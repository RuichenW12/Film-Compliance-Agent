# Policy Loop Gate 3 Design

日期：2026-08-23

状态：设计已确认，待实现

负责人：Richard（B 线）

## 1. 目标

Gate 3 为 Gate 2 的确定性本地 Policy Loop 增加统一管理 API 和两张简洁的政策管理页面。浏览器必须能够完成：

```text
触发 fixture crawl
→ 查看 run 状态
→ 打开 pending proposal
→ 查看 Diff、impact、effective_from 和 draft pack updates
→ 人工 Publish 或 Discard
→ 在列表页看到发布后的 snapshot
```

这是一条真实连接 Gate 2 Python 模块的本地闭环，不是静态页面或前端 mock 数据演示。

## 2. 范围

### 2.1 必须实现

- FastAPI 管理 API，路由前缀为 `/v1/admin/policy`。
- `X-Mock-Role: admin` 的最小 mock admin 鉴权。
- crawl、run 状态、proposal 列表与详情、publish、discard、snapshot 列表。
- FastAPI background task 驱动的 fixture refresh；`202` 响应不等待 refresh 完成。
- Next.js App Router 下的政策列表页和 proposal 详情页。
- future-effective proposal 的前端禁用和后端拒绝双重约束。
- Publish 后对 Gate 2 outbox 做一次 best-effort dispatch。
- API、前端组件、production build 和真实浏览器闭环验证。
- 页面明确标注 `Synthetic local fixture`，避免被当作真实政策数据。

### 2.2 明确不做

- 登录页、用户库、Session、RBAC 或真实身份系统。
- Firestore、GCS、Pub/Sub、Cloud Run、Scheduler 或部署配置。
- 真实 HTTP 政策抓取和 Gemini proposal。
- 通用后台框架、UI 组件库、图表、动画、暗色模式或可视化规则编辑器。
- proposal 编辑、评论、多人审批、预约发布或修订历史。
- Policy 页面以外的产品 UI。
- API 进程重启后的本地 demo 状态持久化。

真实云 adapter 属于 Gate 4；部署联调属于 Gate 5。

## 3. 架构与边界

```text
Browser
  → Next.js Policy Administration UI
  → FastAPI /v1/admin/policy/*
  → Gate 2 launcher / repository / refresh / publisher / dispatcher
  → in-memory state + fixture source + local file blob adapter
```

FastAPI 只负责鉴权、请求校验、后台任务排队、错误映射和响应转换。路由不得复制 refresh、publish、discard 或 outbox 业务规则，也不得直接操作 repository 内部字典。

Next.js 只通过 `web/lib/policy-api.ts` 访问管理 API。页面不得读取 fixture、`file://` URI、Python 文件或 Gate 2 内存状态。

Gate 3 使用一套进程级 `PolicyApiState` 组装本地模块。API 进程存活期间，crawl、proposal、publish 和 snapshot 读取共用同一 repository。进程重启会恢复初始 demo 状态。

## 4. 本地 fixture 演示状态

API 启动时完成以下确定性准备：

1. 从 `policy/seed-snapshot-v1.yaml` 装载 snapshot `v1`。
2. 使用 `tests/fixtures/policy/source-v1.html` 执行一次内部 baseline refresh。
3. 将 fixture fetcher 的当前路径切换到 `source-v2.html`。
4. 不保留 baseline run 作为页面最新手动任务。

因此用户第一次点击 `Run fixture crawl` 就会对已有 baseline 执行 Diff，并创建一个 pending proposal。再次 crawl 时由于 source state 已是 v2，结果为 `no_change`。

proposal draft 使用确定性 fake adapter，内容来自 Gate 2 fixture 场景：

- summary：`分类标准正式公布`；
- impact：`D1c`；
- effective time：固定为可发布的过去时间；
- pack update：`p3_tier_thresholds.thresholds_published=true`。

页面必须把上述数据标为 synthetic fixture，不表示真实政策事实。

## 5. 后端组件

### 5.1 PolicyRunLauncher

位置：`workers/policy/launch.py`

Launcher 是 route 与 `PolicyRefreshModule` 之间的窄边界：

- `launch(source_id, now)` 创建 running record 并返回 `run_id`；
- `execute(run_id, source_id, now)` 调用 refresh；
- run ID 使用进程内单调计数生成；
- refresh 失败由 Gate 2 写入 failed run，后台任务不得删除失败记录。

FastAPI route 调用 `launch` 后，把 `execute` 加入 `BackgroundTasks`，随后立即返回 `202`。

### 5.2 PolicyApiState

位置：`api/deps/policy.py`

该对象持有：

- repository；
- launcher；
- publisher；
- dispatcher；
- blob reader；
- injectable clock。

应用工厂接收可选的 `PolicyApiState`，测试使用 `tmp_path` 和固定 clock 注入确定性状态，生产式本地启动则由 lifespan 创建和清理临时 blob 目录。

### 5.3 管理路由

位置：`api/routes/admin_policy.py`

提供：

```text
POST /v1/admin/policy/crawl
GET  /v1/admin/policy/runs/{run_id}
GET  /v1/admin/policy/proposals?status=pending
GET  /v1/admin/policy/proposals/{proposal_id}
POST /v1/admin/policy/proposals/{proposal_id}/publish
POST /v1/admin/policy/proposals/{proposal_id}/discard
GET  /v1/admin/policy/snapshots
```

所有端点要求 `X-Mock-Role: admin`。缺失或其他值返回 403。

Publish actor 固定为 `admin_richard`。Publish 成功后 route 调用 dispatcher 一次；dispatch 失败只保留 pending outbox 并记录错误，不回滚 snapshot，也不把成功的 `201` 改成失败。

### 5.4 API 响应模型

位置：`api/models/policy.py`

API 使用专用 Pydantic response models，不修改 Gate 1 冻结的共享契约。

proposal summary 返回：

- `proposal_id`；
- `summary`；
- `impact`；
- `effective_from`；
- `status`。

proposal detail 额外返回：

- `source_diff_uri`；
- `source_diff_text`；
- `draft_pack_updates`；
- `published_version`。

Gate 2 的 diff blob 是 `PolicyDiff` JSON。API 通过注入的 blob reader 读取并解析，只把 `unified_diff` 作为 `source_diff_text` 返回，浏览器不直接访问 `file://`。

snapshot summary 返回：

- `version`；
- `published_at`；
- `effective_from`；
- `published_by`；
- `thresholds_published`。

snapshot 按 `published_at` 降序；proposal 按 `created_at` 降序。Gate 3 不增加分页，因为本地演示数据不会超过 100 条。

## 6. HTTP 与错误约束

所有错误沿用统一信封：

```json
{
  "error": {
    "code": "POLICY_NOT_EFFECTIVE",
    "message": "proposal is not effective yet",
    "details": {}
  }
}
```

最小错误映射：

| code | HTTP | 场景 |
|---|---:|---|
| `POLICY_ADMIN_FORBIDDEN` | 403 | mock role 不是 admin |
| `POLICY_RUN_NOT_FOUND` | 404 | run 不存在 |
| `POLICY_PROPOSAL_NOT_FOUND` | 404 | proposal 不存在 |
| `POLICY_PROPOSAL_CONFLICT` | 409 | proposal 非 pending |
| `POLICY_NOT_EFFECTIVE` | 409 | proposal 尚未生效 |
| `SNAPSHOT_NOT_FOUND` | 503 | seed/current snapshot 缺失 |
| `POLICY_BLOB_READ_FAILED` | 500 | proposal diff 无法安全读取或解析 |

Pydantic 请求校验保留 FastAPI 的 422。业务错误不得返回 traceback、内部路径、完整政策正文或 token。

本地跨域只允许 `http://localhost:3000` 和 `http://127.0.0.1:3000`。`X-Mock-Role` 是演示标记，不是安全凭证，不能用于 Gate 4/5 部署。

## 7. 页面设计

### 7.1 列表页 `/admin/policy`

页面采用单列、内容宽度受限的管理布局，包含：

1. 标题 `Policy Administration` 和 `Synthetic local fixture` 标识。
2. Crawl 卡片：`Run fixture crawl` 按钮、最新 run ID、状态、完成时间和错误。
3. Pending Proposals：summary、impact、effective time 和详情链接。
4. Published Snapshots：version、effective time、publisher、thresholds 状态。

点击 crawl 后按钮进入 busy 状态。收到 `202` 后页面轮询对应 run；终态为 `no_change | proposal_created | failed` 时停止，并刷新 proposal 和 snapshot 数据。轮询请求失败时停止并显示行内错误，避免无限请求。

### 7.2 详情页 `/admin/policy/proposals/[proposalId]`

页面显示：

- summary；
- impact chips；
- effective time；
- 等宽、保留换行的 source Diff；
- 可折叠的只读 `draft_pack_updates` JSON；
- `Publish` 和 `Discard`。

当 `effective_from > browser now` 时，Publish 按钮禁用并显示原因。服务端仍独立执行同一校验。Publish 或 Discard 成功后返回列表页并刷新数据。

### 7.3 视觉约束

- 黑、白、灰为主色，一个蓝色操作色。
- 轻量边框、8px 基础间距体系和清晰的状态色。
- 桌面优先，同时保证窄屏不产生横向页面滚动。
- 不引入图片、图标包、字体服务、组件库、图表或动画。
- 所有按钮必须有文字标签，状态不能只靠颜色表达。

## 8. 前端数据层

位置：`web/lib/policy-api.ts`

该文件集中定义 TypeScript DTO 和以下函数：

- `startCrawl`；
- `getRun`；
- `listPendingProposals`；
- `getProposal`；
- `publishProposal`；
- `discardProposal`；
- `listSnapshots`。

每个请求固定发送 `X-Mock-Role: admin`，使用 `NEXT_PUBLIC_POLICY_API_BASE_URL`，默认 `http://127.0.0.1:8000`。非 2xx 响应解析统一错误信封并抛出 `PolicyApiError`。页面不重复编写 fetch/error 逻辑。

## 9. 测试策略

### 9.1 后端 TDD

使用 pytest 和 FastAPI TestClient 覆盖：

- 缺少 admin role 返回 403 错误信封；
- crawl 返回 202 和 run ID；
- background refresh 生成 proposal；
- run、proposal 和 snapshot 的 404；
- pending proposal 列表和详情 Diff 内容；
- future-effective publish 返回 409；
- publish 返回 v2 并可在 snapshot 列表读取；
- discard 返回 204，重复操作返回 409；
- snapshots 按发布时间降序；
- dispatcher 失败不改变 publish 的 201。

每个行为先写失败测试并观察预期失败，再做最小实现。

### 9.2 前端 TDD

使用 Vitest、jsdom 和 React Testing Library 覆盖：

- 列表页渲染 fixture 标识、pending proposal 和 snapshots；
- crawl 后轮询至终态并刷新数据；
- API 错误显示为行内提示；
- future-effective proposal 禁用 Publish；
- Publish/Discard 调用正确 API 并导航返回。

不使用大面积 snapshot test，不测试 CSS 像素值。

### 9.3 构建与浏览器验收

完成前必须运行：

```text
pytest
npm test
npm run build
```

随后启动 FastAPI 和 Next.js，用真实浏览器完成：

```text
打开 /admin/policy
→ Run fixture crawl
→ 等待 proposal_created
→ 打开 proposal_001
→ 核对 Diff、impact 和 effective time
→ Publish
→ 返回列表并看到 v2 snapshot
```

同时直接请求无 admin header 的 API，确认返回 403。

## 10. Gate 3 退出条件

Gate 3 仅在以下条件全部满足时完成：

1. Python 全量测试通过。
2. 前端组件测试通过。
3. Next.js production build 通过。
4. 真实浏览器完成 fixture crawl 到 v2 snapshot 的完整闭环。
5. future-effective proposal 在 UI 和 API 两侧均不可发布。
6. 页面明确标注 synthetic fixture。
7. 独立代码复核没有未解决的 Critical 或 Important 问题。
8. 未引入 Gate 4 或 Gate 5 的云端与部署内容。

Gate 2 PR 合并前，Gate 3 分支可以基于 Gate 2 已验证提交开发；创建 Gate 3 PR 前必须先把分支对齐合并后的 `main`，使 PR 只包含 Gate 3 变更。

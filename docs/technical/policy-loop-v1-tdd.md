# Richard Policy Loop v1 Technical Design Document

日期：2026-08-23

状态：待实现

负责人：Richard（B 线）

上位规格：[Richard 政策回路 v1 设计](../superpowers/specs/2026-08-22-richard-policy-loop-v1-design.md)

## 1. 目的与完成边界

本 TDD 把已确认的 Policy Loop v1 范围转换为可直接编码和测试的技术决策。v1 只完成一条纵向闭环：

```text
一个官方政策页
→ 原文归档与规范化
→ 确定性 Diff
→ Gemini 草拟提案
→ 管理员在政策页发布
→ Firestore snapshot + outbox
→ Pub/Sub policy.updated
→ 项目 stale 标记、暂定档位重算与通知
```

完成本 TDD 不代表上述能力已实现。实现完成必须以第 13 节测试和端到端验收结果为准。

### 1.1 v1 必须保留

- A/B 两线通过 `schemas/` 契约相遇。
- A 线可在无爬虫时读取静态 seed snapshot。
- AI 只草拟 proposal，不能发布 snapshot。
- `effective_from` 决定快照何时可发布、何时可被读取。
- snapshot、proposal 状态和 outbox 在一个 Firestore transaction 中提交。
- `policy.updated` 重复投递不产生重复业务副作用。
- frozen form、submitted materials、registration number 不被政策事件修改。

### 1.2 v1 不实现

- 多来源通用爬虫框架；
- 规则级生效时间；
- 预约发布和自动激活；
- 多级审批、评论或 proposal 修订历史；
- rule-level impact 和全项目精确影响分析；
- 管理员之外的真实身份系统；
- 邮件、短信和移动推送；
- A 线 D1c 分类规则本身。

## 2. 技术栈与运行单元

| 层 | 选择 |
|---|---|
| Policy/API runtime | Python 3.11、FastAPI、Pydantic 2 |
| HTTP fetch | httpx |
| HTML extraction | BeautifulSoup4，首个来源使用 `#zoom` |
| AI proposal | Google Gen AI SDK 2.x、`gemini-3.5-flash` |
| State | Firestore Native mode |
| Blobs | Cloud Storage |
| Events | Pub/Sub |
| Scheduling | Cloud Scheduler → Cloud Run Job |
| Admin UI | Next.js App Router、TypeScript |
| Tests | pytest、Firestore/Pub/Sub emulator、前端测试框架由 A 线统一初始化 |

Policy Loop 使用两个运行单元：

1. 统一 API 服务：承载 `/v1/admin/policy/*`，负责 mock admin 鉴权、请求校验和响应转换。
2. Policy worker：承载刷新 Job、outbox dispatcher 和 `policy.updated` push consumer。

Gemini 使用独立环境变量 `GOOGLE_CLOUD_LOCATION=global`；Firestore、GCS、Cloud Run 的项目区域沿用团队环境配置，不由本 TDD重新定义。

## 3. 目录和文件职责

```text
api/
  routes/admin_policy.py          # Richard：统一 API 中的政策管理路由
  routes/internal_policy.py       # Scheduler 使用 internal token 的触发路由
  deps/policy.py                  # 组装 Policy 模块与 admin/internal 依赖

schemas/
  policy_snapshot.py              # 共享数据模型和枚举
  snapshot.py                     # SnapshotService interface 与适配器选择

policy/
  policy_sources.yaml             # 首个真实来源配置
  seed-snapshot-v1.yaml           # A/B 共用静态 seed

prompts/policy/
  proposal-v1.md                  # Gemini 结构化提案 prompt

workers/policy/
  launch.py                       # PolicyRunLauncher
  refresh.py                      # PolicyRefreshModule
  publish.py                      # PolicyPublisher
  outbox.py                       # OutboxDispatcher
  consumer.py                     # PolicyUpdatedConsumer
  normalize.py                    # 纯函数正文规范化和 Diff
  adapters/
    cloud_run_job.py              # 生产异步 Job launcher adapter
    inline_job.py                 # 本地/测试 launcher adapter
    http_source.py                # httpx 官方页面 adapter
    fixture_source.py             # 测试 fixture adapter
    gcs_blob.py                   # GCS blob adapter
    file_blob.py                  # 本地测试 blob adapter
    firestore_policy.py           # proposal/snapshot/outbox/state adapter
    gemini_proposal.py            # Gemini proposal adapter
    fake_proposal.py              # 确定性测试 adapter
    recalc_api.py                 # A 线 internal recalc-tier adapter

web/
  app/admin/policy/page.tsx
  app/admin/policy/proposals/[proposalId]/page.tsx
  lib/policy-api.ts

tests/
  contract/test_policy_contract.py
  fixtures/policy/source-v1.html
  fixtures/policy/source-v2.html
  fixtures/policy/policy-updated-v2.json
  policy/test_snapshot_service.py
  policy/test_launch.py
  policy/test_normalize.py
  policy/test_refresh.py
  policy/test_publish.py
  policy/test_outbox.py
  policy/test_consumer.py
  policy/test_admin_routes.py
```

不为每个文件创建公共 interface。只有存在生产 adapter 与测试 adapter 的行为才形成 seam。

## 4. 模块和 interface

### 4.1 SnapshotService

位置：`schemas/snapshot.py`

这是 A 线读取政策知识的唯一 interface：

```python
class SnapshotService:
    def latest_version(self, as_of: datetime | None = None) -> str: ...
    def get_pack(self, name: PackName, version: str | None = None) -> dict: ...
    def clause(self, clause_id: str, version: str) -> Clause: ...
```

约束：

- `as_of=None` 使用当前 UTC 时间。
- `latest_version` 只选择 `effective_from <= as_of` 的快照；按 `effective_from DESC, published_at DESC` 取第一条。
- `version=None` 时，`get_pack` 使用 `latest_version()`。
- 本地 adapter 读取 `policy/seed-snapshot-v1.yaml`。
- 云端 adapter 读取 Firestore snapshot，并按 pack 中的 `blob_uri` 读取 GCS。
- 找不到有效快照返回 `SNAPSHOT_NOT_FOUND`，不回退到未来快照。

### 4.2 PolicyRunLauncher

位置：`workers/policy/launch.py`

```python
class PolicyRunLauncher:
    async def start(
        self,
        source_id: str,
        actor_uid: str,
        now: datetime,
    ) -> str: ...  # run_id
```

`start` 校验 source、创建 `policy_runs/{run_id}`，再通过 Job adapter 启动后台执行。生产 adapter 调用 Cloud Run Jobs Execute；本地 adapter 在同一进程异步调用 refresh。Job 启动失败时，run 立即标记为 `failed`。

API 的 `202` 只由 launcher 返回，不等待 fetch 或 Gemini 完成。

### 4.3 PolicyRefreshModule

位置：`workers/policy/refresh.py`

```python
class PolicyRefreshModule:
    async def run(
        self,
        run_id: str,
        source_id: str,
        now: datetime,
    ) -> RefreshResult: ...
```

`run` 隐藏 fetch、归档、规范化、hash、Diff 和 proposal 生成。调用者只需知道：

```python
class RefreshResult(BaseModel):
    run_id: str
    status: Literal["no_change", "proposal_created"]
    proposal_id: str | None
    previous_sha256: str | None
    current_sha256: str
```

异常不作为成功结果返回；模块将 run 标记为 `failed` 后抛出结构化 `PolicyRefreshError`。

### 4.4 PolicyPublisher

位置：`workers/policy/publish.py`

```python
class PolicyPublisher:
    def publish(
        self,
        proposal_id: str,
        actor_uid: str,
        now: datetime,
    ) -> PublishResult: ...

    def discard(
        self,
        proposal_id: str,
        actor_uid: str,
        now: datetime,
    ) -> None: ...
```

```python
class PublishResult(BaseModel):
    snapshot_version: str
    outbox_id: str
```

`publish` 隐藏 proposal 校验、版本生成、snapshot 合并和 outbox 写入。调用者不能分别调用这些内部步骤。

### 4.5 OutboxDispatcher

位置：`workers/policy/outbox.py`

```python
class OutboxDispatcher:
    def dispatch(self, limit: int = 20) -> DispatchSummary: ...
```

```python
class DispatchSummary(BaseModel):
    selected: int
    sent: int
    failed: int
```

v1 每次最多处理 20 条 pending 记录。Pub/Sub 返回 message ID 后才把记录标为 `sent`。

### 4.6 PolicyUpdatedConsumer

位置：`workers/policy/consumer.py`

```python
class PolicyUpdatedConsumer:
    async def handle(self, event: PolicyUpdatedEvent) -> ConsumeResult: ...
```

```python
class ConsumeResult(BaseModel):
    stale_marked: int
    recalculated: int
    already_processed: bool
```

消费者负责 policy update 的业务副作用，但不包含 D1c 规则。档位计算始终调用 A 线 `recalc-tier`。

## 5. 内部 seams 与 adapters

以下 interface 仅供 `workers/policy/` 内部依赖注入，不暴露给 A 线：

```python
class SourceFetcher(Protocol):
    async def fetch(self, source: PolicySource) -> FetchedSource: ...

class BlobStore(Protocol):
    def put_raw(self, source_id: str, content: bytes, fetched_at: datetime) -> BlobRef: ...
    def put_normalized(self, source_id: str, text: str, fetched_at: datetime) -> BlobRef: ...
    def put_diff(self, source_id: str, diff: PolicyDiff, created_at: datetime) -> BlobRef: ...

class ProposalModel(Protocol):
    async def draft(self, request: ProposalRequest) -> ProposalDraft: ...

class RecalcClient(Protocol):
    async def recalc_tier(self, project_id: str, snapshot_version: str) -> RecalcResult: ...

class RefreshJobAdapter(Protocol):
    async def launch(self, run_id: str, source_id: str) -> None: ...
```

每个 seam 至少有两个 adapters：真实云端 adapter 和确定性测试 adapter。Firestore 数据访问集中在 `FirestorePolicyRepository`，不让路由或 UI 直接拼 collection 路径。

## 6. 共享数据契约

位置：`schemas/policy_snapshot.py`

### 6.1 枚举

```python
class ImpactNode(StrEnum):
    D1C = "D1c"
    C1A = "C1-a"

class ProposalStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    DISCARDED = "discarded"

class OutboxStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
```

### 6.2 PolicySnapshot

```python
class PolicySnapshot(BaseModel):
    version: str                 # 必须匹配 ^v[1-9][0-9]*$
    published_at: datetime
    effective_from: datetime
    published_by: str
    packs: PolicyPacks
    diff_from_prev: SnapshotDiff
    thresholds_published: bool
```

`PolicyPacks` 固定包含 `p1_form_definition` 至 `p6_legal_clauses` 六个键。每个 pack 的值允许 inline dict 或 `{"blob_uri": "gs://..."}`，但同一个 pack 不能同时使用两种形态。

### 6.3 PolicyProposal

Firestore document ID 作为 proposal ID，不在 document body 重复存储：

```python
class PolicyProposal(BaseModel):
    created_at: datetime
    source_diff_uri: str
    summary: str
    impact: list[ImpactNode]
    effective_from: datetime
    draft_pack_updates: dict[PackName, dict]
    status: ProposalStatus
    published_version: str | None
```

约束：

- `summary` 长度为 1–1000 字符。
- `impact` 去重后至少一个节点。
- `draft_pack_updates` 至少更新一个已知 pack。
- `status=pending|discarded` 时 `published_version=None`。
- `status=published` 时 `published_version` 必填。

### 6.4 PolicyUpdatedEvent

```python
class PolicyUpdatedEvent(BaseModel):
    snapshot_version: str
    impact: list[ImpactNode]
    thresholds_published: bool
    effective_from: datetime
    published_at: datetime
    idempotency_key: str
```

Publisher 固定生成 `idempotency_key = f"policy.updated:{snapshot_version}"`。消费者拒绝不符合该派生规则的事件。

### 6.5 PolicyOutbox

```python
class PolicyOutbox(BaseModel):
    topic: Literal["policy.updated"]
    payload: PolicyUpdatedEvent
    status: OutboxStatus
    created_at: datetime
    sent_at: datetime | None
    pubsub_message_id: str | None
```

`pending` 时发送字段必须为空；`sent` 时 `sent_at` 和 `pubsub_message_id` 必填。

## 7. 政策来源、规范化和 Diff

### 7.1 初始来源

`policy/policy_sources.yaml` 只配置一个来源：

```yaml
sources:
  - id: nrta_micro_drama_management_measures
    url: https://www.nrta.gov.cn/art/2026/7/31/art_113_73785.html
    content_selector: "#zoom"
    enabled: true
```

### 7.2 规范化算法

`workers/policy/normalize.py` 使用纯函数执行：

1. 用 `content_selector` 选择正文；选择不到或正文为空则失败。
2. 删除 `script`、`style`、`noscript`。
3. 把 `&nbsp;` 和 Unicode 不换行空格转换为普通空格。
4. 对每个段落执行首尾去空白和连续空白折叠。
5. 丢弃空段落，段落之间用单个 `\n` 连接。
6. 对 UTF-8 文本计算 SHA-256。

Diff 输入是前后两个规范化文本，不比较原始 HTML。输出 `PolicyDiff`：

```python
class PolicyDiff(BaseModel):
    source_id: str
    previous_sha256: str
    current_sha256: str
    unified_diff: str
```

无 previous source state 时，首次抓取只建立基线，不创建 proposal。

## 8. 存储布局

### 8.1 Cloud Storage

```text
gs://{GCS_BUCKET}/policy/raw/{source_id}/{yyyy}/{mm}/{dd}/{sha256}.html
gs://{GCS_BUCKET}/policy/normalized/{source_id}/{sha256}.txt
gs://{GCS_BUCKET}/policy/diffs/{source_id}/{previous_sha256}..{current_sha256}.json
gs://{GCS_BUCKET}/policy/packs/{snapshot_version}/{pack_name}.json
```

相同 URI 的写入必须幂等；内容 hash 不同不得覆盖已有对象。

### 8.2 Firestore

```text
policy_source_states/{source_id}
  last_success_at, raw_uri, normalized_uri, normalized_sha256

policy_runs/{run_id}
  source_id, status, started_at, finished_at,
  previous_sha256, current_sha256, proposal_id, error

policy_proposals/{proposal_id}
  PolicyProposal fields

policy_snapshots/{version}
  PolicySnapshot fields

policy_outbox/{outbox_id}
  PolicyOutbox fields

policy_event_receipts/{idempotency_key}
  processed_at, snapshot_version
```

`policy_runs.status` 枚举为 `running | no_change | proposal_created | failed`。`outbox_id` 固定等于 `idempotency_key`，因此同一个 snapshot 不能产生第二条 outbox。

## 9. 刷新与提案流程

1. Admin API 或 internal Scheduler route 调用 PolicyRunLauncher。
2. Launcher 创建 `policy_runs/{run_id}`，状态为 `running`，并触发后台 Job。
3. Job 用 run_id 和 source_id 调用 PolicyRefreshModule。
4. `SourceFetcher` 获取原始 bytes；HTTP 非 2xx、超时或空 body 均失败。
5. 先保存 raw HTML，再提取和保存 normalized text。
6. 与 `policy_source_states/{source_id}` 比较 SHA-256。
7. SHA 相同：run=`no_change`，不调用 Gemini。
8. 无 previous state：更新 source state，run=`no_change`，作为初始基线。
9. SHA 不同：生成并保存 `PolicyDiff`。
10. `ProposalModel` 根据 Diff 输出结构化 `ProposalDraft`。
11. Pydantic 校验失败时用同一 schema 修复重试，最多两次。
12. 成功后创建 pending proposal，更新 source state，run=`proposal_created`。
13. 任一步失败：run=`failed`，保留上一 source state 和所有已发布 snapshot。

Gemini prompt 只接收来源 URL、previous/current hash、unified diff 和允许的 impact/pack 枚举。网页内容置于数据分隔符内，不作为指令。

## 10. 发布事务与 outbox

`PolicyPublisher.publish()` 在一个 Firestore transaction 中：

1. 读取 proposal，要求 `status=pending`。
2. 要求 `effective_from <= now`，否则抛出 `POLICY_NOT_EFFECTIVE`。
3. 校验 `draft_pack_updates` 对应 pack schema。
4. 读取最新已发布 snapshot，把其 packs 与 draft updates 合并。
5. 从最新 `vN` 解析 N，生成 `v{N+1}`；无 snapshot 时发布失败，seed 必须先导入。
6. 创建新的 PolicySnapshot。
7. proposal 更新为 `published` 并写入 `published_version`。
8. 创建 outbox，ID 与 `policy.updated:v{N+1}` 相同。

事务外不发布 Pub/Sub。OutboxDispatcher 发送成功后才更新 outbox；若发送成功但状态更新失败，下一次可能重复发送，最终由 consumer 幂等吸收。

Publish 成功后 API 对 dispatcher 做一次 best-effort 调用；发送失败不回滚 snapshot，接口仍返回 201，outbox 保持 pending。另一个每分钟运行的 Scheduler 调用 dispatcher 补偿所有 pending 记录，因此发布可靠性不依赖请求线程。

Discard 只把 pending proposal 改为 discarded，不删除 proposal、Diff 或原始归档。

## 11. policy.updated 消费

处理顺序：

1. 校验 event schema、版本格式和派生 idempotency key。
2. 若 `policy_event_receipts/{idempotency_key}` 已存在，返回 `already_processed=true`。
3. 用 `^v[1-9][0-9]*$` 解析 event 和 project snapshot 的整数版本；不合法的项目版本记录错误并保持 stale，不执行自动重算。
4. 对使用更旧 snapshot 的项目执行节点级映射：
   - `D1c`：已有 classification 的项目设置 `policy_stale=true`；其中 `tier_provisional=true` 的项目调用 `recalc-tier`。
   - `C1-a`：已有 review 结果的项目设置 `policy_stale=true`，v1 不自动重跑剧本审查。
5. notification 和 timeline 使用确定性 ID `{event_key}:{project_id}:{kind}`，重复写为覆盖。
6. `recalc-tier` 请求携带 `snapshot_version`，A 线端点必须对同一版本幂等。
7. 所有项目完成后写 event receipt。

如果任一 recalc 调用失败，不写 event receipt，消息返回非 2xx 让 Pub/Sub 重试。已完成的 stale/notification 写入和 recalc 请求在重试时保持幂等。

v1 演示项目不超过 100 个；consumer 单次最多查询 100 个项目。超过该规模的分页和分片属于 P1。

## 12. HTTP interface 与政策页

### 12.1 统一 API 路由

位置：`api/routes/admin_policy.py`

所有管理端点要求 `X-Mock-Role: admin`，否则返回 403：

```text
POST /v1/admin/policy/crawl
  body: {"source_id":"nrta_micro_drama_management_measures"}
  202: {"run_id":"run_xxx"}

GET /v1/admin/policy/runs/{run_id}
  200: policy run status

GET /v1/admin/policy/proposals?status=pending
  200: proposal summaries

GET /v1/admin/policy/proposals/{proposal_id}
  200: proposal + side_by_side URIs

POST /v1/admin/policy/proposals/{proposal_id}/publish
  201: {"snapshot_version":"v2"}

POST /v1/admin/policy/proposals/{proposal_id}/discard
  204

GET /v1/admin/policy/snapshots
  200: snapshot summaries ordered by published_at DESC
```

路由不直接访问 Firestore/GCS，也不实现发布逻辑；crawl 调 PolicyRunLauncher，publish/discard 调 PolicyPublisher。Publish 成功后的 dispatcher 调用只是 best-effort 交付尝试，不改变发布事务结果。

Scheduler 每日调用以下 internal route，使用 `X-Internal-Token`，并走同一个 launcher：

```text
POST /v1/internal/policy/crawl
Body: {"source_id":"nrta_micro_drama_management_measures"}
202: {"run_id":"run_xxx"}
```

### 12.2 A 线 internal interface

```text
POST /v1/internal/projects/{project_id}/recalc-tier
Header: X-Internal-Token
Body: {"snapshot_version":"v2"}
200: {"tier":"T2","tier_provisional":false,"changed":true}
```

仅 `tier_provisional=true` 可修改。非 provisional、FORM_FROZEN 或 FILED 项目返回 `changed=false`，不报错。

### 12.3 Admin UI

列表页 `/admin/policy` 显示：

- manual crawl 按钮与最新 run 状态；
- pending proposals；
- published snapshots。

详情页 `/admin/policy/proposals/{proposalId}` 显示：

- summary；
- source Diff；
- impact；
- effective_from；
- draft_pack_updates JSON 只读预览；
- Publish 和 Discard。

`effective_from > now` 时前端禁用 Publish；服务端仍执行同一校验，不能依赖前端保证。

## 13. 错误、日志与安全

### 13.1 错误码

| code | HTTP | 场景 |
|---|---:|---|
| `POLICY_SOURCE_NOT_FOUND` | 404 | source_id 未配置或 disabled |
| `POLICY_FETCH_FAILED` | 502 | timeout、非 2xx 或空 body |
| `POLICY_EXTRACT_FAILED` | 422 | selector 不存在或正文为空 |
| `POLICY_PROPOSAL_INVALID` | 502 | Gemini 两次修复后仍不合法 |
| `POLICY_PROPOSAL_CONFLICT` | 409 | proposal 非 pending |
| `POLICY_NOT_EFFECTIVE` | 409 | effective_from 晚于 now |
| `SNAPSHOT_NOT_FOUND` | 503 | 无当前有效 snapshot |
| `POLICY_EVENT_INVALID` | 422 | event 与派生 key/版本不一致 |

错误沿用统一信封：

```json
{"error":{"code":"POLICY_NOT_EFFECTIVE","message":"...","details":{}}}
```

### 13.2 结构化日志

所有 Policy 模块记录：

```text
source_id, run_id, proposal_id, snapshot_version,
idempotency_key, module, status, latency_ms
```

日志不得包含完整政策正文、prompt、内部 token 或用户材料。正文只记录 URI 和 SHA-256。

### 13.3 网络与权限

- 官方来源只允许 `policy_sources.yaml` 中的 HTTPS URL，用户不能传任意 URL，避免 SSRF。
- Admin route 只接受 mock admin role；真实 auth 不在 v1。
- Worker 调 A 线只使用 Secret Manager 注入的 internal token。
- GCS 和 Firestore 使用服务账号最小权限。

## 14. 测试策略

### 14.1 Contract tests

`tests/contract/test_policy_contract.py` 必须覆盖：

- seed snapshot 可被 SnapshotService 读取；
- future-effective snapshot 不会成为 latest；
- A/B 两线可解析同一个 `policy.updated` fixture；
- 不合法 version、impact 或派生 idempotency key 被拒绝；
- `recalc-tier` 的请求和响应形状固定。

### 14.2 Pure/module tests

- `test_normalize.py`：HTML 噪声变化不改变 normalized hash；正文变化产生 Diff。
- `test_launch.py`：202 前创建 run；Job 启动失败时 run=failed；inline adapter 使用同一 run_id。
- `test_refresh.py`：首次建基线、重复无变化、变化生成 proposal、失败保留 previous state。
- `test_publish.py`：future proposal 拒绝；一次 transaction 产生 snapshot、proposal 状态和 outbox；重复发布冲突。
- `test_outbox.py`：发送成功标 sent；发送失败保留 pending；重复 dispatch 不产生第二个业务结果。
- `test_consumer.py`：provisional 重算、frozen/FILED 不变、通知确定性、事件重放无副作用。
- `test_admin_routes.py`：非 admin 403；route 只调用 module interface；错误码映射正确。

### 14.3 Emulator integration

使用 Firestore/Pub/Sub emulator 验证：

- publish transaction 原子性；
- outbox → Pub/Sub → consumer；
- provisional 与 frozen 双项目对照；
- 同一 Pub/Sub message 重放两次。

真实 NRTA 页面和真实 Gemini 调用属于单独 smoke test，不进入每次本地单测。Smoke 结果必须标注日期、模型和云项目，不能用 fixture 结果代替。

## 15. 开发顺序和提交闸门

### Gate 1：契约握手

先创建 shared schemas、seed snapshot 和 contract fixtures。退出条件：A 线 SnapshotService 读通 seed，双方 contract tests 绿色。

### Gate 2：本地 fixture 闭环

实现 file/fake adapters、refresh、proposal、publish、outbox 和 consumer。退出条件：不使用网络或 GCP 即可完成十二步核心演示。

### Gate 3：政策管理页

实现统一 API routes 和 Richard 的两个政策页面。退出条件：浏览器可触发 fixture crawl、查看 proposal、发布并看到 snapshot 状态。

### Gate 4：真实云 adapter

替换为 HTTP、GCS、Firestore、Gemini、Pub/Sub adapters。退出条件：一个真实 NRTA 来源 smoke 成功，失败时 last-known-good 仍可读。

### Gate 5：部署联调

接 Cloud Run Job、每日 crawl Scheduler、每分钟 outbox Scheduler、push consumer 和 A 线 recalc stub/real endpoint。退出条件：部署环境连续三次端到端通过，frozen project hash 和 registration number 均未变化。

任何 Gate 未通过，不进入下一 Gate。真实来源阻塞时可继续使用 fixture 演示，但不得跳过 publish、outbox、consumer、provisional recalculation 和 frozen-data invariant。

## 16. 外部 interface 变更纪律

以下内容一经 Gate 1 冻结，修改必须由 Maxine 和 Richard 共同确认：

- PolicySnapshot、PolicyProposal、PolicyUpdatedEvent 字段；
- SnapshotService interface；
- `policy.updated` topic payload；
- `/v1/internal/projects/{id}/recalc-tier` 请求与响应；
- `ImpactNode` 枚举。

Policy 模块内部 adapters、文件拆分和实现细节由 Richard 自主调整，只要不改变上述 interface 和验收行为。

## 17. 参考

- [国家广播电视总局令第16号：《微短剧发展管理办法》](https://www.nrta.gov.cn/art/2026/7/31/art_113_73785.html)
- [Gemini 3.5 Flash model documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-flash)

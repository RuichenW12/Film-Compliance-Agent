# Richard 政策回路 v1 设计

日期：2026-08-22

状态：已确认范围，待实现

负责人：Richard（B 线）

## 1. 目标

在 Hackathon v1 中实现一条真实、可演示、可回放的政策更新闭环：

```text
官方政策页
→ 抓取并保存原文
→ 正文规范化与文本 Diff
→ Gemini 生成结构化提案
→ 管理员在政策页人工确认
→ 发布新的 PolicySnapshot
→ outbox 发送 policy.updated
→ 受影响项目打标
→ 暂定档位项目重算
→ 站内通知与时间线可见
```

v1 的完成标准是这条链端到端稳定运行，不建设通用政策平台或通用爬虫框架。

## 2. 已锁定的产品口径

### 2.1 特殊题材

特殊题材命中后，按行业伙伴给出的严格执行口径处理，保持现有判断链：

```text
special_subject_hit = true
tier = T1
co_review_required = true
```

本设计不修改特殊题材判定、协审流程或现有架构导览叙事。

### 2.2 政策生效时间

PolicySnapshot 和 PolicyProposal 增加 `effective_from`。v1 采用快照级生效时间，不做规则级生效时间。

- `SnapshotService.latest_version()` 只能返回 `effective_from <= now` 的最新快照。
- 未来生效的提案可以保存和查看。
- `effective_from > now` 时，政策页禁用 Publish，发布接口也必须拒绝。
- v1 不实现预约发布和到点自动激活。

### 2.3 影响范围

`impact` 继续使用节点级列表，例如 `D1c`、`C1-a`。v1 不增加 rule IDs、项目过滤器或规则级影响计算。

### 2.4 更新边界

`policy.updated` 只允许执行两类动作：

1. 对使用旧快照且命中 `impact` 的项目设置 `policy_stale=true`，并产生通知。
2. 当 `thresholds_published=true` 时，只对 `tier_provisional=true` 的项目调用 A 线 `recalc-tier`。

任何政策更新都不得修改：

- 已冻结表单及其 hash；
- 已提交材料；
- registration number；
- 非 provisional 的最终档位。

## 3. 范围

### 3.1 P0：必须实现

1. PolicySnapshot、PolicyProposal、PolicyUpdatedEvent 契约。
2. 可被 A 线 SnapshotService 读取的 seed snapshot。
3. `effective_from` 校验和当前有效快照选择。
4. 一个真实官方政策来源的抓取、GCS 原文归档、规范化和 Diff。
5. fixture 驱动的变更提案生成。
6. Richard 完整负责的政策管理页 UI。
7. 人工发布事务与最小 outbox。
8. `policy.updated` 幂等消费者。
9. `policy_stale` 和 `tier_recalculated` 两类站内通知及 timeline 事件。
10. Cloud Run Job、Pub/Sub、Cloud Scheduler 和手动触发端点接线。
11. provisional 项目与 frozen/FILED 项目的对照测试。

### 3.2 P1：P0 全绿后再做

- 第二个政策来源；
- 更完整的政策页视觉样式；
- 更好的文本 Diff 高亮；
- clean-clone 部署验证；
- 演示数据整理。

### 3.3 明确不做

- 通用政策知识平台；
- 规则级 `effective_from`；
- 自动预约发布；
- 多级审核流；
- rule-level impact；
- 全项目精确影响查询；
- 通用爬虫框架或复杂反爬；
- 页面结构自动修复；
- 可视化规则编辑器；
- 多人批注和提案修订历史；
- 邮件、短信或移动推送；
- 美国政策来源；
- Veo 素材协助；
- 政策后台以外的 UI。

## 4. 数据契约

### 4.1 PolicySnapshot

在现有快照结构上只增加 `effective_from`：

```json
{
  "version": "v2",
  "published_at": "2026-09-01T00:05:00+08:00",
  "effective_from": "2026-09-01T00:00:00+08:00",
  "published_by": "admin_demo",
  "packs": {
    "p1_form_definition": {},
    "p2_subject_rules": {},
    "p3_tier_thresholds": {},
    "p4_process_templates": {},
    "p5_form_templates": {},
    "p6_legal_clauses": {}
  },
  "diff_from_prev": {
    "summary": "正式公布一、二、三类投资额度标准",
    "impact": ["D1c"]
  },
  "thresholds_published": true
}
```

`version` 沿用 `v1`、`v2` 展示格式。实现内部生成下一版本时解析数字部分，不使用字符串大小比较版本先后。

### 4.2 PolicyProposal

```json
{
  "created_at": "2026-08-31T23:50:00+08:00",
  "source_diff_uri": "gs://film-agent-assets/policy-diffs/diff-001.json",
  "summary": "投资额度分类标准发生变化",
  "impact": ["D1c"],
  "effective_from": "2026-09-01T00:00:00+08:00",
  "draft_pack_updates": {
    "p3_tier_thresholds": {}
  },
  "status": "pending",
  "published_version": null
}
```

约束：

- `status` 只能是 `pending | published | discarded`。
- `published_version` 仅在发布成功后写入。
- `impact` 只能使用双方冻结的节点枚举。
- `draft_pack_updates` 必须通过对应 pack 的 Pydantic schema。

### 4.3 PolicyUpdatedEvent

```json
{
  "snapshot_version": "v2",
  "impact": ["D1c"],
  "thresholds_published": true,
  "effective_from": "2026-09-01T00:00:00+08:00",
  "published_at": "2026-09-01T00:05:00+08:00",
  "idempotency_key": "policy.updated:v2"
}
```

`idempotency_key` 固定由 snapshot version 派生。消费者必须先查重，重复投递返回成功但不重复执行副作用。

### 4.4 PolicyOutbox

```json
{
  "topic": "policy.updated",
  "payload": {},
  "status": "pending",
  "created_at": "2026-09-01T00:05:00+08:00",
  "sent_at": null
}
```

`status` 只需要 `pending | sent`。v1 不建设通用重试控制台。

## 5. 组件与职责

### 5.1 契约与 seed

Richard 负责：

- `schemas/policy_snapshot.py`；
- PolicySnapshot、PolicyProposal、PolicyUpdatedEvent；
- `policy/seed-snapshot-v1.yaml`；
- loader 和 validation tests；
- A/B 两线共用的 JSON fixtures。

A 线只依赖冻结的模型、fixtures 和 SnapshotService 接口，不依赖爬虫实现。

### 5.2 PolicyRefreshJob

v1 只保证一个真实官方来源完整跑通：

1. 从 `policy_sources.yaml` 读取 URL 和正文选择器。
2. 抓取页面，原始 HTML 保存到 GCS。
3. 提取正文，去除导航、脚本、样式、多余空白等稳定噪声。
4. 对规范化正文计算 hash，并与上一版本比较。
5. 无变化时正常结束，不创建 proposal。
6. 有变化时保存 Diff，并调用 ProposalGenerator。
7. 抓取或解析失败时记录结构化日志，继续服务上一快照。

入口包括 Cloud Scheduler 每日触发和政策页手动触发。

### 5.3 ProposalGenerator

Gemini 只接收确定性文本 Diff，输出：

```json
{
  "summary": "...",
  "impact": ["D1c"],
  "effective_from": "...",
  "draft_pack_updates": {}
}
```

输出必须通过 Pydantic 校验。schema 失败最多修复重试两次，仍失败则任务进入 `needs_human`，不得创建可发布提案。

### 5.4 政策管理页

Richard 完整负责：

- `/admin/policy`；
- `/admin/policy/proposals/{id}`；
- 对应 API 接入和页面交互。

页面最小能力：

- 手动触发抓取并查看任务状态；
- 查看 pending proposal 列表；
- 查看 summary、原始文本 Diff、impact、effective_from 和 draft_pack_updates；
- Publish；
- Discard；
- 查看历史快照列表。

未来生效提案显示生效时间，并禁用 Publish。

### 5.5 发布与 outbox

Publish 接口在一个 Firestore transaction 中完成：

1. 校验 proposal 存在且状态为 `pending`；
2. 校验 `effective_from <= now`；
3. 校验 `draft_pack_updates`；
4. 创建下一版本 PolicySnapshot；
5. proposal 更新为 `published` 并写入 `published_version`；
6. 创建 PolicyOutbox 记录。

发布接口不得直接把“已发送 Pub/Sub”作为事务成功条件。独立 dispatcher 发送 pending outbox，成功后更新为 `sent`。

### 5.6 PolicyUpdatedConsumer

消费者按 `idempotency_key` 去重并执行：

1. 查找使用旧快照且受 `impact` 影响的项目。
2. 设置 `policy_stale=true`。
3. 写入 `policy_stale` notification 和 timeline。
4. 若 `thresholds_published=true`，筛选 `tier_provisional=true` 的项目并调用 A 线 `recalc-tier`。
5. 重算成功后写入 `tier_recalculated` notification 和 timeline。

消费者不得直接实现 D1c 规则，档位重算始终由 A 线接口完成。

## 6. API 范围

沿用总手册现有端点：

```text
POST /v1/admin/policy/crawl
GET  /v1/admin/policy/proposals?status=pending
GET  /v1/admin/policy/proposals/{proposal_id}
POST /v1/admin/policy/proposals/{proposal_id}/publish
POST /v1/admin/policy/proposals/{proposal_id}/discard
GET  /v1/admin/policy/snapshots
```

发布接口新增错误：

```json
{
  "error": {
    "code": "POLICY_NOT_EFFECTIVE",
    "message": "The proposal is not effective yet.",
    "details": {"effective_from": "2026-09-01T00:00:00+08:00"}
  }
}
```

HTTP 状态为 `409`。

## 7. 错误处理

- 页面抓取失败：保留 last-known-good 原文和快照，任务失败但线上读取不受影响。
- 正文提取为空：视为解析失败，不创建 Diff。
- Gemini 输出不合法：最多修复两次，之后 `needs_human`。
- proposal 已发布或丢弃：重复 Publish 返回 `409 CONFLICT`。
- 提案尚未生效：返回 `409 POLICY_NOT_EFFECTIVE`。
- Pub/Sub 发送失败：outbox 保持 `pending`，dispatcher 后续重试。
- 消费者重复投递：按 idempotency key 返回成功且无重复副作用。
- A 线 recalc 暂时失败：项目保留 `policy_stale=true`，记录 task error，不修改 provisional 结果。

## 8. 测试与验收

### 8.1 契约测试

- seed snapshot 可被 SnapshotService 读取。
- 缺少 `effective_from` 时校验失败。
- packs 结构非法时校验失败。
- 未来快照不会被 `latest_version()` 选中。
- `policy.updated` fixture 可被 A/B 两线共同反序列化。

### 8.2 抓取与 Diff

- 同一页面连续运行两次，第二次 Diff 为空。
- 修改 fixture 正文后产生 Diff 和 proposal。
- 页面超时或正文为空时不覆盖 last-known-good 数据。

### 8.3 发布

- 未来生效 proposal 无法发布。
- 发布成功后同时出现 snapshot、proposal 状态变化和 pending outbox。
- 重复 Publish 不创建第二个 snapshot。
- dispatcher 重跑不产生第二次业务更新。

### 8.4 消费者对照测试

准备：

- 项目 A：`tier_provisional=true`；
- 项目 B：表单 frozen 或状态为 FILED。

发布 v2 后必须满足：

- A 调用 `recalc-tier`，更新档位并清除 provisional；
- A 收到 `tier_recalculated` 通知；
- B 只设置 `policy_stale=true` 并收到提醒；
- B 的 form hash、材料和 registration number 不变；
- 同一事件投递两次，通知和重算不重复。

### 8.5 唯一硬性端到端验收

1. v1 快照中金额阈值未公布。
2. 创建一个 provisional 项目和一个 frozen 项目。
3. 管理员在政策页手动触发政策抓取。
4. 系统识别 fixture 或真实来源变化并生成 proposal。
5. 政策页显示 Diff、impact 和 effective_from。
6. 管理员点击 Publish。
7. Firestore 出现 v2 和 pending outbox。
8. outbox 发出 `policy.updated` 并标记 sent。
9. provisional 项目完成重算并收到通知。
10. frozen 项目只显示政策过期提醒。
11. frozen form hash 和 registration number 不变。
12. 重放同一事件，数据不重复变化。

十二步全部通过，Richard 的政策回路 v1 才算完成。

## 9. 实现顺序与降级线

实现顺序：

1. 契约、seed 和 SnapshotService 握手；
2. fixture crawl → Diff → proposal；
3. 政策管理页；
4. publish transaction + outbox；
5. `policy.updated` 消费者和双项目测试；
6. 一个真实官方来源；
7. Cloud Run、Pub/Sub、Scheduler；
8. 联调、部署和演示数据。

若真实来源适配影响主线，降级为：保留真实页面抓取和 GCS 归档，但演示变化使用固定 fixture。不得砍掉发布、outbox、消费者、暂定项目重算和冻结数据不变测试。

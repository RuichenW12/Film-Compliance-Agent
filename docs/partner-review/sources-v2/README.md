# v2 政策源离线归档与 MOCK 清单

生成/复核日期：2026-08-26

对应快照：`policy/seed-snapshot-v2.yaml`

## 结论先行

这次归档不再只有三个短网页。现已保存：国家正式文件、57 页地方经营指南、当前政府办事页面和流程图，以及 3 份政府门户公开的真实 DOCX 表单。

但“来源是真实政府文件”不等于“产品映射已经审核通过”。当前快照继续保持：

- `published_by: mock_seed`
- `verification_status: mock_verified`
- p4/p5 `mapping_status: mock_pending_human_review`

《微短剧发展管理办法》自 2026-09-01 起施行；在此之前，v2 是供联调和人工复核的未来制度候选数据。

## 文件分区

- `authoritative/`：正式政策文件和政府办事指南/页面；
- `forms/`：政府门户可公开下载的真实示例/空白表；
- `reference-only/`：行业自律/团体标准线索，只作参考，不驱动门槛；
- `system-generated/`：需要登录备案系统后生成、公开站点没有空白下载的表；
- `raw/`、`text/`、`metadata/`：此前三个网页的原始抓取、正文和响应头；
- `snapshot/`：物化后的 v2 冻结副本和复核清单。

全部 URL、适用范围、状态、SHA-256 和风险说明见 `manifest.json`。

## 可直接打开的重点材料

| ID | 内容 | 用途 | 边界 |
|---|---|---|---|
| SRC-001 | 总局令第 16 号《微短剧发展管理办法》 | p1/p2/p4/p5/p6 国家规则 | 2026-09-01 生效 |
| SRC-004 | 广电发〔2022〕128 号正式 PDF | 历史制度和材料来源背景 | 不能覆盖 2026 新办法 |
| SRC-005 | 57 页《上海市松江区微短剧依法经营指引》 | p4/p5 字段和流程参考 | 含旧金额门槛，金额部分禁用 |
| SRC-006 | 上海规划备案办事页面 | 规划材料、系统生成表、办理流程 | 上海口径 |
| SRC-007 | 上海内容审查办事页面 | 完成片、字幕表、成本/合同等材料 | 上海口径 |
| SRC-008/009 | 北京办事页面和流程 PDF | 跨地区对照 | 北京口径，不直接驱动 runtime |
| SRC-010 | 广东规划备案问答 | 系统填报和剧本大纲补充说明 | 广东口径，不直接驱动 runtime |
| FORM-001/002 | 规划备案承诺书示例/空白 DOCX | 真实公开表单 | 上海门户模板 |
| FORM-003 | 成本配置比例情况报告空白 DOCX | 真实公开表单 | 上海门户模板 |

## p4/p5 如何进入 v2

- p4 保留 Maxine 已接入的 `T1_7steps`、`T2_5steps`、`T3_4steps` 三个模板名，步骤改为规划备案、完成片审核/许可、播出单位播前审核三条有来源的路径。
- p5 的完整参考字段来自 SRC-005；因其是地方指引且含旧门槛，新增字段放在 `reference_fields` 待影视伙伴确认，暂不加入会阻断 Gate 的 `required_facts`，旧金额不进入 p3。
- 国家层面明确要求的申请表、剧情梗概、许可证、样片、字幕表等由 SRC-001 第十四/十九条支持。
- 当前 asset contract 不为每种行政附件新建枚举，多份行政文件暂按 `supporting_document` 分组，具体清单保留在卡片 metadata 中。完成片、字幕表和行政附件已进入候选卡片，但在缺少阶段化 requiredness 前不阻断拍摄前 Gate。
- 新版《微短剧备案公示申请表》和在线报审表没有公开空白件，按 `external_system_generated` 记录，等待影视伙伴从实际系统导出。

## 仍需人工复核

1. 真人 300/100 万、AI 80/30 万的原始总局通知及边界；
2. SRC-005 的十四个字段在 2026-09-01 后新版系统中是否仍全部存在/必填；
3. 上海操作步骤能否作为演示默认，还是仅在选择上海辖区后展示；
4. 多份 `supporting_document` 后续是否需要拆成独立 asset kinds；
5. 实际登录系统生成的新版备案公示申请表、报审表和字段截图；
6. 人工签字后才可把整个 snapshot 晋升为 `human_verified`。

## 重跑方式

```bash
python scripts/materialize_policy_snapshot_v2.py
python scripts/materialize_policy_snapshot_v2.py --check
```

第一条校验快照语义、source ID 和所有归档文件哈希，然后刷新 `snapshot/seed-snapshot-v2.yaml`；第二条只检查，不写文件。

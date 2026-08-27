# Policy library

The deduplicated set of documents this product's policy claims rest on. One
place to look, one manifest, no second copies.

Everything here is a real document from an official source. What is *derived*
from them — the snapshot packs — lives in `policy/` and is still marked mock
until a human confirms each mapping.

## Layout

| Folder | What is in it | How far it can be trusted |
|---|---|---|
| `primary/` | 官方原文：总局令、总局办公厅通知、部门规章 | 一手来源 |
| `text/` | 从 PDF 提取的纯文本，便于检索比对 | 派生物，法律核验请回看 PDF |

转述页、省市办事指南和空白表格**没有再复制一份**。它们已经在
`docs/partner-review/sources-v2/` 里，`manifest.json` 直接登记那边的路径。
清单是统一入口，不是第二份拷贝。

`manifest.json` lists every document with its SHA-256 and where it is stored,
and records what was deliberately **not** copied and why.

## What is here

**Primary (5)** — 总局令第16号《微短剧发展管理办法》· 广电办发〔2024〕35号 ·
广电办发〔2022〕128号 · 总局令第63号《电视剧内容管理规定》·
《网络短视频内容审核标准细则（2021）》

**Republication (2)** — 分类分层门槛（宝鸡转述）· AI 门槛（西藏转述）.
**These two carry the numbers the product actually uses**, and both are second
hand. That is the largest open risk in the policy data.

**Operational (6)** — 松江依法经营指引（57页，最完整的一份）· 上海规划备案 ·
上海成片审查 · 北京备案 · 北京流程图 · 广东问答

**Forms (3)** — 规划备案承诺书（示例 + 空白）· 成本配置比例情况报告（空白）

## Relationship to `docs/partner-review/sources-v2/`

That directory is the **frozen evidence archive for snapshot v2**: it has its own
manifest, its own hashes, and tests that verify them
(`tests/policy/test_snapshot_materialization.py`). It records what v2 was built
from, at the time it was built. It does not change.

This library is the **working set going forward**. Where a document exists in
both, the library keeps the better copy and the manifest says which one was
skipped and why. Two examples:

- 广电办发〔2022〕128号 exists in both. The archive's copy is a **scan with no
  text layer**; the copy here has one, so this is the searchable version. The
  scan is kept over there because it carries a 北京市广电局 收文 stamp, which is
  evidence of real circulation.
- 总局令第16号 exists as a scraped web page over there and as the **official PDF**
  here. The PDF is the stronger evidence.

## Reading order, if you are new to this

1. [`MISSING.md`](MISSING.md) — what is still needed, and why it matters
2. `text/P-002-nrta-2024-35.txt` — the clearest statement of how tiers work
3. `operational/O-001-songjiang-guide.pdf` — the most practical document in the
   set; 57 pages of Q&A covering the whole lifecycle
4. `republication/R-001-live-action-thresholds.txt` — the numbers the product
   uses today, and the reason `MISSING.md` starts where it does

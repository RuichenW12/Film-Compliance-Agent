# 影视伙伴政策数据复核材料包 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从当前 mock-verified policy snapshot v2 生成一份可直接发送的中文 PDF 说明和可填写 Excel 确认表。

**Architecture:** 两个独立生成器读取同一份 `policy/seed-snapshot-v2.yaml` 和已确认设计。JavaScript 生成器使用 `@oai/artifact-tool` 创建、校验和渲染 Excel；Python 生成器使用 ReportLab 创建 PDF。最终文件写入 `docs/partner-review/`，中间渲染图写入 `tmp/partner-review/`，不进入交付包。

**Tech Stack:** YAML, JavaScript, `@oai/artifact-tool`, Python, ReportLab, Poppler

---

### Task 1: 建立 Excel 生成器和五张工作表

**Files:**
- Create: `scripts/build_partner_review_workbook.mjs`
- Create: `docs/partner-review/影视伙伴政策数据确认表-v1.xlsx`

- [ ] **Step 1: 读取真实输入并构造可追溯行**

生成器读取 `policy/seed-snapshot-v2.yaml`，为以下内容生成稳定条目 ID：

```text
p1-definition
SR-001..SR-009
p3-live-action, p3-ai-generated
T1_7steps:1..7, T2_5steps:1..5, T3_4steps:1..4
p5-fact:title..applicant_entity
mat_synopsis..mat_subtitle_sheet
p6 clause_id
```

每一行携带 pack、优先级、当前候选值和候选来源；人工字段初始为
`待确认` 或空值，不写入任何人工结论。

- [ ] **Step 2: 创建工作簿结构**

创建以下工作表：

```javascript
const workbook = Workbook.create();
for (const name of [
  "填写说明",
  "规则确认_p1-p3",
  "流程材料_p4-p5",
  "条款来源_p6",
  "复核汇总",
]) workbook.worksheets.add(name);
```

通用确认表列为：

```text
优先级 | Pack | 条目ID | 复核主题 | 当前候选值 | 确认状态 |
建议修改值 | 适用地区 | 项目类型 | effective_from | 依据类型 |
来源链接或附件名 | 复核人 | 备注与边界案例
```

- [ ] **Step 3: 增加编辑约束和汇总公式**

确认状态使用列表验证：

```javascript
statusRange.dataValidation = {
  rule: { type: "list", values: ["待确认", "已确认", "需修改", "无法确认"] },
};
```

汇总表分别引用三张确认表的状态列，使用有界 `COUNTIF` 公式统计四种状态；
合计等于三张明细表的实际复核条目数量。

- [ ] **Step 4: 应用专业且可编辑的格式**

使用深蓝标题、蓝灰只读区、浅黄色回填区；冻结表头、隐藏网格线、设置筛选，
并按数据类型设置日期和人民币格式。长文本先扩宽再换行，避免超过可读行高。

- [ ] **Step 5: 导出、结构检查和公式错误扫描**

运行：

```bash
NODE_PATH=/Users/ruichenwang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules \
/Users/ruichenwang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
scripts/build_partner_review_workbook.mjs
```

生成器必须使用 `workbook.inspect` 检查五张工作表和关键范围，并扫描
`#REF!|#DIV/0!|#VALUE!|#NAME?|#N/A`。预期：五张表存在，错误扫描为空。

### Task 2: 渲染并视觉校验 Excel

**Files:**
- Create: `tmp/partner-review/xlsx-填写说明.png`
- Create: `tmp/partner-review/xlsx-规则确认.png`
- Create: `tmp/partner-review/xlsx-流程材料.png`
- Create: `tmp/partner-review/xlsx-条款来源.png`
- Create: `tmp/partner-review/xlsx-复核汇总.png`

- [ ] **Step 1: 渲染全部工作表**

生成器在最终导出前调用：

```javascript
await workbook.render({
  sheetName,
  autoCrop: "all",
  scale: 1,
  format: "png",
});
```

- [ ] **Step 2: 逐张检查视觉缺陷**

使用图像查看工具检查：标题、表头、候选金额、URL、黄色回填列、汇总数字均可见；
不存在裁切、重叠、默认空白页或不可读的深色正文。

- [ ] **Step 3: 修复后重新渲染**

仅调整出现问题的列宽、行高和换行范围，重新运行生成器并检查受影响工作表。

### Task 3: 生成 PDF 说明页

**Files:**
- Create: `scripts/build_partner_review_pdf.py`
- Create: `docs/partner-review/影视伙伴政策数据复核说明-v1.pdf`

- [ ] **Step 1: 创建一致的四页内容**

使用 ReportLab `SimpleDocTemplate` 和支持中文的系统字体，内容顺序固定为：

```text
第1页：目的、范围、mock_verified 警示
第2页：P0 流程、表单和材料
第3页：P1 九类特殊题材和真人/AI候选金额
第4页：P2 条款来源、回填方法、升级条件
```

页眉显示“影视伙伴政策数据复核”，页脚显示页码。首页和结尾使用醒目警示：
“联调候选数据，未经完整人工复核，不构成法律意见。”

- [ ] **Step 2: 运行生成器**

```bash
/Users/ruichenwang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
scripts/build_partner_review_pdf.py
```

预期：输出 PDF 存在，包含 4 页，无异常退出。

- [ ] **Step 3: 检查文本和页数**

使用 `pdfinfo` 确认 4 页，使用 `pdftotext` 检查标题、两组金额、九类题材、
`mock_verified` 和免责声明均存在。

### Task 4: 渲染、视觉验收和范围核对

**Files:**
- Create: `tmp/partner-review/pdf-page-1.png`
- Create: `tmp/partner-review/pdf-page-2.png`
- Create: `tmp/partner-review/pdf-page-3.png`
- Create: `tmp/partner-review/pdf-page-4.png`

- [ ] **Step 1: 渲染 PDF 全部页面**

```bash
pdftoppm -png -r 144 \
docs/partner-review/影视伙伴政策数据复核说明-v1.pdf \
tmp/partner-review/pdf-page
```

- [ ] **Step 2: 检查每一页**

确认无乱码、黑方块、内容裁切、孤立标题、表格跨页破损；页码与免责声明清晰。

- [ ] **Step 3: 核对 PDF 与 Excel 一致性**

检查两份文件对以下内容完全一致：

```text
P0/P1/P2 优先级
九类特殊题材
真人 T1 300万 / T2 100万
AI T1 80万 / T2 30万
所有项目初始待确认
整份 snapshot 保持 mock_verified
```

- [ ] **Step 4: 清理和提交范围**

只暂存两个最终文件、两个生成器和本计划；不暂存 `tmp/partner-review/`、
`.DS_Store` 或任何凭据。运行 `git diff --check` 后提交：

```bash
git commit -m "docs: add film partner policy review package"
```

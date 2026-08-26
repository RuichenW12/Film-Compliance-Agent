import { spawnSync } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const SNAPSHOT_PATH = path.join(ROOT, "policy", "seed-snapshot-v2.yaml");
const OUTPUT_DIR = path.join(ROOT, "docs", "partner-review");
const PREVIEW_DIR = path.join(ROOT, "tmp", "partner-review");
const OUTPUT_PATH = path.join(OUTPUT_DIR, "影视伙伴政策数据确认表-v1.xlsx");
const REPO_PYTHON = "/Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/python";
const DISCLAIMER = "联调候选数据，未经完整人工复核，不构成法律意见。";
const STATUSES = ["待确认", "已确认", "需修改", "无法确认"];
const CATEGORY_LABELS = {
  political: "政治",
  military: "军事",
  diplomatic: "外交",
  national_security: "国家安全",
  united_front: "统战",
  ethnic: "民族",
  religious: "宗教",
  judicial: "司法",
  public_security: "公安",
};
const STEP_LABELS = {
  "roadmap.step.confirm_classification": "确认分类结果",
  "roadmap.step.materials": "准备并核对材料",
  "roadmap.step.script_precheck": "运行剧本预检",
  "roadmap.step.resolve_coreview": "处理协审事项",
  "roadmap.step.freeze_form": "确认并冻结备案表",
  "roadmap.step.authority_review": "机构或主管部门审核",
  "roadmap.step.record_filing": "记录备案结果",
  "roadmap.step.self_check": "完成自查与剧本预检",
  "roadmap.step.institution_review": "机构审核",
};
const OWNER_LABELS = {
  creator: "创作者（creator）",
  system: "系统（system）",
  institution: "机构（institution）",
};
const FACT_LABELS = {
  title: "片名（title）",
  episode_count: "集数（episode_count）",
  episode_minutes: "单集时长（episode_minutes）",
  investment_amount_rmb: "实际投资金额（investment_amount_rmb）",
  applicant_entity: "申报主体（applicant_entity）",
};
const MATERIAL_LABELS = {
  "material.synopsis": "剧本梗概（synopsis）",
  "material.script": "剧本（script）",
  "material.supporting_document": "佐证材料（supporting_document）",
  "material.prompts": "生成提示词（prompts）",
  "material.subtitle_sheet": "字幕表（subtitle_sheet）",
};
const ASSET_KIND_LABELS = {
  synopsis: "剧本梗概（synopsis）",
  script: "剧本（script）",
  supporting_document: "佐证材料（supporting_document）",
  prompts: "生成提示词（prompts）",
  subtitle_sheet: "字幕表（subtitle_sheet）",
};

const COLORS = {
  navy: "#17365D",
  blue: "#2F75B5",
  paleBlue: "#D9EAF7",
  gray: "#E7E6E6",
  paleYellow: "#FFF2CC",
  paleRed: "#FCE4D6",
  paleGreen: "#E2F0D9",
  border: "#B4C7DC",
  white: "#FFFFFF",
  text: "#1F2937",
};


function loadSnapshot() {
  const code = [
    "import json,sys,yaml",
    "with open(sys.argv[1], encoding='utf-8') as stream:",
    " print(json.dumps(yaml.safe_load(stream), ensure_ascii=False))",
  ].join("\n");
  const result = spawnSync(REPO_PYTHON, ["-c", code, SNAPSHOT_PATH], {
    encoding: "utf8",
  });
  if (result.status !== 0) {
    throw new Error(`snapshot parse failed: ${result.stderr}`);
  }
  return JSON.parse(result.stdout);
}


function clauseMap(snapshot) {
  return new Map(
    snapshot.packs.p6_legal_clauses.clauses.map((clause) => [
      clause.clause_id,
      clause,
    ]),
  );
}


function sourceFor(clauses, clauseId) {
  return clauses.get(clauseId)?.source_url ?? "";
}


function buildRuleRows(snapshot) {
  const packs = snapshot.packs;
  const clauses = clauseMap(snapshot);
  const p1 = packs.p1_form_definition;
  const p2 = packs.p2_subject_rules;
  const p3 = packs.p3_tier_thresholds;
  const rows = [
    [
      "P2",
      "p1_form_definition",
      "p1-definition",
      "微短剧定义",
      `单集时长严格少于${p1.episode_max_minutes_exclusive}分钟；主题主线明确、故事情节连续完整、人物角色突出`,
      null,
      null,
      "待确认",
      "",
      "中国境内",
      "微短剧",
      new Date(snapshot.effective_from),
      "政府文件候选",
      sourceFor(clauses, p1.clause_ref),
      "",
      "请确认原文、适用范围、管辖范围及生效时间",
    ],
  ];

  for (const rule of p2.subject_rules) {
    rows.push([
      "P1",
      "p2_subject_rules",
      rule.rule_id,
      `特殊题材：${CATEGORY_LABELS[rule.category]}（${rule.category}）`,
      `字面触发“${rule.trigger_patterns.join("、")}”；当前联调结果为T1并需协审；expert_pending=${rule.expert_pending}`,
      null,
      null,
      "待确认",
      "",
      "中国境内",
      "微短剧",
      new Date(snapshot.effective_from),
      "影视伙伴严格口径 + 政府文件候选",
      sourceFor(clauses, rule.clause_ref),
      "",
      "请补充真实触发口径、边界案例及是否必然协审",
    ]);
  }

  const labels = { live_action: "真人微短剧", ai_generated: "AI生成微短剧" };
  for (const [mode, thresholds] of Object.entries(p3.threshold_sets)) {
    rows.push([
      "P1",
      "p3_tier_thresholds",
      `p3-${mode.replaceAll("_", "-")}`,
      `${labels[mode]}金额门槛`,
      `T1≥${thresholds.T1_min_rmb / 10000}万元；T2≥${thresholds.T2_min_rmb / 10000}万元；其余为T3`,
      thresholds.T1_min_rmb,
      thresholds.T2_min_rmb,
      "待确认",
      "",
      "中国境内",
      labels[mode],
      new Date(thresholds.effective_from),
      "政府办事信息候选",
      sourceFor(clauses, thresholds.clause_ref),
      "",
      "请确认金额口径、等于边界时的档位、适用地区和生效时间",
    ]);
  }
  return rows;
}


function buildFlowRows(snapshot) {
  const packs = snapshot.packs;
  const rows = [];
  const p4 = packs.p4_process_templates.templates;
  for (const [template, definition] of Object.entries(p4)) {
    definition.steps.forEach((step, index) => {
      rows.push([
        "P0",
        "p4_process_templates",
        `${template}:${index + 1}`,
        "流程步骤",
        `${template} 第${index + 1}步：${STEP_LABELS[step.name]}（${step.name}）`,
        index + 1,
        OWNER_LABELS[step.owner],
        "",
        "",
        "待确认",
        "",
        "中国境内",
        template.slice(0, 2),
        null,
        "影视伙伴实际操作口径",
        "",
        "",
        `关联材料：${(step.material_refs ?? []).join("、") || "无"}；请确认顺序、责任人、必要性和时限`,
      ]);
    });
  }

  for (const fact of packs.p5_form_templates.required_facts) {
    rows.push([
      "P0",
      "p5_form_templates",
      `p5-fact:${fact}`,
      "备案字段",
      FACT_LABELS[fact],
      null,
      OWNER_LABELS.creator,
      "是",
      "",
      "待确认",
      "",
      "中国境内",
      "T1/T2/T3",
      null,
      "真实表格或办事指南待提供",
      "",
      "",
      "请提供实际中文字段名、是否必填及表格模板",
    ]);
  }

  for (const card of packs.p5_form_templates.material_cards) {
    rows.push([
      "P0",
      "p5_form_templates",
      card.material_id,
      "材料清单",
      MATERIAL_LABELS[card.name_key],
      null,
      OWNER_LABELS.creator,
      card.required ? "是" : "否",
      ASSET_KIND_LABELS[card.asset_kind],
      "待确认",
      "",
      "中国境内",
      "T1/T2/T3",
      null,
      "真实材料清单或模板待提供",
      "",
      "",
      "请确认材料名称、必要性、适用档位、文件类型及模板",
    ]);
  }
  return rows;
}


function buildClauseRows(snapshot) {
  return snapshot.packs.p6_legal_clauses.clauses.map((clause) => [
    "P2",
    "p6_legal_clauses",
    clause.clause_id,
    clause.title,
    clause.text,
    new Date(snapshot.effective_from),
    "待确认",
    "",
    "中国境内",
    "微短剧",
    clause.clause_id.startsWith("nrta-") ? "政府文件候选" : "政府办事信息候选",
    clause.source_url,
    "",
    "请确认原文、链接有效性、适用范围、生效时间和规则映射",
  ]);
}


function setWidths(sheet, widths, lastRow) {
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, lastRow, 1).format.columnWidth = width;
  });
}


function styleTitle(sheet, lastColumn, subtitle) {
  sheet.showGridLines = false;
  const title = sheet.getRange(`A1:${lastColumn}1`);
  title.merge();
  title.values = [["影视伙伴政策数据确认表"]];
  title.format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white, size: 18 },
    rowHeight: 30,
    verticalAlignment: "center",
  };
  const note = sheet.getRange(`A2:${lastColumn}2`);
  note.merge();
  note.values = [[subtitle]];
  note.format = {
    fill: COLORS.paleRed,
    font: { bold: true, color: "#9C0006", size: 10 },
    wrapText: true,
    rowHeight: 28,
    verticalAlignment: "center",
  };
}


function styleDataSheet(sheet, headerRange, dataRange, editableColumns) {
  headerRange.format = {
    fill: COLORS.blue,
    font: { bold: true, color: COLORS.white, size: 10 },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: COLORS.border },
    rowHeight: 32,
  };
  dataRange.format = {
    font: { color: COLORS.text, size: 9 },
    wrapText: true,
    verticalAlignment: "top",
    borders: {
      insideHorizontal: { style: "thin", color: "#D9E2F3" },
      bottom: { style: "thin", color: COLORS.border },
    },
    rowHeight: 44,
  };
  editableColumns.forEach((range) => {
    range.format.fill = COLORS.paleYellow;
  });
  sheet.freezePanes.freezeRows(4);
}


function addTable(sheet, range, name) {
  const table = sheet.tables.add(range, true, name);
  table.style = "TableStyleMedium2";
  table.showFilterButton = true;
  return table;
}


function buildInstructions(sheet) {
  styleTitle(sheet, "H", DISCLAIMER);
  sheet.getRange("A4:H4").values = [[
    "项目",
    "说明",
    "项目",
    "说明",
    "项目",
    "说明",
    "项目",
    "说明",
  ]];
  sheet.getRange("A4:H4").format = {
    fill: COLORS.blue,
    font: { bold: true, color: COLORS.white },
    borders: { preset: "all", style: "thin", color: COLORS.border },
  };
  sheet.getRange("A5:H8").values = [
    ["当前状态", "mock_verified", "填写顺序", "先P0，再P1，最后P2", "待确认", "尚未完成人工判断", "已确认", "候选值准确且证据充分"],
    ["P0", "流程、字段、材料", "P1", "特殊题材、金额门槛", "需修改", "候选值不准确，请给出修改值", "无法确认", "当前复核人或材料不足"],
    ["证据要求", "填写链接或附件名", "时间要求", "填写effective_from", "边界案例", "写入备注列", "复核人", "填写真实姓名或团队角色"],
    ["交付方式", "回传此Excel及相关附件", "升级条件", "完整复核+证据+技术验证", "法律边界", "不构成法律意见", "禁止", "不要预先标记已确认"],
  ];
  sheet.getRange("A5:H8").format = {
    wrapText: true,
    verticalAlignment: "top",
    borders: { preset: "all", style: "thin", color: "#D9E2F3" },
    rowHeight: 42,
  };
  sheet.getRange("A10:H10").merge();
  sheet.getRange("A10:H10").values = [["填写示例"]];
  sheet.getRange("A10:H10").format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white },
  };
  sheet.getRange("A11:H12").values = [
    ["条目ID", "确认状态", "建议修改值", "适用地区", "effective_from", "依据类型", "来源", "备注"],
    ["示例条目", "需修改", "填写准确口径", "填写实际地区", new Date("2026-08-26T00:00:00+08:00"), "政府文件", "https://example.gov.cn/", "说明边界案例"],
  ];
  sheet.getRange("A11:H11").format = {
    fill: COLORS.blue,
    font: { bold: true, color: COLORS.white },
  };
  sheet.getRange("A12:H12").format = {
    fill: COLORS.paleYellow,
    wrapText: true,
    borders: { preset: "all", style: "thin", color: COLORS.border },
    rowHeight: 38,
  };
  sheet.getRange("E12").format.numberFormat = "yyyy-mm-dd";
  setWidths(sheet, [14, 18, 22, 18, 16, 22, 34, 34], 12);
}


function buildRulesSheet(sheet, rows) {
  const headers = [
    "优先级", "Pack", "条目ID", "复核主题", "当前候选值", "T1门槛（元）",
    "T2门槛（元）", "确认状态", "建议修改值", "适用地区", "项目类型",
    "effective_from", "依据类型", "来源链接或附件名", "复核人", "备注与边界案例",
  ];
  const endRow = 4 + rows.length;
  styleTitle(sheet, "P", DISCLAIMER);
  sheet.getRange("A4:P4").values = [headers];
  sheet.getRange(`A5:P${endRow}`).values = rows;
  styleDataSheet(
    sheet,
    sheet.getRange("A4:P4"),
    sheet.getRange(`A5:P${endRow}`),
    [sheet.getRange(`H5:L${endRow}`), sheet.getRange(`O5:P${endRow}`)],
  );
  sheet.getRange(`F5:G${endRow}`).format.numberFormat = "¥#,##0";
  sheet.getRange(`L5:L${endRow}`).format.numberFormat = "yyyy-mm-dd";
  sheet.getRange(`H5:H${endRow}`).dataValidation = {
    rule: { type: "list", values: STATUSES },
  };
  addTable(sheet, `A4:P${endRow}`, "RulesReviewTable");
  setWidths(sheet, [9, 22, 19, 20, 48, 15, 15, 12, 30, 16, 18, 16, 28, 48, 16, 48], endRow);
  return { statusRange: `H5:H${endRow}`, count: rows.length };
}


function buildFlowSheet(sheet, rows) {
  const headers = [
    "优先级", "Pack", "条目ID", "条目类型", "当前候选值", "步骤序号",
    "责任人", "是否必需", "asset_kind", "确认状态", "建议修改值", "适用地区",
    "项目类型", "effective_from", "依据类型", "来源链接或附件名", "复核人", "备注与边界案例",
  ];
  const endRow = 4 + rows.length;
  styleTitle(sheet, "R", DISCLAIMER);
  sheet.getRange("A4:R4").values = [headers];
  sheet.getRange(`A5:R${endRow}`).values = rows;
  styleDataSheet(
    sheet,
    sheet.getRange("A4:R4"),
    sheet.getRange(`A5:R${endRow}`),
    [sheet.getRange(`J5:N${endRow}`), sheet.getRange(`Q5:R${endRow}`)],
  );
  sheet.getRange(`N5:N${endRow}`).format.numberFormat = "yyyy-mm-dd";
  sheet.getRange(`J5:J${endRow}`).dataValidation = {
    rule: { type: "list", values: STATUSES },
  };
  addTable(sheet, `A4:R${endRow}`, "FlowMaterialsReviewTable");
  setWidths(sheet, [9, 22, 22, 14, 45, 10, 12, 12, 20, 12, 30, 16, 16, 16, 30, 42, 16, 50], endRow);
  return { statusRange: `J5:J${endRow}`, count: rows.length };
}


function buildClausesSheet(sheet, rows) {
  const headers = [
    "优先级", "Pack", "条款ID", "标题", "当前候选原文", "effective_from",
    "确认状态", "建议修改值", "适用地区", "项目类型", "依据类型",
    "来源URL或附件名", "复核人", "备注与规则映射",
  ];
  const endRow = 4 + rows.length;
  styleTitle(sheet, "N", DISCLAIMER);
  sheet.getRange("A4:N4").values = [headers];
  sheet.getRange(`A5:N${endRow}`).values = rows;
  styleDataSheet(
    sheet,
    sheet.getRange("A4:N4"),
    sheet.getRange(`A5:N${endRow}`),
    [sheet.getRange(`F5:J${endRow}`), sheet.getRange(`M5:N${endRow}`)],
  );
  sheet.getRange(`F5:F${endRow}`).format.numberFormat = "yyyy-mm-dd";
  sheet.getRange(`G5:G${endRow}`).dataValidation = {
    rule: { type: "list", values: STATUSES },
  };
  addTable(sheet, `A4:N${endRow}`, "ClauseReviewTable");
  setWidths(sheet, [9, 22, 26, 18, 72, 16, 12, 34, 16, 16, 24, 52, 16, 48], endRow);
  return { statusRange: `G5:G${endRow}`, count: rows.length };
}


function buildSummary(sheet, refs) {
  styleTitle(sheet, "F", DISCLAIMER);
  sheet.getRange("A4:F4").values = [["确认状态", "条目数", "占比", "含义", "下一步", "责任" ]];
  sheet.getRange("A5:A8").values = STATUSES.map((status) => [status]);
  for (let index = 0; index < STATUSES.length; index += 1) {
    const row = 5 + index;
    const formula = refs
      .map((ref) => `COUNTIF('${ref.sheet}'!$${ref.statusColumn}$5:$${ref.statusColumn}$${ref.endRow},A${row})`)
      .join("+");
    sheet.getRange(`B${row}`).formulas = [[`=${formula}`]];
    sheet.getRange(`C${row}`).formulas = [[`=B${row}/$B$10`]];
  }
  sheet.getRange("D5:F8").values = [
    ["尚未完成人工判断", "分配复核人并补证据", "Richard / 影视伙伴"],
    ["候选值准确且有依据", "保留证据，等待整体验收", "影视伙伴"],
    ["候选值需要调整", "填写修改值、依据和生效时间", "影视伙伴"],
    ["当前材料不足", "补充官方文件或升级复核人", "Richard / 影视伙伴"],
  ];
  sheet.getRange("A10").values = [["全部条目"]];
  sheet.getRange("B10").formulas = [["=SUM(B5:B8)"]];
  sheet.getRange("A11").values = [["预期条目"]];
  sheet.getRange("B11").values = [[refs.reduce((sum, ref) => sum + ref.count, 0)]];
  sheet.getRange("A12").values = [["一致性检查"]];
  sheet.getRange("B12").formulas = [["=IF(B10=B11,\"通过\",\"请检查\")"]];
  sheet.getRange("A4:F4").format = {
    fill: COLORS.blue,
    font: { bold: true, color: COLORS.white },
    borders: { preset: "all", style: "thin", color: COLORS.border },
  };
  sheet.getRange("A5:F8").format = {
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#D9E2F3" },
    rowHeight: 36,
  };
  sheet.getRange("C5:C8").format.numberFormat = "0.0%";
  sheet.getRange("A10:B12").format = {
    fill: COLORS.paleBlue,
    font: { bold: true },
    borders: { preset: "all", style: "thin", color: COLORS.border },
  };
  sheet.getRange("B12").conditionalFormats.add("containsText", {
    text: "通过",
    format: { fill: COLORS.paleGreen, font: { bold: true, color: "#006100" } },
  });
  setWidths(sheet, [16, 14, 14, 32, 42, 24], 12);
}


async function savePreview(workbook, sheetName, fileName) {
  const preview = await workbook.render({
    sheetName,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  const bytes = new Uint8Array(await preview.arrayBuffer());
  await fs.writeFile(path.join(PREVIEW_DIR, fileName), bytes);
}


async function main() {
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  await fs.mkdir(PREVIEW_DIR, { recursive: true });
  const snapshot = loadSnapshot();
  if (snapshot.verification_status !== "mock_verified") {
    throw new Error("partner package must start from mock_verified snapshot v2");
  }

  const workbook = Workbook.create();
  const instructions = workbook.worksheets.add("填写说明");
  const rules = workbook.worksheets.add("规则确认_p1-p3");
  const flow = workbook.worksheets.add("流程材料_p4-p5");
  const clauses = workbook.worksheets.add("条款来源_p6");
  const summary = workbook.worksheets.add("复核汇总");

  buildInstructions(instructions);
  const ruleMeta = buildRulesSheet(rules, buildRuleRows(snapshot));
  const flowMeta = buildFlowSheet(flow, buildFlowRows(snapshot));
  const clauseMeta = buildClausesSheet(clauses, buildClauseRows(snapshot));
  buildSummary(summary, [
    { sheet: "规则确认_p1-p3", statusColumn: "H", endRow: 4 + ruleMeta.count, count: ruleMeta.count },
    { sheet: "流程材料_p4-p5", statusColumn: "J", endRow: 4 + flowMeta.count, count: flowMeta.count },
    { sheet: "条款来源_p6", statusColumn: "G", endRow: 4 + clauseMeta.count, count: clauseMeta.count },
  ]);

  const sheetInspection = await workbook.inspect({
    kind: "sheet",
    include: "id,name",
    maxChars: 3000,
  });
  const summaryInspection = await workbook.inspect({
    kind: "table",
    sheetId: "复核汇总",
    range: "A4:F12",
    include: "values,formulas",
    tableMaxRows: 12,
    tableMaxCols: 6,
    maxChars: 5000,
  });
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 100 },
    summary: "final formula error scan",
    maxChars: 3000,
  });
  console.log(sheetInspection.ndjson);
  console.log(summaryInspection.ndjson);
  console.log(errors.ndjson);

  await savePreview(workbook, "填写说明", "xlsx-填写说明.png");
  await savePreview(workbook, "规则确认_p1-p3", "xlsx-规则确认.png");
  await savePreview(workbook, "流程材料_p4-p5", "xlsx-流程材料.png");
  await savePreview(workbook, "条款来源_p6", "xlsx-条款来源.png");
  await savePreview(workbook, "复核汇总", "xlsx-复核汇总.png");

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(OUTPUT_PATH);
  console.log(JSON.stringify({
    output: OUTPUT_PATH,
    rows: {
      rules: ruleMeta.count,
      flow_materials: flowMeta.count,
      clauses: clauseMeta.count,
      total: ruleMeta.count + flowMeta.count + clauseMeta.count,
    },
  }));
}


await main();

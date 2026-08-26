"""Generate the sendable Chinese policy-data review brief."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "policy" / "seed-snapshot-v2.yaml"
OUTPUT_DIR = ROOT / "docs" / "partner-review"
OUTPUT_PATH = OUTPUT_DIR / "影视伙伴政策数据复核说明-v1.pdf"
REPO_PYTHON = Path(
    "/Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/python"
)
FONT_PATH = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
FONT_NAME = "PartnerSans"
DISCLAIMER = "联调候选数据，未经完整人工复核，不构成法律意见。"

NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#2F75B5")
PALE_BLUE = colors.HexColor("#D9EAF7")
PALE_YELLOW = colors.HexColor("#FFF2CC")
PALE_RED = colors.HexColor("#FCE4D6")
PALE_GREEN = colors.HexColor("#E2F0D9")
TEXT = colors.HexColor("#1F2937")
BORDER = colors.HexColor("#B4C7DC")

CATEGORY_LABELS = {
    "political": "政治",
    "military": "军事",
    "diplomatic": "外交",
    "national_security": "国家安全",
    "united_front": "统战",
    "ethnic": "民族",
    "religious": "宗教",
    "judicial": "司法",
    "public_security": "公安",
}

STEP_LABELS = {
    "roadmap.step.confirm_classification": "确认分类结果",
    "roadmap.step.materials": "准备并核对材料",
    "roadmap.step.script_precheck": "运行剧本预检",
    "roadmap.step.resolve_coreview": "处理协审事项",
    "roadmap.step.freeze_form": "确认并冻结备案表",
    "roadmap.step.authority_review": "机构或主管部门审核",
    "roadmap.step.record_filing": "记录备案结果",
    "roadmap.step.self_check": "完成自查与剧本预检",
    "roadmap.step.institution_review": "机构审核",
    "roadmap.step.prepare_planning_filing": "准备规划备案材料",
    "roadmap.step.planning_review": "规划备案审核",
    "roadmap.step.produce_final_film": "完成拍摄制作",
    "roadmap.step.submit_content_review": "提交内容审核",
    "roadmap.step.record_license": "记录发行许可证",
    "roadmap.step.record_approval": "记录批准文件",
    "roadmap.step.prepare_broadcast_materials": "准备播前审核材料",
    "roadmap.step.broadcaster_review": "播出单位播前审核",
    "roadmap.step.record_program_number": "记录节目编号",
}

OWNER_LABELS = {
    "creator": "创作者",
    "system": "系统",
    "institution": "机构",
}

FACT_LABELS = {
    "title": "片名",
    "episode_count": "集数",
    "episode_minutes": "单集时长",
    "investment_amount_rmb": "实际投资金额",
    "applicant_entity": "申报主体",
    "production_license_number": "制作经营许可证号",
    "intended_platform": "拟播平台",
    "story_source": "故事来源",
    "joint_production_entities": "联合制作机构",
    "subject_type": "题材类型",
    "content_summary": "内容概要",
    "ideological_connotation": "思想内涵",
    "contact_name": "联系人",
    "contact_phone": "联系电话",
}

MATERIAL_LABELS = {
    "material.synopsis": "剧本梗概",
    "material.script": "剧本",
    "material.supporting_document": "佐证材料",
    "material.prompts": "生成提示词",
    "material.subtitle_sheet": "字幕表",
    "material.final_film": "完成片",
}


def load_snapshot() -> dict:
    code = (
        "import json,sys,yaml\n"
        "with open(sys.argv[1], encoding='utf-8') as stream:\n"
        " print(json.dumps(yaml.safe_load(stream), ensure_ascii=False))"
    )
    result = subprocess.run(
        [str(REPO_PYTHON), "-c", code, str(SNAPSHOT_PATH)],
        check=True,
        capture_output=True,
        text=True,
    )
    snapshot = json.loads(result.stdout)
    if snapshot["verification_status"] != "mock_verified":
        raise ValueError("partner brief must start from mock_verified snapshot v2")
    return snapshot


pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))

BASE = getSampleStyleSheet()
TITLE = ParagraphStyle(
    "PartnerTitle",
    parent=BASE["Title"],
    fontName=FONT_NAME,
    fontSize=23,
    leading=31,
    textColor=NAVY,
    alignment=TA_LEFT,
    spaceAfter=7 * mm,
)
SUBTITLE = ParagraphStyle(
    "PartnerSubtitle",
    parent=BASE["Normal"],
    fontName=FONT_NAME,
    fontSize=11,
    leading=18,
    textColor=colors.HexColor("#51606F"),
    spaceAfter=5 * mm,
)
H1 = ParagraphStyle(
    "PartnerH1",
    parent=BASE["Heading1"],
    fontName=FONT_NAME,
    fontSize=16,
    leading=22,
    textColor=NAVY,
    spaceBefore=1 * mm,
    spaceAfter=3 * mm,
)
H2 = ParagraphStyle(
    "PartnerH2",
    parent=BASE["Heading2"],
    fontName=FONT_NAME,
    fontSize=11.5,
    leading=16,
    textColor=BLUE,
    spaceBefore=2 * mm,
    spaceAfter=1.5 * mm,
)
BODY = ParagraphStyle(
    "PartnerBody",
    parent=BASE["BodyText"],
    fontName=FONT_NAME,
    fontSize=9.5,
    leading=15,
    textColor=TEXT,
    wordWrap="CJK",
    spaceAfter=2 * mm,
)
SMALL = ParagraphStyle(
    "PartnerSmall",
    parent=BODY,
    fontSize=7.4,
    leading=10.2,
    spaceAfter=0,
)
TABLE_TEXT = ParagraphStyle(
    "PartnerTable",
    parent=BODY,
    fontSize=8.1,
    leading=11.5,
    spaceAfter=0,
)
TABLE_HEAD = ParagraphStyle(
    "PartnerTableHead",
    parent=TABLE_TEXT,
    textColor=colors.white,
    alignment=TA_CENTER,
)
WARNING = ParagraphStyle(
    "PartnerWarning",
    parent=BODY,
    fontSize=10,
    leading=15,
    textColor=colors.HexColor("#9C0006"),
    alignment=TA_CENTER,
    spaceAfter=0,
)


def p(text: object, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(str(text), style)


def review_table(data: list[list[object]], widths: list[float]) -> Table:
    converted = []
    for row_index, row in enumerate(data):
        converted.append(
            [p(cell, TABLE_HEAD if row_index == 0 else TABLE_TEXT) for cell in row]
        )
    table = Table(converted, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PALE_BLUE, colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def callout(text: str, fill: colors.Color, style: ParagraphStyle = BODY) -> Table:
    table = Table([[p(text, style)]], colWidths=[177 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill),
                ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def page_frame(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(17 * mm, height - 15 * mm, width - 17 * mm, height - 15 * mm)
    canvas.setFont(FONT_NAME, 7.5)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(17 * mm, height - 11 * mm, "影视伙伴政策数据复核")
    canvas.drawRightString(
        width - 17 * mm,
        10 * mm,
        f"第 {doc.page} 页 / 共 4 页",
    )
    canvas.restoreState()


def build_page_one(snapshot: dict) -> list:
    story = [
        Spacer(1, 7 * mm),
        p("影视伙伴政策数据复核说明", TITLE),
        p("Policy Snapshot v2 - 国内微短剧联调数据人工确认包", SUBTITLE),
        callout(DISCLAIMER, PALE_RED, WARNING),
        Spacer(1, 6 * mm),
        p("本轮要解决什么", H1),
        p(
            "当前系统已能用完整 p1-p6 数据跑通分类、路线图、材料收集、剧本预检、D3 Gate 和表单冻结。但这些数据仍标记为 mock_verified：技术链路可用，不等于政策内容已经由影视专业人员确认。",
        ),
        p(
            "请影视伙伴只判断业务与政策事实，不需要阅读代码。每个条目请在 Excel 中选择“已确认、需修改、无法确认”之一，并尽量附上政府文件、办事指南、真实模板或行业操作依据。",
        ),
        p("复核优先级", H1),
        review_table(
            [
                ["优先级", "需要确认的内容", "为什么先看"],
                ["P0", "p4 办理流程；p5 表单字段与材料清单", "最依赖真实项目经验，直接决定流程能否落地"],
                ["P1", "p2 九类特殊题材；p3 真人/AI金额门槛", "直接影响T1/T2/T3分类和是否协审"],
                ["P2", "p1 微短剧定义；p6 条款原文、链接和映射", "用于确认适用范围和证据边界"],
            ],
            [22 * mm, 68 * mm, 87 * mm],
        ),
        Spacer(1, 5 * mm),
        p("希望收到的回复", H2),
        callout(
            "1. 回填后的 Excel；2. 引用的网页或附件；3. 适用地区与项目类型；4. 生效时间 effective_from；5. 无法确认时说明缺少什么材料或应由谁判断。",
            PALE_YELLOW,
        ),
        Spacer(1, 4 * mm),
        p(
            f"当前候选版本：{snapshot['version']}　当前状态：{snapshot['verification_status']}　候选生效时间：{snapshot['effective_from']}",
            SMALL,
        ),
    ]
    return story


def build_page_two(snapshot: dict) -> list:
    packs = snapshot["packs"]
    required_facts = packs["p5_form_templates"]["required_facts"]
    reference_fields = [
        field["field_id"]
        for field in packs["p5_form_templates"].get("reference_fields", [])
    ]
    displayed_facts = list(dict.fromkeys([*required_facts, *reference_fields]))
    story = [
        p("P0 - 请优先确认真实办理流程和材料", H1),
        p(
            "这一页不是在声称真实主管部门流程，而是把当前系统联调使用的候选步骤展开，请按实际办理经验逐项修订。",
        ),
    ]
    process_rows: list[list[object]] = [["档位", "当前候选步骤", "当前责任人"]]
    for template, definition in packs["p4_process_templates"]["templates"].items():
        process_rows.append(
            [
                template[:2],
                "；".join(
                    f"{index + 1}.{STEP_LABELS[step['name']]}"
                    for index, step in enumerate(definition["steps"])
                ),
                "；".join(
                    dict.fromkeys(OWNER_LABELS[step["owner"]] for step in definition["steps"])
                ),
            ]
        )
    story.extend(
        [
            review_table(process_rows, [19 * mm, 123 * mm, 35 * mm]),
            Spacer(1, 3 * mm),
            p("请确认：步骤顺序、责任人、必做/可选、协审条件、是否存在公开或经验时限。", SMALL),
            p("当前候选备案字段", H2),
            review_table(
                [
                    ["字段", "当前设定", "请提供"],
                    *[
                        [
                            FACT_LABELS[fact],
                            "联调必填" if fact in required_facts else "地方参考／待确认",
                            "真实中文字段名、是否必填、表格模板",
                        ]
                        for fact in displayed_facts
                    ],
                ],
                [48 * mm, 28 * mm, 101 * mm],
            ),
            Spacer(1, 3 * mm),
            p("当前候选材料清单", H2),
            review_table(
                [
                    ["材料", "当前设定", "请确认"],
                    *[
                        [
                            MATERIAL_LABELS[card["name_key"]],
                            "必需" if card["required"] else "可选",
                            f"真实名称、适用档位、模板及文件类型 {card['asset_kind']}",
                        ]
                        for card in packs["p5_form_templates"]["material_cards"]
                    ],
                ],
                [48 * mm, 28 * mm, 101 * mm],
            ),
            Spacer(1, 3 * mm),
            callout(
                "重点问题：AI 项目是否必须提交生成提示词？真人项目是否不需要？不同档位是否使用不同表格或材料？",
                PALE_YELLOW,
                SMALL,
            ),
        ]
    )
    return story


def build_page_three(snapshot: dict) -> list:
    packs = snapshot["packs"]
    subject_rows = [["类别", "当前候选触发", "当前候选结果"]]
    for rule in packs["p2_subject_rules"]["subject_rules"]:
        subject_rows.append(
            [
                f"{CATEGORY_LABELS[rule['category']]} ({rule['category']})",
                "、".join(rule["trigger_patterns"]),
                "T1 + 协审；仍待专家确认",
            ]
        )
    threshold_rows = [["项目类型", "T1候选门槛", "T2候选门槛", "候选生效时间"]]
    mode_labels = {"live_action": "真人微短剧", "ai_generated": "AI生成微短剧"}
    for mode, values in packs["p3_tier_thresholds"]["threshold_sets"].items():
        threshold_rows.append(
            [
                mode_labels[mode],
                f"{values['T1_min_rmb'] / 10000:g}万元",
                f"{values['T2_min_rmb'] / 10000:g}万元",
                values["effective_from"][:10],
            ]
        )
    return [
        p("P1 - 请确认分类规则", H1),
        p("九类特殊题材", H2),
        p(
            "当前实现严格保留影视伙伴此前提出的九类口径，只使用字面触发词，不自行扩展同义词。请确认是否“涉及即T1”、是否必然协审，以及真实边界案例。",
        ),
        review_table(subject_rows, [58 * mm, 43 * mm, 76 * mm]),
        Spacer(1, 4 * mm),
        p("真人与 AI 金额门槛", H2),
        review_table(threshold_rows, [52 * mm, 37 * mm, 37 * mm, 51 * mm]),
        Spacer(1, 3 * mm),
        callout(
            "请确认：金额是预算、实际投资还是申报金额；刚好等于门槛时归入哪档；是否全国统一；AI与真人是否确实分别计算。",
            PALE_YELLOW,
        ),
        Spacer(1, 5 * mm),
        callout(
            "系统可以得到 tier_provisional=false，但只表示输入和计算完整，不表示政策已经人工核验。分类结果仍必须同时显示 mock_verified。",
            PALE_BLUE,
        ),
    ]


def build_page_four(snapshot: dict) -> list:
    clauses = snapshot["packs"]["p6_legal_clauses"]["clauses"]
    clause_rows = [["条款ID", "当前候选内容", "候选来源"]]
    for index, clause in enumerate(clauses, start=1):
        clause_rows.append(
            [
                clause["clause_id"],
                f"{clause['title']}：{clause['text']}",
                f"S{index}",
            ]
        )
    source_lines = "<br/>".join(
        f"S{index}　{clause['source_url']}" for index, clause in enumerate(clauses, start=1)
    )
    return [
        p("P2 - 请确认定义、条款和来源", H1),
        p(
            "候选来源只用于帮助定位。请确认原文、链接有效性、适用地区、生效时间，以及每条业务规则是否真的由对应条款支持。行业经验不能直接包装成法律条文。",
        ),
        review_table(clause_rows, [48 * mm, 105 * mm, 24 * mm]),
        Spacer(1, 3 * mm),
        p("候选来源索引", H2),
        callout(source_lines, PALE_BLUE, SMALL),
        Spacer(1, 4 * mm),
        p("Excel 回填方法", H2),
        review_table(
            [
                ["状态", "何时使用", "必须补充"],
                ["已确认", "候选值准确且依据充分", "复核人、依据、适用范围、生效时间"],
                ["需修改", "候选值不准确或不完整", "建议修改值、依据、边界案例"],
                ["无法确认", "当前材料或权限不足", "缺少什么、建议找谁确认"],
            ],
            [28 * mm, 68 * mm, 81 * mm],
        ),
        Spacer(1, 4 * mm),
        p("升级条件", H2),
        callout(
            "全部条目完成复核并留存证据；所有 mock 内容被确认或替换；同一套 Python、前端和集成验证保持通过；最后由人工复核人明确授权整份 snapshot 升级。任何单项确认都不会自动把状态改成 human_verified。",
            PALE_GREEN,
        ),
        Spacer(1, 5 * mm),
        callout(DISCLAIMER, PALE_RED, WARNING),
    ]


def build_pdf() -> None:
    snapshot = load_snapshot()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=A4,
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=20 * mm,
        bottomMargin=16 * mm,
        title="影视伙伴政策数据复核说明-v1",
        author="Richard",
        subject="Policy Snapshot v2 人工复核材料",
    )
    story = []
    for page_index, page_content in enumerate(
        [
            build_page_one(snapshot),
            build_page_two(snapshot),
            build_page_three(snapshot),
            build_page_four(snapshot),
        ]
    ):
        story.extend(page_content)
        if page_index < 3:
            story.append(PageBreak())
    document.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    print(json.dumps({"output": str(OUTPUT_PATH)}, ensure_ascii=False))


if __name__ == "__main__":
    build_pdf()

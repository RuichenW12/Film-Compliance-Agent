# Complete Mock Policy Snapshot v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a complete, locally default, mock-verified v2 policy snapshot that drives the China domestic T1/T2/T3 workflow end to end without presenting integration data as human-reviewed policy.

**Architecture:** Add one conservative snapshot-wide verification status, validate cross-pack semantics at every file-load and publication boundary, and compose the unified local app from a complete v2 seed. Persist the selected status with classification, keep roadmap/form/material operations pinned to that snapshot, and expose one reusable non-dismissible UI banner. Preserve v1 as an explicit regression fixture and leave cloud bootstrap and Gate 5-b unchanged.

**Tech Stack:** Python 3.14, Pydantic v2, FastAPI, PyYAML, pytest, Next.js 16, React 19, TypeScript, Vitest, Testing Library.

---

## File map

| Responsibility | Files |
| --- | --- |
| Verification contract | `schemas/policy_snapshot.py`, `schemas/snapshot.py`, `schemas/project.py`, `schemas/__init__.py`, `workers/policy/adapters/repository_snapshot.py` |
| Cross-pack validation | `policy/validation.py`, `workers/policy/publish.py` |
| Complete integration data and local composition | `policy/seed-snapshot-v2.yaml`, `api/settings.py`, `api/deps/policy.py`, `api/main.py` |
| Material-kind enforcement | `schemas/enums.py`, `schemas/assets.py`, `core/materials.py`, `core/workflow_service.py` |
| API propagation | `core/classify/chain.py`, `core/workflow_service.py`, `api/routers/health.py`, `api/models/policy.py`, `api/routers/admin_policy.py` |
| UI visibility and matching assets | `web/components/policy-verification-banner.tsx`, `web/lib/api.ts`, `web/lib/policy-api.ts`, `web/app/wizard/page.tsx`, `web/app/dashboard/page.tsx`, `web/app/collection/page.tsx`, `web/components/policy/policy-admin-page.tsx`, locale files |
| Evidence and promotion checklist | `docs/policy-v2-human-review-checklist.md`, `docs/decisions.md`, `CHANGELOG.md` |

Use the repository virtual environment for Python checks:

```bash
PYTHON=/Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/python
```

Use this Node 26 workaround for Vitest:

```bash
NODE_OPTIONS=--localstorage-file=/tmp/codex-film-compliance-vitest-localstorage.json
```

### Task 1: Add the conservative verification contract

**Files:**
- Modify: `schemas/policy_snapshot.py`
- Modify: `schemas/snapshot.py`
- Modify: `schemas/project.py`
- Modify: `schemas/__init__.py`
- Modify: `workers/policy/adapters/repository_snapshot.py`
- Test: `tests/contract/test_policy_contract.py`
- Test: `tests/test_snapshot_service.py`
- Test: `tests/policy/test_repository_snapshot_service.py`

- [ ] **Step 1: Write failing contract and adapter tests**

Add these assertions before changing production code:

```python
from schemas.policy_snapshot import VerificationStatus


def test_snapshot_verification_defaults_to_mock() -> None:
    snapshot = PolicySnapshot.model_validate(snapshot_payload())
    assert snapshot.verification_status is VerificationStatus.MOCK_VERIFIED


def test_snapshot_can_be_explicitly_human_verified() -> None:
    snapshot = PolicySnapshot.model_validate(
        snapshot_payload(verification_status="human_verified")
    )
    assert snapshot.verification_status is VerificationStatus.HUMAN_VERIFIED
```

Extend the file-adapter acceptance test:

```python
def test_legacy_seed_is_conservatively_mock_verified(snapshots) -> None:
    assert snapshots.verification_status("v1") is VerificationStatus.MOCK_VERIFIED
```

Extend repository adapter coverage:

```python
def test_repository_exposes_snapshot_verification_status() -> None:
    repository, _ = seed_repository()
    service = RepositorySnapshotService(repository)
    assert service.verification_status("v1") is VerificationStatus.MOCK_VERIFIED
    with pytest.raises(SnapshotNotFoundError, match="v99"):
        service.verification_status("v99")
```

- [ ] **Step 2: Run the focused tests and observe RED**

Run:

```bash
$PYTHON -m pytest \
  tests/contract/test_policy_contract.py \
  tests/test_snapshot_service.py \
  tests/policy/test_repository_snapshot_service.py -q
```

Expected: collection/import failures because `VerificationStatus` and
`SnapshotService.verification_status()` do not exist.

- [ ] **Step 3: Implement the minimal shared contract**

In `schemas/policy_snapshot.py`:

```python
class VerificationStatus(StrEnum):
    MOCK_VERIFIED = "mock_verified"
    HUMAN_VERIFIED = "human_verified"


class PolicySnapshot(ContractModel):
    version: Version
    published_at: AwareDatetime
    effective_from: AwareDatetime
    published_by: str = Field(min_length=1)
    packs: PolicyPacks
    diff_from_prev: SnapshotDiff
    thresholds_published: bool
    verification_status: VerificationStatus = VerificationStatus.MOCK_VERIFIED
```

Add a concrete conservative method, not a new abstract method, so existing
test doubles remain source-compatible:

```python
class SnapshotService(ABC):
    def verification_status(self, version: str) -> VerificationStatus:
        _ = version
        return VerificationStatus.MOCK_VERIFIED
```

Override it in both real adapters:

```python
def verification_status(self, version: str) -> VerificationStatus:
    return self._snapshot(version).verification_status
```

Add the same conservative field to `Classification`:

```python
policy_verification_status: VerificationStatus = VerificationStatus.MOCK_VERIFIED
```

Export `VerificationStatus` from `schemas/__init__.py`.

- [ ] **Step 4: Run focused and schema regressions**

Run:

```bash
$PYTHON -m pytest \
  tests/contract/test_policy_contract.py \
  tests/test_snapshot_service.py \
  tests/policy/test_repository_snapshot_service.py \
  tests/test_classify.py -q
```

Expected: all selected tests pass and existing classifications deserialize as
mock-verified without fixture rewrites.

- [ ] **Step 5: Commit**

```bash
git add schemas/policy_snapshot.py schemas/snapshot.py schemas/project.py \
  schemas/__init__.py workers/policy/adapters/repository_snapshot.py \
  tests/contract/test_policy_contract.py tests/test_snapshot_service.py \
  tests/policy/test_repository_snapshot_service.py
git commit -m "feat: track policy snapshot verification status"
```

### Task 2: Add the complete v2 fixture and validate cross-pack semantics

**Files:**
- Create: `policy/seed-snapshot-v2.yaml`
- Create: `policy/validation.py`
- Create: `tests/test_policy_v2_seed.py`
- Create: `tests/policy/test_snapshot_validation.py`

- [ ] **Step 1: Write failing semantic-validator tests**

Load the exact integration fixture and mutate one concern per test:

```python
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from policy.validation import SnapshotSemanticError, validate_snapshot
from schemas.policy_snapshot import PackName, PolicySnapshot

V1 = Path(__file__).parents[2] / "policy" / "seed-snapshot-v1.yaml"
V2 = Path(__file__).parents[2] / "policy" / "seed-snapshot-v2.yaml"


def _payload() -> dict:
    return yaml.safe_load(V2.read_text(encoding="utf-8"))


def _validate(payload: dict) -> PolicySnapshot:
    return validate_snapshot(PolicySnapshot.model_validate(payload))


def test_complete_v2_passes_semantic_validation() -> None:
    snapshot = PolicySnapshot.model_validate(_payload())
    assert validate_snapshot(snapshot) is snapshot


def test_missing_clause_fails_closed() -> None:
    payload = _payload()
    payload["packs"]["p6_legal_clauses"]["clauses"] = []
    with pytest.raises(SnapshotSemanticError, match="missing clause"):
        _validate(payload)


def test_missing_material_fails_closed() -> None:
    payload = _payload()
    payload["packs"]["p4_process_templates"]["templates"]["T2_5steps"][
        "steps"
    ][0]["material_refs"].append("mat_unknown")
    with pytest.raises(SnapshotSemanticError, match="missing material"):
        _validate(payload)


def test_duplicate_material_id_fails_closed() -> None:
    payload = _payload()
    cards = payload["packs"]["p5_form_templates"]["material_cards"]
    cards.append(deepcopy(cards[0]))
    with pytest.raises(SnapshotSemanticError, match="duplicate material_id"):
        _validate(payload)


def test_missing_asset_kind_fails_closed() -> None:
    payload = _payload()
    del payload["packs"]["p5_form_templates"]["material_cards"][0]["asset_kind"]
    with pytest.raises(SnapshotSemanticError, match="asset_kind"):
        _validate(payload)


def test_unsupported_asset_kind_fails_closed() -> None:
    payload = _payload()
    payload["packs"]["p5_form_templates"]["material_cards"][0][
        "asset_kind"
    ] = "unknown_kind"
    with pytest.raises(SnapshotSemanticError, match="asset_kind"):
        _validate(payload)


def test_inverted_thresholds_fail_closed() -> None:
    payload = _payload()
    threshold = payload["packs"]["p3_tier_thresholds"]["threshold_sets"][
        "live_action"
    ]
    threshold["T1_min_rmb"] = threshold["T2_min_rmb"] - 1
    with pytest.raises(SnapshotSemanticError, match="T1_min_rmb"):
        _validate(payload)


def test_published_threshold_missing_boundary_fails_closed() -> None:
    payload = _payload()
    del payload["packs"]["p3_tier_thresholds"]["threshold_sets"][
        "live_action"
    ]["T2_min_rmb"]
    with pytest.raises(SnapshotSemanticError, match="T2_min_rmb"):
        _validate(payload)


def test_missing_roadmap_fails_closed() -> None:
    payload = _payload()
    del payload["packs"]["p4_process_templates"]["templates"]["T2_5steps"]
    with pytest.raises(SnapshotSemanticError, match="T2_5steps"):
        _validate(payload)


def test_missing_required_facts_fails_closed() -> None:
    payload = _payload()
    payload["packs"]["p5_form_templates"]["required_facts"] = []
    with pytest.raises(SnapshotSemanticError, match="required_facts"):
        _validate(payload)


def test_missing_required_material_fails_closed() -> None:
    payload = _payload()
    for card in payload["packs"]["p5_form_templates"]["material_cards"]:
        card["required"] = False
    with pytest.raises(SnapshotSemanticError, match="required material"):
        _validate(payload)


def test_v1_may_keep_empty_process_and_form_packs() -> None:
    payload = yaml.safe_load(V1.read_text(encoding="utf-8"))
    snapshot = PolicySnapshot.model_validate(payload)
    assert validate_snapshot(snapshot) is snapshot
```

- [ ] **Step 2: Run the new file and observe RED**

Run:

```bash
$PYTHON -m pytest tests/policy/test_snapshot_validation.py -q
```

Expected: import failure because `policy.validation` and the v2 fixture do not
exist.

- [ ] **Step 3: Create the exact complete v2 fixture**

Create `policy/seed-snapshot-v2.yaml` from the canonical YAML printed in Task 3
Step 3. Task 2 owns this file even though the long reference block is kept next
to the startup wiring for readability. Do not alter its amounts or legal
wording without updating the approved design.

- [ ] **Step 4: Implement a pure validator**

Create `policy/validation.py` with no repository or API dependencies:

```python
from __future__ import annotations

from schemas.policy_snapshot import PackName, PolicySnapshot


class SnapshotSemanticError(ValueError):
    pass


SUPPORTED_MATERIAL_ASSET_KINDS = {
    "synopsis",
    "script",
    "supporting_document",
    "prompts",
    "subtitle_sheet",
}


def _complete_version(version: str) -> bool:
    return int(version[1:]) >= 2


def validate_snapshot(snapshot: PolicySnapshot) -> PolicySnapshot:
    packs = snapshot.packs.model_dump(mode="python")
    clauses = {
        str(item["clause_id"])
        for item in packs[PackName.P6_LEGAL_CLAUSES.value].get("clauses", [])
        if item.get("clause_id")
    }
    cards = packs[PackName.P5_FORM_TEMPLATES.value].get("material_cards", []) or []
    card_ids = [str(card.get("material_id", "")) for card in cards]
    if len(card_ids) != len(set(card_ids)):
        raise SnapshotSemanticError("duplicate material_id")

    for card in cards:
        kind = card.get("asset_kind")
        if kind not in SUPPORTED_MATERIAL_ASSET_KINDS:
            raise SnapshotSemanticError("unsupported or missing asset_kind")

    referenced_clauses: list[str] = []
    p1 = packs[PackName.P1_FORM_DEFINITION.value]
    if p1.get("clause_ref"):
        referenced_clauses.append(str(p1["clause_ref"]))
    for rule in packs[PackName.P2_SUBJECT_RULES.value].get("subject_rules", []) or []:
        if rule.get("clause_ref"):
            referenced_clauses.append(str(rule["clause_ref"]))
    p3 = packs[PackName.P3_TIER_THRESHOLDS.value]
    for threshold_set in (p3.get("threshold_sets") or {}).values():
        if p3.get("thresholds_published"):
            missing_fields = {
                "T1_min_rmb",
                "T2_min_rmb",
                "clause_ref",
            } - set(threshold_set)
            if missing_fields:
                raise SnapshotSemanticError(
                    f"published threshold set missing: {sorted(missing_fields)}"
                )
        if threshold_set.get("clause_ref"):
            referenced_clauses.append(str(threshold_set["clause_ref"]))
        if int(threshold_set.get("T1_min_rmb", -1)) < int(
            threshold_set.get("T2_min_rmb", -1)
        ):
            raise SnapshotSemanticError("T1_min_rmb must be >= T2_min_rmb")
    for card in cards:
        if card.get("why_clause_id"):
            referenced_clauses.append(str(card["why_clause_id"]))
    missing = sorted(set(referenced_clauses) - clauses)
    if missing:
        raise SnapshotSemanticError(f"missing clause references: {missing}")

    templates = packs[PackName.P4_PROCESS_TEMPLATES.value].get("templates", {}) or {}
    for name, definition in templates.items():
        for step in definition.get("steps", []) or []:
            unknown = sorted(set(step.get("material_refs", []) or []) - set(card_ids))
            if unknown:
                raise SnapshotSemanticError(
                    f"{name} references missing material: {unknown}"
                )

    if _complete_version(snapshot.version):
        for required in ("T1_7steps", "T2_5steps", "T3_4steps"):
            if not (templates.get(required) or {}).get("steps"):
                raise SnapshotSemanticError(f"missing roadmap template: {required}")
        if not packs[PackName.P5_FORM_TEMPLATES.value].get("required_facts"):
            raise SnapshotSemanticError("v2 requires required_facts")
        if not any(card.get("required") for card in cards):
            raise SnapshotSemanticError("v2 requires at least one required material")
        if p3.get("thresholds_published") and not p3.get("threshold_sets"):
            raise SnapshotSemanticError("published thresholds require threshold_sets")
    return snapshot
```

Keep helper functions private; do not add a generic validation framework.

- [ ] **Step 5: Add fixture completeness tests and run both files**

In `tests/test_policy_v2_seed.py`, parse v2 through `PolicySnapshot` and assert:

```python
def test_v2_seed_is_complete_and_mock_verified() -> None:
    snapshot = PolicySnapshot.model_validate(
        yaml.safe_load(V2.read_text(encoding="utf-8"))
    )
    assert snapshot.version == "v2"
    assert snapshot.verification_status is VerificationStatus.MOCK_VERIFIED
    for name in PackName:
        assert getattr(snapshot.packs, name.value)


def test_v2_contains_all_runtime_templates_and_cards() -> None:
    snapshot = PolicySnapshot.model_validate(
        yaml.safe_load(V2.read_text(encoding="utf-8"))
    )
    p4 = snapshot.packs.p4_process_templates
    p5 = snapshot.packs.p5_form_templates
    assert set(p4["templates"]) == {"T1_7steps", "T2_5steps", "T3_4steps"}
    assert {card["asset_kind"] for card in p5["material_cards"]} == {
        "synopsis",
        "script",
        "supporting_document",
        "prompts",
        "subtitle_sheet",
    }
```

Run:

```bash
$PYTHON -m pytest tests/policy/test_snapshot_validation.py \
  tests/test_policy_v2_seed.py -q
```

Expected: all cases pass.

- [ ] **Step 6: Commit**

```bash
git add policy/seed-snapshot-v2.yaml policy/validation.py \
  tests/test_policy_v2_seed.py tests/policy/test_snapshot_validation.py
git commit -m "feat: add complete validated policy snapshot v2"
```

### Task 3: Validate file loads and make local startup use v2

**Files:**
- Modify: `schemas/snapshot.py`
- Modify: `api/settings.py`
- Modify: `api/deps/policy.py`
- Modify: `api/main.py`
- Modify: `tests/test_policy_v2_seed.py`
- Modify: `tests/policy/test_admin_routes.py`

- [ ] **Step 1: Write failing file-load/default tests**

```python
def test_file_service_loads_the_validated_v2_fixture() -> None:
    service = FileSnapshotService(V2)
    assert service.latest_version(as_of=NOW) == "v2"
    assert service.verification_status("v2") is VerificationStatus.MOCK_VERIFIED


def test_default_app_starts_from_v2() -> None:
    with TestClient(create_app()) as client:
        health = client.get("/healthz").json()
        assert health["snapshot_version"] == "v2"
```

- [ ] **Step 2: Run the tests and observe RED**

Run:

```bash
$PYTHON -m pytest tests/test_policy_v2_seed.py \
  tests/policy/test_admin_routes.py::test_default_app_builds_the_local_fixture_state -q
```

Expected: the default app still reports v1; the file-service test remains green
until semantic validation is wired.

- [ ] **Step 3: Use the exact fixture content from Task 2**

Task 2 creates `policy/seed-snapshot-v2.yaml` with this exact content:

```yaml
version: v2
published_at: "2026-08-26T00:05:00+08:00"
effective_from: "2026-08-26T00:00:00+08:00"
published_by: mock_seed
verification_status: mock_verified
packs:
  p1_form_definition:
    episode_max_minutes_exclusive: 20
    continuous_plot_required: true
    clause_ref: nrta-order-16-article-2
  p2_subject_rules:
    subject_rules:
      - {rule_id: SR-001, category: political, trigger_patterns: [政治], expert_pending: true, clause_ref: nrta-order-16-article-5}
      - {rule_id: SR-002, category: military, trigger_patterns: [军事], expert_pending: true, clause_ref: nrta-order-16-article-5}
      - {rule_id: SR-003, category: diplomatic, trigger_patterns: [外交], expert_pending: true, clause_ref: nrta-order-16-article-5}
      - {rule_id: SR-004, category: national_security, trigger_patterns: [国家安全], expert_pending: true, clause_ref: nrta-order-16-article-5}
      - {rule_id: SR-005, category: united_front, trigger_patterns: [统战], expert_pending: true, clause_ref: nrta-order-16-article-5}
      - {rule_id: SR-006, category: ethnic, trigger_patterns: [民族], expert_pending: true, clause_ref: nrta-order-16-article-5}
      - {rule_id: SR-007, category: religious, trigger_patterns: [宗教], expert_pending: true, clause_ref: nrta-order-16-article-5}
      - {rule_id: SR-008, category: judicial, trigger_patterns: [司法], expert_pending: true, clause_ref: nrta-order-16-article-5}
      - {rule_id: SR-009, category: public_security, trigger_patterns: [公安], expert_pending: true, clause_ref: nrta-order-16-article-5}
  p3_tier_thresholds:
    thresholds_published: true
    threshold_sets:
      live_action: {effective_from: "2026-01-01T00:00:00+08:00", T1_min_rmb: 3000000, T2_min_rmb: 1000000, clause_ref: tier-live-action-2026}
      ai_generated: {effective_from: "2026-07-01T00:00:00+08:00", T1_min_rmb: 800000, T2_min_rmb: 300000, clause_ref: tier-ai-generated-2026}
  p4_process_templates:
    templates:
      T1_7steps:
        steps:
          - {name: roadmap.step.confirm_classification, owner: creator}
          - {name: roadmap.step.materials, owner: creator, material_refs: [mat_synopsis, mat_script]}
          - {name: roadmap.step.script_precheck, owner: system}
          - {name: roadmap.step.resolve_coreview, owner: creator}
          - {name: roadmap.step.freeze_form, owner: creator}
          - {name: roadmap.step.authority_review, owner: institution}
          - {name: roadmap.step.record_filing, owner: institution}
      T2_5steps:
        steps:
          - {name: roadmap.step.materials, owner: creator, material_refs: [mat_synopsis, mat_script]}
          - {name: roadmap.step.self_check, owner: creator}
          - {name: roadmap.step.freeze_form, owner: creator}
          - {name: roadmap.step.institution_review, owner: institution}
          - {name: roadmap.step.record_filing, owner: institution}
      T3_4steps:
        steps:
          - {name: roadmap.step.materials, owner: creator, material_refs: [mat_synopsis, mat_script]}
          - {name: roadmap.step.freeze_form, owner: creator}
          - {name: roadmap.step.institution_review, owner: institution}
          - {name: roadmap.step.record_filing, owner: institution}
  p5_form_templates:
    required_facts: [title, episode_count, episode_minutes, investment_amount_rmb, applicant_entity]
    material_cards:
      - {material_id: mat_synopsis, name_key: material.synopsis, asset_kind: synopsis, required: true}
      - {material_id: mat_script, name_key: material.script, asset_kind: script, required: true}
      - {material_id: mat_supporting_document, name_key: material.supporting_document, asset_kind: supporting_document, required: false}
      - {material_id: mat_prompts, name_key: material.prompts, asset_kind: prompts, required: false}
      - {material_id: mat_subtitle_sheet, name_key: material.subtitle_sheet, asset_kind: subtitle_sheet, required: false}
  p6_legal_clauses:
    source_name: Mock-verified integration sources
    clauses:
      - {clause_id: nrta-order-16-article-2, title: 第二条, text: 本办法所称微短剧，是指单集时长少于二十分钟，主题主线明确、故事情节连续完整、人物角色突出的剧集。, source_url: "https://www.nrta.gov.cn/art/2026/7/31/art_113_73785.html"}
      - {clause_id: nrta-order-16-article-5, title: 第五条, text: 特殊题材类别与较大投资额度的一类微短剧定义。, source_url: "https://www.nrta.gov.cn/art/2026/7/31/art_113_73785.html"}
      - {clause_id: tier-live-action-2026, title: 真人微短剧联调门槛候选, text: 联调值：T1 300万元，T2 100万元。, source_url: "https://whhlyj.baoji.gov.cn/zzzb/xygl/202601/t20260115_1240723.html"}
      - {clause_id: tier-ai-generated-2026, title: AI微短剧联调门槛候选, text: 联调值：T1 80万元，T2 30万元。, source_url: "https://wxb.xzdw.gov.cn/wlcb/cbgz/202606/t20260626_680352.html"}
diff_from_prev:
  summary: Complete mock-verified v2 for domestic integration
  impact: [D1c, C1-a]
thresholds_published: true
```

- [ ] **Step 4: Wire validation and configurable local composition**

In `FileSnapshotService.__init__` call `validate_snapshot(snapshot)` before
storing it.

Change both defaults in `api/settings.py` to v2:

```python
snapshot_seed_path: str = "policy/seed-snapshot-v2.yaml"
# from_env fallback: policy/seed-snapshot-v2.yaml
```

Add an explicit seed path to the local policy builder:

```python
async def build_local_policy_api_state(
    blob_root: Path,
    *,
    seed_path: Path,
    clock: Callable[[], datetime] = utc_now,
) -> PolicyApiState:
```

Pass `seed_path` into `build_local_policy_loop`. In `create_app`, resolve one
`Settings.from_env()` value and pass `settings.snapshot_path` to both the
policy state and product context. Tests that exercise legacy policy publication
must pass the v1 path explicitly rather than relying on the default.

- [ ] **Step 5: Run seed/default regressions**

Run:

```bash
$PYTHON -m pytest tests/test_policy_v2_seed.py tests/test_snapshot_service.py \
  tests/policy/test_admin_routes.py -q
```

Expected: v2 is the default app snapshot; the explicit v1 fixture tests remain
v1 and pass.

- [ ] **Step 6: Commit**

```bash
git add schemas/snapshot.py api/settings.py \
  api/deps/policy.py api/main.py tests/test_policy_v2_seed.py \
  tests/policy/test_admin_routes.py
git commit -m "feat: default local policy to complete snapshot v2"
```

### Task 4: Reject semantically invalid publications

**Files:**
- Modify: `workers/policy/publish.py`
- Modify: `tests/policy/test_publish.py`
- Modify: `tests/policy/test_policy_loop.py`
- Modify: `tests/policy/test_admin_routes.py`
- Modify: `tests/test_app_policy_snapshot_bridge.py`

- [ ] **Step 1: Write the failing publication test**

```python
def test_publish_rejects_a_semantically_incomplete_v2() -> None:
    repository = InMemoryPolicyRepository()
    repository.put_snapshot(seed_snapshot_v1())
    proposal_id = repository.create_proposal(flag_only_proposal())

    with pytest.raises(PolicyPublishError) as raised:
        PolicyPublisher(repository).publish(proposal_id, "admin_richard", NOW)

    assert raised.value.code == "POLICY_PROPOSAL_INVALID"
    assert set(repository.list_snapshots()) == {"v1"}
```

Add a positive test seeded from complete v2; a p3-only proposal inherits the
other complete packs and publishes v3.

- [ ] **Step 2: Run focused RED**

Run:

```bash
$PYTHON -m pytest tests/policy/test_publish.py::test_publish_rejects_a_semantically_incomplete_v2 -q
```

Expected: FAIL because the publisher currently commits incomplete v2.

- [ ] **Step 3: Validate before building the event/outbox**

In `PolicyPublisher.publish`:

```python
try:
    validate_snapshot(snapshot)
except SnapshotSemanticError as exc:
    raise PolicyPublishError("POLICY_PROPOSAL_INVALID", str(exc)) from exc
```

Place this before `PolicyUpdatedEvent` and before `commit_publication`, so a
failure leaves proposal, snapshots, and outbox unchanged.

- [ ] **Step 4: Move publication-path fixtures to complete v2**

Where a test is about successful publication rather than legacy compatibility,
seed with `policy/seed-snapshot-v2.yaml` and expect `v3`,
`policy.updated:v3`, and the v3 idempotency key. Keep one explicit v1 negative
test proving an incomplete v2 cannot be published. Update the Gate 5-a bridge
test to publish v3 from complete v2 and assert the product reads v3 through the
same repository.

- [ ] **Step 5: Run publication and bridge suites**

Run:

```bash
$PYTHON -m pytest tests/policy/test_publish.py tests/policy/test_policy_loop.py \
  tests/policy/test_admin_routes.py tests/test_app_policy_snapshot_bridge.py -q
```

Expected: all pass; successful publications create v3 and the single incomplete
v2 case fails closed.

- [ ] **Step 6: Commit**

```bash
git add workers/policy/publish.py tests/policy/test_publish.py \
  tests/policy/test_policy_loop.py tests/policy/test_admin_routes.py \
  tests/test_app_policy_snapshot_bridge.py
git commit -m "feat: reject invalid policy publications"
```

### Task 5: Enforce one asset kind per material card

**Files:**
- Modify: `schemas/enums.py`
- Modify: `schemas/assets.py`
- Modify: `core/materials.py`
- Modify: `core/workflow_service.py`
- Modify: `tests/test_materials.py`
- Modify: `tests/test_guards.py`
- Modify: `tests/test_form_freeze.py`

- [ ] **Step 1: Write failing material-kind tests**

Update `CARD_PACK` so every card declares a kind, then add:

```python
def test_cards_expose_the_pack_asset_kind(client: TestClient) -> None:
    project_id = new_project(client)
    cards = client.get(
        f"/v1/projects/{project_id}/materials", headers=OWNER
    ).json()
    assert {card["material_id"]: card["asset_kind"] for card in cards} == {
        "mat_synopsis": "synopsis",
        "mat_id_scan": "supporting_document",
    }


def test_wrong_asset_kind_is_422_and_does_not_mutate_card(client: TestClient) -> None:
    project_id = new_project(client)
    script_version = upload_asset(client, project_id, "script", b"script")
    response = client.post(
        f"/v1/projects/{project_id}/materials/mat_synopsis/attach",
        json={"asset_version": script_version},
        headers=OWNER,
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"] == {
        "expected_kind": "synopsis",
        "actual_kind": "script",
    }
    card = client.get(
        f"/v1/projects/{project_id}/materials", headers=OWNER
    ).json()[0]
    assert card["status"] == "pending"
    assert card["asset_version"] is None
```

- [ ] **Step 2: Run focused RED**

Run:

```bash
$PYTHON -m pytest tests/test_materials.py -q
```

Expected: missing `asset_kind` in responses and wrong-kind attachment succeeds.

- [ ] **Step 3: Implement the narrow contract and guard**

```python
class AssetKind(StrEnum):
    SYNOPSIS = "synopsis"
    SCRIPT = "script"
    PROMPTS = "prompts"
    FINAL_FILM = "final_film"
    SUBTITLE_SHEET = "subtitle_sheet"
    SUPPORTING_DOCUMENT = "supporting_document"


class MaterialCard(DomainModel):
    material_id: str
    name_key: str
    asset_kind: AssetKind
    # existing fields unchanged
```

In `build_material_cards`, construct `asset_kind=AssetKind(raw["asset_kind"])`.
In `attach_material`, retrieve the asset once and reject before copying or
storing the card:

```python
asset = self._stores.assets.get(project_id, asset_version)
if asset is None:
    raise NotFoundError(
        f"asset version not found: {asset_version}",
        {"asset_version": asset_version},
    )
if asset.kind is not card.asset_kind:
    raise ValidationFailedError(
        "asset kind does not match material card",
        {
            "expected_kind": card.asset_kind.value,
            "actual_kind": asset.kind.value,
        },
    )
```

Update every direct `MaterialCard(...)` test fixture with its intended kind;
do not add a default that would hide old ambiguous cards.

- [ ] **Step 4: Run material/gate/form regressions**

Run:

```bash
$PYTHON -m pytest tests/test_materials.py tests/test_guards.py \
  tests/test_form_freeze.py tests/test_policy_v2_seed.py -q
```

Expected: all pass and the failed attachment is state-preserving.

- [ ] **Step 5: Commit**

```bash
git add schemas/enums.py schemas/assets.py core/materials.py \
  core/workflow_service.py tests/test_materials.py tests/test_guards.py \
  tests/test_form_freeze.py
git commit -m "feat: bind material cards to asset kinds"
```

### Task 6: Pin and expose verification status through API responses

**Files:**
- Modify: `core/classify/chain.py`
- Modify: `core/workflow_service.py`
- Modify: `api/routers/health.py`
- Modify: `api/models/policy.py`
- Modify: `api/routers/admin_policy.py`
- Modify: `tests/test_classify.py`
- Modify: `tests/test_tier_recalc.py`
- Modify: `tests/test_api_intake.py`
- Modify: `tests/policy/test_admin_routes.py`

- [ ] **Step 1: Write failing propagation tests**

```python
def test_classification_pins_mock_verification_status(v2_snapshots) -> None:
    outcome = classify(EXACT_LIVE_T2, CHANNELS, v2_snapshots)
    assert outcome.classification is not None
    assert outcome.classification.tier_provisional is False
    assert outcome.classification.policy_verification_status == "mock_verified"


def test_health_exposes_active_snapshot_verification(api_client) -> None:
    health = api_client.get("/healthz").json()
    assert health["snapshot_version"] == "v2"
    assert health["snapshot_verification_status"] == "mock_verified"
```

Extend admin snapshot expectations with
`"verification_status": "mock_verified"`, and extend the recalc test so moving
to v2 changes both the pinned version and pinned verification status.

- [ ] **Step 2: Run focused RED**

Run:

```bash
$PYTHON -m pytest tests/test_classify.py tests/test_tier_recalc.py \
  tests/test_api_intake.py tests/policy/test_admin_routes.py -q
```

Expected: status remains only the model default and is absent from health/admin.

- [ ] **Step 3: Set the status on every classification branch**

At the start of `classify`:

```python
version = snapshot_version or snapshots.latest_version()
verification_status = snapshots.verification_status(version)
```

Pass `policy_verification_status=verification_status` to every
`Classification(...)` constructor, including needs-human and exit outcomes.
In `recalc_tier`, add:

```python
"policy_verification_status": self._snapshots.verification_status(
    snapshot_version
),
```

to `classification_updates`.

- [ ] **Step 4: Expose the active/admin status**

Health:

```python
version = context.snapshots.latest_version()
return {
    "status": "ok",
    "snapshot_version": version,
    "snapshot_verification_status": context.snapshots.verification_status(version),
    # existing fields
}
```

Add `verification_status: VerificationStatus` to `SnapshotSummary` and populate
it from each repository snapshot in `list_snapshots`.

- [ ] **Step 5: Run focused and API regressions**

Run:

```bash
$PYTHON -m pytest tests/test_classify.py tests/test_tier_recalc.py \
  tests/test_api_intake.py tests/policy/test_admin_routes.py \
  tests/test_app_policy_snapshot_bridge.py -q
```

Expected: all pass and a final tier can simultaneously report mock verification.

- [ ] **Step 6: Commit**

```bash
git add core/classify/chain.py core/workflow_service.py api/routers/health.py \
  api/models/policy.py api/routers/admin_policy.py tests/test_classify.py \
  tests/test_tier_recalc.py tests/test_api_intake.py \
  tests/policy/test_admin_routes.py
git commit -m "feat: expose pinned policy verification"
```

### Task 7: Show the mock banner and attach only matching assets in the UI

**Files:**
- Create: `web/components/policy-verification-banner.tsx`
- Create: `web/lib/assets.ts`
- Create: `web/tests/policy-verification-banner.test.tsx`
- Create: `web/tests/assets.test.ts`
- Modify: `web/lib/api.ts`
- Modify: `web/lib/policy-api.ts`
- Modify: `web/app/wizard/page.tsx`
- Modify: `web/app/dashboard/page.tsx`
- Modify: `web/app/collection/page.tsx`
- Modify: `web/components/policy/policy-admin-page.tsx`
- Modify: `web/tests/wizard-page.test.tsx`
- Modify: `web/tests/policy-admin-page.test.tsx`
- Modify: `web/locales/en.json`
- Modify: `web/locales/zh.json`

- [ ] **Step 1: Write failing component and matching tests**

```tsx
it("renders a non-dismissible integration warning for mock policy", () => {
  render(<PolicyVerificationBanner status="mock_verified" />);
  expect(screen.getByRole("alert")).toHaveTextContent("integration data");
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it("renders nothing for human-verified policy", () => {
  const { container } = render(
    <PolicyVerificationBanner status="human_verified" />,
  );
  expect(container).toBeEmptyDOMElement();
});
```

```ts
it("selects the latest asset of the card kind", () => {
  expect(
    latestAssetOfKind(
      [
        { version_id: "script-1", kind: "script" },
        { version_id: "synopsis-1", kind: "synopsis" },
        { version_id: "script-2", kind: "script" },
      ],
      "synopsis",
    )?.version_id,
  ).toBe("synopsis-1");
});
```

Update Wizard and admin-page tests so mock responses must render the banner.

- [ ] **Step 2: Run UI RED**

Run:

```bash
cd web
NODE_OPTIONS=--localstorage-file=/tmp/codex-film-compliance-vitest-localstorage.json \
  npm test -- tests/policy-verification-banner.test.tsx tests/assets.test.ts \
  tests/wizard-page.test.tsx tests/policy-admin-page.test.tsx
```

Expected: missing component/helper and no banner in existing pages.

- [ ] **Step 3: Implement one reusable banner and typed statuses**

```tsx
export type PolicyVerificationStatus = "mock_verified" | "human_verified";

export function PolicyVerificationBanner({
  status,
}: {
  status: PolicyVerificationStatus | null | undefined;
}) {
  if (status !== "mock_verified") return null;
  return (
    <p className="alert warning-alert" role="alert">
      Integration data only. Not human-verified policy or legal advice.
    </p>
  );
}
```

Add corresponding Chinese and English locale strings rather than duplicating
page-specific copy. Add `policy_verification_status` to classification types,
`verification_status` to policy snapshot types, and `asset_kind` to
`MaterialCard`.

- [ ] **Step 4: Render the banner on all four surfaces**

- Wizard: use the returned classification status.
- Dashboard: use `project.classification.policy_verification_status`.
- Collection: fetch `/v1/projects/{id}` during `refresh` and retain its pinned
  classification status.
- Admin: render the banner when any active/listed snapshot is mock and add a
  Verification column for each row.

Add `supporting_document` to the upload kind list.

- [ ] **Step 5: Match attachments by card kind**

Create:

```ts
export function latestAssetOfKind<T extends { kind: string }>(
  assets: T[],
  kind: string,
): T | undefined {
  return assets.filter((asset) => asset.kind === kind).at(-1);
}
```

In each material row, use `latestAssetOfKind(assets, card.asset_kind)`, disable
attach when absent, and send only that version. Rename the button to “Attach
latest matching asset” through locales. Remove the global `latestScript` path.

- [ ] **Step 6: Run full frontend verification**

Run:

```bash
cd web
NODE_OPTIONS=--localstorage-file=/tmp/codex-film-compliance-vitest-localstorage.json npm test
npm run typecheck
npm run build
```

Expected: all frontend tests, typecheck, and production build pass.

- [ ] **Step 7: Commit**

```bash
git add web/components/policy-verification-banner.tsx web/lib/assets.ts \
  web/lib/api.ts web/lib/policy-api.ts web/app/wizard/page.tsx \
  web/app/dashboard/page.tsx web/app/collection/page.tsx \
  web/components/policy/policy-admin-page.tsx web/tests \
  web/locales/en.json web/locales/zh.json
git commit -m "feat: label mock policy throughout the UI"
```

### Task 8: Prove the default v2 end to end and add the human-review gate

**Files:**
- Create: `tests/test_default_v2_integration.py`
- Create: `docs/policy-v2-human-review-checklist.md`
- Modify: `docs/decisions.md`
- Modify: `CHANGELOG.md`
- Modify: `policy/README.md`

- [ ] **Step 1: Write the failing deterministic HTTP integration test**

The test must use `create_app()` with no live Gemini credentials:

```python
def upload(client, project_id: str, kind: str, content: bytes) -> str:
    ticket = client.post(
        f"/v1/projects/{project_id}/assets/upload-url",
        json={"kind": kind},
        headers=OWNER,
    ).json()
    response = client.put(ticket["upload_url"], content=content, headers=OWNER)
    assert response.status_code == 201
    return response.json()["version_id"]


def test_default_mock_v2_reaches_gate_and_frozen_form() -> None:
    with TestClient(create_app()) as client:
        health = client.get("/healthz").json()
        assert health["snapshot_version"] == "v2"
        assert health["snapshot_verification_status"] == "mock_verified"
        project_id = client.post(
            "/v1/projects",
            json={"title_working": "联调项目"},
            headers=OWNER,
        ).json()["project_id"]
        client.post(
            f"/v1/projects/{project_id}/intent",
            json={
                "form_type_claimed": "micro_drama",
                "genre_keywords": ["都市"],
                "logline": "两位创业者共同完成一部作品。",
                "episode_count": 20,
                "episode_minutes": 3,
                "budget_band": "band_b",
                "investment_amount_rmb": 1_500_000,
                "is_ai_generated": False,
            },
            headers=OWNER,
        )
        classified = client.post(
            f"/v1/projects/{project_id}/classify", headers=OWNER
        ).json()["classification"]
        assert (classified["tier"], classified["tier_provisional"]) == ("T2", False)
        assert classified["policy_verification_status"] == "mock_verified"

        client.post(f"/v1/projects/{project_id}/roadmap/confirm", headers=OWNER)
        versions = {
            "mat_synopsis": upload(client, project_id, "synopsis", b"synopsis"),
            "mat_script": upload(
                client,
                project_id,
                "script",
                "第一集 场景一：办公室。两位创业者讨论作品。".encode(),
            ),
        }
        for material_id, version_id in versions.items():
            attached = client.post(
                f"/v1/projects/{project_id}/materials/{material_id}/attach",
                json={"asset_version": version_id},
                headers=OWNER,
            )
            assert attached.status_code == 200
            validated = client.post(
                f"/v1/projects/{project_id}/materials/{material_id}/validate",
                headers=OWNER,
            )
            assert validated.json()["status"] == "valid"

        reviewed = client.post(f"/v1/projects/{project_id}/review", headers=OWNER)
        assert reviewed.status_code == 200
        for key, value in {
            "title": "联调项目",
            "applicant_entity": "联调主体",
        }.items():
            assert client.post(
                f"/v1/projects/{project_id}/form/fields/{key}/confirm",
                json={"value": value},
                headers=OWNER,
            ).status_code == 200
        assert client.post(
            f"/v1/projects/{project_id}/gate/pass", headers=OWNER
        ).status_code == 200
        frozen = client.post(
            f"/v1/projects/{project_id}/form/freeze", headers=OWNER
        ).json()
        assert frozen["frozen"] is True
        assert frozen["snapshot_version"] == "v2"
```

- [ ] **Step 2: Run the E2E test and observe RED before completing missing seams**

Run:

```bash
$PYTHON -m pytest tests/test_default_v2_integration.py -q
```

Expected: the first still-unwired v2/material/status seam fails. Fix only the
production seam identified by the failure; do not weaken the end-to-end path.

- [ ] **Step 3: Add the explicit human-review checklist**

Create `docs/policy-v2-human-review-checklist.md` with six sections and unchecked
review boxes for the exact approved items:

```markdown
# Policy Snapshot v2 Human Review Checklist

The current v2 is `mock_verified`. Automated tests cannot check any box below.
The snapshot remains mock until every item is reviewed and evidence is recorded.

## p1 form definition
- [ ] Definition wording matches the cited original.
- [ ] Applicability, jurisdiction, and effective date are confirmed.

## p2 subject rules
- [ ] All nine triggers and edge cases are confirmed by the film partner.
- [ ] T1 and co-review outcomes are confirmed.

## p3 tier thresholds
- [ ] Live-action amounts and applicability are confirmed.
- [ ] AI-generated amounts and applicability are confirmed.
- [ ] Publication and effective dates are confirmed.

## p4 process templates
- [ ] Step order and owners are confirmed.
- [ ] Mandatory steps and any published durations are confirmed.

## p5 form and materials
- [ ] Actual field names and requiredness are confirmed.
- [ ] Material names, templates, and asset-kind mappings are confirmed.

## p6 clauses and evidence
- [ ] Original wording and official URLs are confirmed.
- [ ] Every rule-to-clause mapping is confirmed.

## Promotion
- [ ] All mock content identified above has been replaced or confirmed.
- [ ] Full Python and frontend verification passes unchanged.
- [ ] A human reviewer authorizes `verification_status=human_verified`.
```

- [ ] **Step 4: Record the shared decision and scope**

Add a new accepted decision stating that computational finality and policy
verification are separate, v2 is local-default mock integration data, and
promotion is whole-snapshot and human-only. Update changelog and policy README
with the exact test evidence after verification. Do not claim cloud deployment
or human verification.

- [ ] **Step 5: Run complete verification**

Run from repository root:

```bash
git diff --check
$PYTHON -m pytest
cd web
NODE_OPTIONS=--localstorage-file=/tmp/codex-film-compliance-vitest-localstorage.json npm test
npm run typecheck
npm run build
```

Expected: all Python and frontend tests pass, typecheck exits 0, and Next.js
production build exits 0. Record exact counts in `CHANGELOG.md` only after this
run.

- [ ] **Step 6: Inspect scope and commit**

Run:

```bash
git status --short
git diff --check
git diff --stat origin/main...HEAD
```

Confirm that cloud infrastructure, Gate 5-b, overseas policy, currencies, and
conditional-rule languages are untouched.

```bash
git add tests/test_default_v2_integration.py \
  docs/policy-v2-human-review-checklist.md docs/decisions.md CHANGELOG.md \
  policy/README.md
git commit -m "test: prove complete mock policy v2 workflow"
```

## Final review checkpoint

Before pushing, re-read
`docs/superpowers/specs/2026-08-26-policy-snapshot-v2-complete-mock-design.md`
against the branch diff and verify these non-negotiable outcomes:

- v2 is the local default and v1 remains an explicit fixture;
- p1-p6 are non-empty and cross-pack valid;
- final tier and `mock_verified` coexist without semantic ambiguity;
- every mock UI surface is visibly labelled;
- wrong material kind is 422 and state-preserving;
- one deterministic HTTP path reaches D3 and form freeze;
- no automatic or partial promotion to `human_verified` exists.

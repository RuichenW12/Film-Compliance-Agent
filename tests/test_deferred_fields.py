"""A field can be left blank on purpose without inventing a value.

`applicant_entity` is the case that forced this. A 备案 is filed by a company
holding the 广播电视节目制作经营许可证, so an individual creator has nothing to
put there -- and the licensed company that files supplies its own details.
Before `defer_form_field` existed, the three reachable outcomes were: invent a
company name (which the ground rules forbid), leave the field pending (which
holds the form shut forever), or abandon the filing.

Deferring is the fourth: a fact with no value and `PENDING_INSTITUTION` status,
recorded against the creator who said so. The tests below pin the properties
that make it honest rather than a hole -- the value stays absent, the field
still reads as 待补充, the hash still distinguishes it from a filled field, and
a confirmed value is never silently discarded.
"""

from __future__ import annotations

import pytest

from core.forms import build_fields, deferred_keys, draft_hash, pending_keys
from schemas.common import Fact, SourceRef
from schemas.enums import FactStatus, FieldStatus, SourceRefType
from schemas.forms import PENDING_DISPLAY, FormDraft

KEYS = ("title", "applicant_entity")


def _fact(key: str, value, status: FactStatus) -> Fact:
    return Fact(
        fact_id=f"fact_{key}",
        key=key,
        value=value,
        source_ref=SourceRef(type=SourceRefType.USER_ANSWER, answer_id="ans_1"),
        status=status,
    )


def _draft(fields) -> FormDraft:
    return FormDraft(draft_id="draft_1", fields=fields, snapshot_version="v2")


def test_a_deferred_fact_becomes_a_pending_institution_field() -> None:
    fields, conflicts = build_fields(
        KEYS,
        [
            _fact("title", "夏日便利店", FactStatus.CONFIRMED),
            _fact("applicant_entity", None, FactStatus.PENDING_INSTITUTION),
        ],
    )
    assert not conflicts
    assert fields["applicant_entity"].status is FieldStatus.PENDING_INSTITUTION
    assert fields["applicant_entity"].value is None, "deferring must not invent a value"


def test_a_deferred_field_does_not_hold_the_form_shut() -> None:
    fields, _ = build_fields(
        KEYS,
        [
            _fact("title", "夏日便利店", FactStatus.CONFIRMED),
            _fact("applicant_entity", None, FactStatus.PENDING_INSTITUTION),
        ],
    )
    assert pending_keys(_draft(fields)) == []


def test_an_unanswered_field_still_holds_the_form_shut() -> None:
    """The whole point is that declaring a gap differs from ignoring one."""

    fields, _ = build_fields(KEYS, [_fact("title", "夏日便利店", FactStatus.CONFIRMED)])
    assert pending_keys(_draft(fields)) == ["applicant_entity"]


def test_a_deferred_field_is_listed_on_the_frozen_form() -> None:
    fields, _ = build_fields(
        KEYS,
        [
            _fact("title", "夏日便利店", FactStatus.CONFIRMED),
            _fact("applicant_entity", None, FactStatus.PENDING_INSTITUTION),
        ],
    )
    assert deferred_keys(_draft(fields)) == ["applicant_entity"]


def test_a_deferred_field_reads_as_to_be_supplied() -> None:
    """A reader of the frozen form must see a gap, not a blank that looks filled."""

    fields, _ = build_fields(
        KEYS, [_fact("applicant_entity", None, FactStatus.PENDING_INSTITUTION)]
    )
    field = fields["applicant_entity"]
    rendered = field.value if field.status is FieldStatus.FILLED else PENDING_DISPLAY
    assert rendered == PENDING_DISPLAY


def test_deferring_hashes_differently_from_filling() -> None:
    """Otherwise a declared gap and a real answer would be indistinguishable."""

    deferred, _ = build_fields(
        KEYS, [_fact("applicant_entity", None, FactStatus.PENDING_INSTITUTION)]
    )
    filled, _ = build_fields(
        KEYS, [_fact("applicant_entity", "某某影视有限公司", FactStatus.CONFIRMED)]
    )
    assert draft_hash(_draft(deferred)) != draft_hash(_draft(filled))


def test_a_confirmed_value_outranks_a_later_deferral() -> None:
    """Deferring after answering would quietly throw the answer away."""

    fields, _ = build_fields(
        KEYS,
        [
            _fact("applicant_entity", "某某影视有限公司", FactStatus.CONFIRMED),
            _fact("applicant_entity", None, FactStatus.PENDING_INSTITUTION),
        ],
    )
    assert fields["applicant_entity"].status is FieldStatus.FILLED
    assert fields["applicant_entity"].value == "某某影视有限公司"


def test_the_gate_accepts_a_deferred_fact() -> None:
    """The gate already allowed PENDING_INSTITUTION; this pins it against drift."""

    from core.gate import required_fact_keys

    usable = {
        fact.key
        for fact in [_fact("applicant_entity", None, FactStatus.PENDING_INSTITUTION)]
        if fact.status in (FactStatus.CONFIRMED, FactStatus.PENDING_INSTITUTION)
    }
    assert "applicant_entity" in usable
    assert "applicant_entity" in required_fact_keys()


@pytest.mark.parametrize("status", list(FactStatus))
def test_every_fact_status_maps_to_a_field_status(status: FactStatus) -> None:
    """A new FactStatus must not fall through to a silent PENDING."""

    fields, _ = build_fields(("applicant_entity",), [_fact("applicant_entity", "x", status)])
    field = fields["applicant_entity"]
    expected = {
        FactStatus.CONFIRMED: FieldStatus.FILLED,
        FactStatus.CONFLICT: FieldStatus.CONFLICT,
        FactStatus.PENDING_INSTITUTION: FieldStatus.PENDING_INSTITUTION,
    }[status]
    assert field.status is expected


def test_the_revision_loop_is_not_a_dead_end(workflow, intent_romance) -> None:
    """A returned project must be correctable and resubmittable.

    `form_draft` returns a frozen draft unchanged and `freeze_form` early-returns
    one, so before `resume_after_return` started a successor draft a returned
    project could be resumed and its gate re-passed but never re-frozen. The
    state never reached FORM_FROZEN again and every resubmission answered 409:
    the creator could read the reviewer's comments and had no way to act on them.
    """

    from schemas.enums import ProjectState

    project_id = workflow.create_project("u_demo", "夏日便利店").project_id
    workflow.submit_intent(project_id, intent_romance.model_dump())
    workflow.run_classification(project_id)

    before = workflow.form_draft(project_id)
    frozen = before.model_copy(update={"frozen": True, "hash": "a" * 64})
    workflow._stores.forms.put(project_id, frozen)
    project = workflow.get_project(project_id)
    workflow._stores.projects.save(
        project.model_copy(update={"state": ProjectState.INSTITUTION_RETURNED})
    )

    workflow.resume_after_return(project_id)

    successor = workflow.form_draft(project_id)
    assert successor.frozen is False, "the creator must be able to edit again"
    assert successor.draft_id != frozen.draft_id, "a new draft, not the old one"
    assert successor.parent_draft == frozen.draft_id, "lineage is kept"

    # The reviewed version is still retrievable: it is the record of what was
    # sent, and resuming must not rewrite history.
    kept = workflow._stores.forms.get(project_id, frozen.draft_id)
    assert kept is not None and kept.frozen is True
    assert kept.hash == "a" * 64

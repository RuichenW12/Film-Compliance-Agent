"""C1-c form drafts: preview, confirm, freeze (contract step 11).

Which fields the form has is policy content — the same `required_facts` the D3
gate uses, so the gate and the form can never disagree about what is needed.

A field is only ever filled from a confirmed fact, carrying that fact's
`SourceRef`. Everything else renders as 待补充. The model layer refuses to mark a
field filled without a source, so an invented value cannot reach a form even by
mistake.

Freezing hashes the draft. The hash covers the field values, their sources, and
the snapshot version, so a frozen form is verifiable against the policy it was
prepared under.
"""

from __future__ import annotations

import hashlib
import json

from schemas.common import Fact, SourceRef
from schemas.enums import FactStatus, FieldStatus
from schemas.forms import FormConflict, FormDraft, FormField


def build_fields(
    fact_keys: tuple[str, ...] | list[str], facts: list[Fact]
) -> tuple[dict[str, FormField], list[FormConflict]]:
    """One field per required key, filled only where a confirmed fact exists."""

    by_key: dict[str, list[Fact]] = {}
    for fact in facts:
        by_key.setdefault(fact.key, []).append(fact)

    fields: dict[str, FormField] = {}
    conflicts: list[FormConflict] = []

    for key in fact_keys:
        candidates = by_key.get(key) or []
        conflicting = [f for f in candidates if f.status is FactStatus.CONFLICT]
        confirmed = [f for f in candidates if f.status is FactStatus.CONFIRMED]

        if conflicting:
            # Two sources disagree. Neither is rendered as the answer.
            fields[key] = FormField(status=FieldStatus.CONFLICT)
            conflicts.append(
                FormConflict(
                    check="facts_conflicting",
                    message_key="form.conflict.facts",
                    items=[key],
                )
            )
            continue

        if confirmed:
            latest = confirmed[-1]
            fields[key] = FormField(
                value=latest.value,
                source_ref=latest.source_ref,
                status=FieldStatus.FILLED,
            )
            continue

        # A fact the creator has deliberately left for the filing institution.
        # It renders 待补充 exactly like an unanswered field -- the difference is
        # that somebody said so on the record, which is why it carries the
        # answer's SourceRef and does not hold the form shut.
        deferred = [f for f in candidates if f.status is FactStatus.PENDING_INSTITUTION]
        if deferred:
            fields[key] = FormField(
                source_ref=deferred[-1].source_ref,
                status=FieldStatus.PENDING_INSTITUTION,
            )
            continue

        fields[key] = FormField(status=FieldStatus.PENDING)

    return fields, conflicts


def draft_hash(draft: FormDraft) -> str:
    """Stable over field values, their provenance, and the pinned snapshot."""

    payload = {
        "form_type": draft.form_type,
        "snapshot_version": draft.snapshot_version,
        "fields": {
            key: {
                "value": field.value,
                "status": field.status.value,
                "source": _source_key(field.source_ref),
            }
            for key, field in sorted(draft.fields.items())
        },
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _source_key(source: SourceRef | None) -> dict | None:
    if source is None:
        return None
    return {
        "type": source.type.value,
        "asset_version": source.asset_version,
        "locator": source.locator,
        "answer_id": source.answer_id,
        "institution_id": source.institution_id,
    }


def pending_keys(draft: FormDraft) -> list[str]:
    """Fields that still hold the form shut.

    `PENDING_INSTITUTION` is not among them. It means a human said this value
    comes from the institution that files the project rather than from the
    creator -- the commonest case being `applicant_entity`, which an individual
    creator does not have because the licensed company supplies its own. The
    field still renders 待补充 and still hashes as unfilled, so nothing is
    invented and the gap stays visible on the frozen form; it simply stops
    being a reason the creator can never finish.
    """

    return sorted(
        key
        for key, field in draft.fields.items()
        if field.status not in (FieldStatus.FILLED, FieldStatus.PENDING_INSTITUTION)
    )


def deferred_keys(draft: FormDraft) -> list[str]:
    """Fields frozen as 待补充 on purpose, for whoever reads the form later."""

    return sorted(
        key
        for key, field in draft.fields.items()
        if field.status is FieldStatus.PENDING_INSTITUTION
    )

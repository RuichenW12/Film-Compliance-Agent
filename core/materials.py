"""Building material collection cards from the `p5_form_templates` pack.

The card list is policy content, not product logic: the product decides how a
card behaves, the snapshot decides which cards exist. An empty pack yields no
cards rather than invented ones, so a missing pack is visible instead of guessed.

Pack shape this loader accepts:

```yaml
p5_form_templates:
  required_facts: [title, applicant_entity]
  material_cards:
    - material_id: mat_synopsis      # required
      name_key: material.synopsis    # required, rendered from web/locales
      required: true                 # default true
      why_clause_id: nrta-order-16-article-19   # optional
      template_uri: https://...      # optional
      common_rejects_key: material.synopsis.rejects   # optional
```

`why_clause_id` is resolved against the pinned snapshot. A card whose clause is
missing from that snapshot keeps its `why_clause` empty rather than pointing at
a clause that is not there — ground rule 2 in the collection UI.
"""

from __future__ import annotations

from schemas.assets import MaterialCard
from schemas.common import EvidenceRef
from schemas.snapshot import SnapshotNotFoundError, SnapshotService

CARDS_KEY = "material_cards"


def build_material_cards(
    form_pack: dict | None,
    snapshots: SnapshotService,
    version: str,
) -> list[MaterialCard]:
    """Cards defined by the pack, in pack order. No pack, no cards."""

    if not form_pack:
        return []

    cards: list[MaterialCard] = []
    for raw in form_pack.get(CARDS_KEY) or []:
        material_id = raw.get("material_id")
        name_key = raw.get("name_key")
        if not material_id or not name_key:
            # A malformed entry is skipped rather than rendered as a nameless
            # obligation. The pack author sees the gap, the creator does not
            # see a card with no meaning.
            continue
        cards.append(
            MaterialCard(
                material_id=str(material_id),
                name_key=str(name_key),
                required=bool(raw.get("required", True)),
                why_clause=_evidence_for(raw.get("why_clause_id"), snapshots, version),
                template_uri=raw.get("template_uri"),
                common_rejects_key=raw.get("common_rejects_key"),
            )
        )
    return cards


def _evidence_for(
    clause_id: str | None, snapshots: SnapshotService, version: str
) -> EvidenceRef | None:
    if not clause_id:
        return None
    try:
        snapshots.clause(str(clause_id), version)
    except (SnapshotNotFoundError, KeyError):
        return None
    return EvidenceRef(snapshot_version=version, clause_id=str(clause_id))

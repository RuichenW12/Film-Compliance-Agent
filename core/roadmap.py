"""Building a roadmap from the `p4_process_templates` pack.

Which template a project gets is already decided by the classification chain
(tier -> template name). Which steps that template contains is policy content.
An unpublished template yields no steps and a `roadmap_template_pending` flag,
because a plan the policy does not define must not be invented — the creator
would follow it.

Pack shape this loader accepts:

```yaml
p4_process_templates:
  templates:
    T3_4steps:
      steps:
        - name: roadmap.step.materials   # message key, rendered from web/locales
          owner: creator                 # creator | institution | system
          material_refs: [mat_synopsis]  # optional, ids from p5 material_cards
          est_weeks: 2                   # optional
```

`name` carries a message key rather than prose so the UI renders it in the
viewer's locale, the same way `MaterialCard.name_key` works. The field is called
`name` because `RoadmapStep` already names it that; see D-017.
"""

from __future__ import annotations

from schemas.project import Roadmap, RoadmapStep

TEMPLATES_KEY = "templates"
STEPS_KEY = "steps"
PENDING_FLAG = "roadmap_template_pending"


def build_roadmap(
    template: str, process_pack: dict | None
) -> tuple[Roadmap, list[str]]:
    """Return the roadmap for this template plus any pending flags."""

    steps = _steps_for(template, process_pack)
    roadmap = Roadmap(template=template, steps=steps)
    return roadmap, [] if steps else [PENDING_FLAG]


def _steps_for(template: str, process_pack: dict | None) -> list[RoadmapStep]:
    if not process_pack:
        return []
    definition = (process_pack.get(TEMPLATES_KEY) or {}).get(template) or {}

    steps: list[RoadmapStep] = []
    for index, raw in enumerate(definition.get(STEPS_KEY) or [], start=1):
        name = raw.get("name")
        owner = raw.get("owner")
        if not name or not owner:
            # A step with no name or no owner tells the creator nothing about
            # what to do or who does it, so it is skipped rather than shown.
            continue
        steps.append(
            RoadmapStep(
                idx=index,
                name=str(name),
                owner=str(owner),
                material_refs=[str(ref) for ref in raw.get("material_refs") or []],
                est_weeks=raw.get("est_weeks"),
            )
        )
    return steps

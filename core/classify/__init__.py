"""The D1a -> D1b -> D1c decision chain. Pure rules first, one semantic check."""

from .chain import ClassificationOutcome, classify
from .d1a import FormTypeDecision, judge_form_type
from .d1b import SubjectDecision, judge_subject
from .d1c import TierDecision, judge_tier

__all__ = [
    "ClassificationOutcome",
    "FormTypeDecision",
    "SubjectDecision",
    "TierDecision",
    "classify",
    "judge_form_type",
    "judge_subject",
    "judge_tier",
]

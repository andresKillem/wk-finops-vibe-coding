"""Abstract base for detection rules.

A `DetectionRule` is a self-contained, testable unit that turns one Resource
(plus its BillingRecord history) into 0 or 1 Finding. Rules are intentionally
**declarative and isolated** — see BITACORA ADR-008 for the rules-as-code
rationale.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from finops.db.models import BillingRecord, Finding, Resource


@dataclass
class RuleSignal:
    """One named signal that contributed to a rule firing.

    Capturing signals separately (instead of inlining boolean math) gives us:
    1. Confidence calibration (more signals → higher confidence).
    2. Auditability — the Finding records *why* it fired, not just that it did.
    """

    name: str
    matched: bool
    weight: float = 1.0
    detail: str = ""


@dataclass
class RuleEvaluation:
    """Internal scratch space a rule fills in `_evaluate_signals`. Stays out of DB."""

    signals: list[RuleSignal] = field(default_factory=list)
    savings_estimate: float = 0.0
    extra_attrs: dict[str, Any] = field(default_factory=dict)


class DetectionRule(ABC):
    """Subclass and override `applies_to` and `_evaluate_signals`.

    The base class:
    - Routes signals → confidence (sum of matched signal weights, clamped to 1.0).
    - Skips emitting a Finding when no signals matched.
    - Builds the Finding object so subclasses don't have to care about ORM details.
    """

    rule_id: str = ""
    severity: str = "LOW"  # LOW | MEDIUM | HIGH
    title: str = ""
    description_template: str = ""

    # Minimum confidence (sum of matched-signal weights, capped at 1.0) required
    # to actually emit a Finding. Default 0.5 — at least one strong signal,
    # or several supporting ones together. Override per-rule if needed.
    min_confidence: float = 0.5

    # Rationale documented inside each rule's docstring; surfaced in scan output.
    production_signal: str = "(documented in subclass)"
    offline_proxy: str = "(documented in subclass)"

    @abstractmethod
    def applies_to(self, resource: Resource) -> bool:
        """Quick filter — does this rule even consider resources of this type/provider?"""

    @abstractmethod
    def _evaluate_signals(
        self, resource: Resource, billing: list[BillingRecord]
    ) -> RuleEvaluation:
        """Inspect resource + billing, return signals + savings estimate."""

    def evaluate(
        self, resource: Resource, billing: list[BillingRecord]
    ) -> Finding | None:
        """Public entrypoint. Returns a Finding if any signal matched, else None."""
        if not self.applies_to(resource):
            return None
        ev = self._evaluate_signals(resource, billing)
        matched = [s for s in ev.signals if s.matched]
        if not matched:
            return None

        confidence = min(sum(s.weight for s in matched), 1.0)
        if confidence < self.min_confidence:
            return None
        return Finding(
            resource_id=resource.resource_id,
            rule_id=self.rule_id,
            severity=self.severity,
            description=self._format_description(resource, ev),
            savings_estimate=round(ev.savings_estimate, 2),
            confidence=round(confidence, 3),
            attrs={
                "title": self.title,
                "production_signal": self.production_signal,
                "offline_proxy": self.offline_proxy,
                "signals": [
                    {"name": s.name, "matched": s.matched, "weight": s.weight, "detail": s.detail}
                    for s in ev.signals
                ],
                **ev.extra_attrs,
            },
        )

    def _format_description(self, resource: Resource, ev: RuleEvaluation) -> str:
        """Default description renderer; subclasses can override."""
        return self.description_template.format(
            resource_id=resource.resource_id,
            type=resource.type,
            region=resource.region or "",
            savings=ev.savings_estimate,
            **ev.extra_attrs,
        )

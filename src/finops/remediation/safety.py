"""SafetyGate — last-line validator before a RemediationPlan is released.

Two layers of protection sit upstream of this validator (the deny list in
`.claude/settings.json` and the `safety_gate.sh` PreToolUse hook); this
Python-side validator handles the case where someone tries to ingest a plan
generated externally, and re-validates plans we generate ourselves so the
guarantee survives module changes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from finops.db.models import RemediationPlan

# Patterns we never tolerate in any rendered plan or commands list.
DANGEROUS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("rm -rf",                    re.compile(r"\brm\s+-rf\b")),
    ("--force",                   re.compile(r"--force\b")),
    ("--skip-final-snapshot",     re.compile(r"--skip-final-snapshot\b")),
    ("SkipFinalSnapshot=True",    re.compile(r"SkipFinalSnapshot\s*=\s*True", re.IGNORECASE)),
    ("terraform destroy auto",    re.compile(r"terraform\s+destroy[^\n]*-auto-approve", re.IGNORECASE)),
    ("terraform apply auto",      re.compile(r"terraform\s+apply[^\n]*-auto-approve", re.IGNORECASE)),
    ("kubectl delete --all",      re.compile(r"kubectl\s+delete\b[^\n]*--all\b")),
    ("aws ec2 terminate raw",     re.compile(r"^[^\n#]*aws\s+ec2\s+terminate-instances\b(?![^\n]*--dry-run)", re.MULTILINE)),
    ("aws ec2 delete-volume raw", re.compile(r"^[^\n#]*aws\s+ec2\s+delete-volume\b(?![^\n]*--dry-run)", re.MULTILINE)),
    ("aws rds delete raw",        re.compile(r"^[^\n#]*aws\s+rds\s+delete-db-instance\b(?![^\n]*--final)", re.MULTILINE)),
    ("aws s3 rb",                 re.compile(r"\baws\s+s3\s+rb\b")),
    ("fork bomb",                 re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:")),
]


@dataclass
class Violation:
    name: str
    pattern: str
    snippet: str


@dataclass
class ValidationResult:
    ok: bool
    violations: list[Violation]
    blast_radius_blocked: bool = False

    def __bool__(self) -> bool:
        return self.ok


class SafetyGate:
    """Validate a RemediationPlan against forbidden patterns + blast-radius gating."""

    @staticmethod
    def _scan_text(text: str) -> list[Violation]:
        results: list[Violation] = []
        for name, pat in DANGEROUS_PATTERNS:
            for m in pat.finditer(text):
                start = max(0, m.start() - 30)
                end = min(len(text), m.end() + 30)
                results.append(
                    Violation(name=name, pattern=pat.pattern, snippet=text[start:end].strip())
                )
        return results

    @classmethod
    def validate(cls, plan: RemediationPlan, allow_high_blast_radius: bool = False) -> ValidationResult:
        """Reject if any dangerous pattern OR if blast_radius=high without override."""
        violations: list[Violation] = []

        # Scan rendered text + each command line
        violations.extend(cls._scan_text(plan.rendered or ""))
        for cmd in plan.commands or []:
            violations.extend(cls._scan_text(cmd))

        blast_blocked = False
        if (plan.blast_radius or "low").lower() == "high" and not allow_high_blast_radius:
            blast_blocked = True

        ok = not violations and not blast_blocked
        return ValidationResult(ok=ok, violations=violations, blast_radius_blocked=blast_blocked)

    @classmethod
    def validate_text(cls, text: str) -> ValidationResult:
        """Convenience for testing / external rendering — scans a string."""
        v = cls._scan_text(text)
        return ValidationResult(ok=not v, violations=v)

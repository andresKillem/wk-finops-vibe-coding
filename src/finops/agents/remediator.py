"""RemediatorAgent — Haiku worker. Runs in parallel, one per critical finding.

Receives a single Finding plus the deterministically-generated base plan.
Returns enrichment (preconditions narrative, rollback steps, stakeholder comm,
adjacent optimisations). Cheap and fast; multiple instances run in parallel
via asyncio.gather in the orchestrator.
"""
from __future__ import annotations

import time
from typing import Any

from finops.agents.base import AgentResponse, BaseAgent, estimate_cost, extract_json_object
from finops.config import settings


SYSTEM_PROMPT = """\
You are a senior infrastructure engineer drafting a safe decommission plan
for a single cloud resource.

You receive: a `finding` object and a deterministically-generated `base_plan`
with the actual commands. Your job is to add the human layer around them.

You MUST output ONLY a single JSON object — no markdown, no prose before or after.

Output schema:
{
  "preconditions_narrative": "1-2 sentences: what state must hold for the plan to be safe.",
  "rollback_procedure": ["step 1", "step 2", "step 3"],
  "stakeholder_communication": "Slack-ready, ≤4 lines: who to notify, what to say.",
  "adjacent_optimizations": ["1-2 nearby savings opportunities, optional"]
}

Hard rules:
- Do NOT modify the base plan's commands. The deterministic generator owns those.
- Do NOT lower the safety bar. If blast_radius is high, your rollback procedure
  reinforces caution (additional verification steps) instead of rationalising bypass.
- Be specific. "Verify volume state is available" beats "verify state".
- Adjacent optimisations are optional; omit the list if nothing useful comes to mind.
"""


class RemediatorAgent(BaseAgent):
    """One Haiku call per finding. Enriches a base plan with human-readable layers."""

    name = "remediator"

    def __init__(self) -> None:
        super().__init__(model=settings.anthropic_worker_model)

    async def _run_llm(self, input_dict: dict[str, Any]) -> AgentResponse:
        client = self.client
        assert client is not None

        user_msg = (
            f"Finding:\n```json\n{input_dict.get('finding', {})}\n```\n\n"
            f"Base plan (do not modify commands):\n```json\n{input_dict.get('base_plan', {})}\n```\n\n"
            "Produce the enrichment JSON per the schema in your system prompt."
        )

        start = time.perf_counter()
        msg = await client.messages.create(
            model=self.model,
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        duration_ms = int((time.perf_counter() - start) * 1000)

        text = "".join(b.text for b in msg.content if b.type == "text")
        output = extract_json_object(text)
        success = bool(output)

        return AgentResponse(
            agent_name=self.name,
            model=msg.model,
            success=success,
            output=output if success else {"raw_text": text},
            raw_response=text,
            tokens_in=msg.usage.input_tokens,
            tokens_out=msg.usage.output_tokens,
            duration_ms=duration_ms,
            cost_estimate=estimate_cost(msg.model, msg.usage.input_tokens, msg.usage.output_tokens),
            error=None if success else "could not extract JSON object from response",
        )

    def _run_fallback(self, input_dict: dict[str, Any]) -> AgentResponse:
        finding = input_dict.get("finding") or {}
        base_plan = input_dict.get("base_plan") or {}
        rid = finding.get("resource_id", "<unknown>")
        rtype = finding.get("rule_id", "").split("-")[1].lower() if finding.get("rule_id") else "resource"
        savings = float(finding.get("savings_estimate", 0) or 0)
        blast = base_plan.get("blast_radius", "low")

        templates = {
            "ebs": {
                "preconditions": f"Volume {rid} must remain in 'available' state and not be reattached since the last scan.",
                "rollback": [
                    "Restore from the snapshot taken in the Snapshot section of the plan.",
                    "Recreate the volume in the original AZ and same size.",
                    "Reattach to the originating instance if still present.",
                ],
            },
            "ec2": {
                "preconditions": f"Instance {rid} must remain stopped and untagged for re-activation since the last scan.",
                "rollback": [
                    "Launch a new instance from the AMI captured in the AMI step.",
                    "Reattach EBS volumes referenced in the AMI's block device mappings.",
                    "Update DNS / load-balancer registrations.",
                ],
            },
            "eip": {
                "preconditions": f"EIP {rid} must remain unassociated; check ec2 describe-addresses again immediately before release.",
                "rollback": [
                    "Allocate a new Elastic IP (will get a different public IP).",
                    "Update DNS records or downstream consumers if anything depended on the old address.",
                ],
            },
            "nat": {
                "preconditions": f"NAT Gateway {rid} must have zero referencing route tables (verify list in the Pre-check).",
                "rollback": [
                    "Recreate the NAT Gateway in the same subnet.",
                    "Re-associate referenced route tables to the new NAT.",
                    "Validate egress from private subnets within 5 minutes.",
                ],
            },
            "rds": {
                "preconditions": f"RDS {rid} must show zero DatabaseConnections in the most recent 24h CloudWatch window.",
                "rollback": [
                    "Restore from the final snapshot taken on delete.",
                    "Update application connection strings to the restored endpoint.",
                    "Re-enable any IAM-auth or security group rules.",
                ],
            },
            "elb": {
                "preconditions": f"Load balancer {rid} must have zero healthy targets across all target groups.",
                "rollback": [
                    "Recreate the LB with the saved listener/target group configuration.",
                    "Re-register targets and verify health checks pass.",
                    "Re-point DNS to the new LB DNS name.",
                ],
            },
            "inst": {
                "preconditions": f"Migration window for {rid}: schedule maintenance, ensure rollback path exists.",
                "rollback": [
                    "Roll back to previous instance type via stop / change-type / start.",
                    "Validate application performance after rollback.",
                ],
            },
        }
        t = templates.get(rtype, templates["ebs"])

        return AgentResponse(
            agent_name=self.name,
            model="deterministic-fallback",
            success=True,
            output={
                "preconditions_narrative": t["preconditions"],
                "rollback_procedure": t["rollback"],
                "stakeholder_communication": (
                    f":warning: FinOps action — `{rid}` ({rtype}, ~${savings:.2f}/mo, blast {blast}). "
                    f"Plan attached. Approval needed from on-call before execute. "
                    f"Snapshot/AMI retained per rollback procedure."
                ),
                "adjacent_optimizations": [],
            },
            raw_response="",
            tokens_in=0,
            tokens_out=0,
            duration_ms=0,
            cost_estimate=0.0,
            fallback_mode=True,
        )

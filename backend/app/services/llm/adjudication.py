"""LLM adjudication reasoning — analyzes medical necessity and exclusions against policy terms."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import Settings, get_settings, get_llm_client_and_model

logger = logging.getLogger(__name__)

ADJUDICATION_SCHEMA = """
Return JSON with this shape only:
{
  "medical_necessity_established": bool,
  "exclusions_detected": [str],
  "rejected_line_items": [
    {
      "item_name": str,       // name of the rejected medicine, test, or procedure
      "amount": float,        // cost of this item from the bill
      "reason": str           // why it was rejected
    }
  ],
  "approved_amount": float,    // total approved amount after removing rejected items and applying copay
  "verdict": "APPROVED" | "REJECTED" | "PARTIAL" | "MANUAL_REVIEW",
  "confidence_score": float,  // 0.0 to 1.0
  "notes": str,                // clear explanation of medical necessity, exclusions, and rules applied
  "next_steps": str            // instructions for the claimant
}
"""

def analyze_claim_with_llm(
    claim_id: str,
    claim_number: str,
    claim_amount: float,
    treatment_date: str,
    member_name: str,
    member_id: str,
    documents: dict[str, Any],
    preliminary_decision: dict[str, Any],
    policy_context: list[dict[str, str]],
    settings: Settings | None = None,
) -> dict[str, Any]:
    """
    Call LLM to evaluate the claim's medical necessity and policy exclusions.
    Returns the LLM decision analysis.
    """
    settings = settings or get_settings()
    client, model = get_llm_client_and_model(settings)

    if not client or not model:
        logger.info("No LLM API key resolved. Skipping LLM adjudication.")
        return _build_fallback_response(preliminary_decision, "LLM adjudication skipped: API key missing.")

    # Format the policy RAG context
    policy_text = ""
    for idx, chunk in enumerate(policy_context, 1):
        policy_text += f"\n[Policy Reference {idx}] (Source: {chunk.get('source')}):\n{chunk.get('text')}\n"

    # Formulate prompts
    prompt = (
        f"Claim Details:\n"
        f"- ID: {claim_id}\n"
        f"- Number: {claim_number}\n"
        f"- Member Name: {member_name} (ID: {member_id})\n"
        f"- Treatment Date: {treatment_date}\n"
        f"- Claim Amount: ₹{claim_amount}\n\n"
        f"Extracted Documents Data:\n"
        f"{json.dumps(documents, indent=2)}\n\n"
        f"Rule Engine Preliminary Outcome:\n"
        f"{json.dumps(preliminary_decision, indent=2)}\n\n"
        f"Retrieved Policy Context (RAG):\n"
        f"{policy_text if policy_text else 'No policy RAG context retrieved.'}\n\n"
        f"Instructions:\n"
        f"1. Evaluate if the diagnosis justifies the treatment, medicines, and tests prescribed (Medical Necessity).\n"
        f"2. Check if any prescribed item or condition is explicitly excluded by the policy (e.g. vitamins/supplements without deficiency, cosmetic procedures, medicines not relevant to the diagnosis).\n"
        f"3. Verify the preliminary decision computed by the rule engine.\n"
        f"4. Recommend a final verdict and provide detailed reasons in 'notes'.\n"
        f"5. For each item that is NOT medically necessary or is excluded, add it to 'rejected_line_items' with its cost from the bill. "
        f"Then compute 'approved_amount' = (claim_amount - sum of rejected item costs), then apply 10% copay on any remaining consultation fees, and cap at the per-claim limit of ₹5000. "
        f"If any items are rejected but some are approved, set verdict to 'PARTIAL'. If ALL items are rejected, set verdict to 'REJECTED'.\n\n"
        f"{ADJUDICATION_SCHEMA}"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert insurance claim adjudicator. Analyze medical necessity, "
                        "exclusions, and policy rules, then output a structured JSON analysis. "
                        "CRITICAL: Output valid JSON only. Do not include any unescaped double-quotes "
                        "inside string values (use single-quotes or escape them as \\\")."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=2048,
        )
        content = response.choices[0].message.content or "{}"
        logger.info("Raw LLM response content: %s", content)
        content_clean = content.strip()
        if content_clean.startswith("```"):
            if content_clean.startswith("```json"):
                content_clean = content_clean[7:]
            else:
                content_clean = content_clean[3:]
            if content_clean.endswith("```"):
                content_clean = content_clean[:-3]
            content_clean = content_clean.strip()
        result = json.loads(content_clean)
        logger.info("Successfully completed LLM adjudication analysis for claim %s", claim_number)
        return result

    except Exception as exc:
        logger.warning("LLM adjudication failed for claim %s: %s. Reverting to rule engine.", claim_number, exc)
        return _build_fallback_response(
            preliminary_decision,
            f"LLM adjudication failed: {exc}. Reverted to deterministic rule engine outcome."
        )


def _build_fallback_response(preliminary_decision: dict[str, Any], fallback_reason: str) -> dict[str, Any]:
    """Helper to construct a standard structured response if LLM call is bypassed or fails."""
    # Heuristically infer medical necessity from rule engine outcome
    is_rejected = preliminary_decision.get("decision") == "REJECTED"
    rejection_reasons = preliminary_decision.get("rejection_reasons") or []

    # Map exclusions detected
    exclusions = []
    if "SERVICE_NOT_COVERED" in rejection_reasons:
        exclusions.append("Treatment/Service is excluded or not covered under policy rules")

    return {
        "medical_necessity_established": not is_rejected,
        "exclusions_detected": exclusions,
        "rejected_line_items": [],
        "approved_amount": None,
        "verdict": preliminary_decision.get("decision", "MANUAL_REVIEW"),
        "confidence_score": preliminary_decision.get("confidence_score", 0.95),
        "notes": f"{preliminary_decision.get('notes', '')}\n\n[System Info: {fallback_reason}]".strip(),
        "next_steps": preliminary_decision.get("next_steps") or "Refer to claims representative for support."
    }

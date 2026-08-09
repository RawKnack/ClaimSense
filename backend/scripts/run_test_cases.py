"""Run test_cases.json against the rule engine (no HTTP server required)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.rule_engine import AdjudicationContext, run_rule_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_CASES_PATH = PROJECT_ROOT / "test_cases.json"


def main() -> None:
    data = json.loads(TEST_CASES_PATH.read_text(encoding="utf-8"))
    passed = 0
    for tc in data["test_cases"]:
        inp = tc["input_data"]
        expected = tc["expected_output"]
        ctx = AdjudicationContext(
            member_id=inp["member_id"],
            member_name=inp["member_name"],
            treatment_date=inp["treatment_date"],
            claim_amount=inp["claim_amount"],
            documents=inp.get("documents", {}),
            member_join_date=inp.get("member_join_date"),
            hospital=inp.get("hospital"),
            cashless_request=inp.get("cashless_request", False),
            previous_claims_same_day=inp.get("previous_claims_same_day"),
        )
        result = run_rule_engine(ctx)
        ok = result["decision"] == expected["decision"]
        if expected.get("approved_amount") is not None:
            ok = ok and result.get("approved_amount") == expected["approved_amount"]
        if expected.get("rejection_reasons"):
            ok = ok and result.get("rejection_reasons") == expected["rejection_reasons"]
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"{status} {tc['case_id']}: got {result['decision']}, expected {expected['decision']}")
        if not ok:
            print(f"       full result: {result}")
    print(f"\n{passed}/{len(data['test_cases'])} passed")


if __name__ == "__main__":
    main()

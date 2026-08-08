import os
import sys
import uuid
import hashlib
import json
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.db.models import Claim, ClaimStatus, Decision
from app.services.adjudication_pipeline import adjudicate_claim


def run_verification():
    # Clean up pre-existing database file from prior failed runs
    if os.path.exists("verification_temp.db"):
        try:
            os.remove("verification_temp.db")
        except Exception:
            pass

    print("Initializing verification SQLite database...")
    db_url = "sqlite:///./verification_temp.db"
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Generate unique claim numbers
        cn1 = f"CLM_TEST_{uuid.uuid4().hex[:8].upper()}"
        cn2 = f"CLM_TEST_{uuid.uuid4().hex[:8].upper()}"

        # 1. Create a first claim
        claim1 = Claim(
            id=uuid.uuid4(),
            claim_number=cn1,
            status=ClaimStatus.PENDING,
            member_id="EMP001",
            member_name="Rajesh Kumar",
            treatment_date="2024-11-01",
            claim_amount=1500,
            metadata_extra={
                "structured_documents": {
                    "prescription": {
                        "doctor_name": "Dr. Sharma",
                        "doctor_reg": "KA/45678/2015",
                        "diagnosis": "Viral fever",
                    },
                    "bill": {
                        "consultation_fee": 1000,
                        "diagnostic_tests": 500,
                    }
                }
            },
            document_paths={},
        )
        db.add(claim1)
        db.commit()
        db.refresh(claim1)

        print("Adjudicating first claim...")
        res1 = adjudicate_claim(db, claim1, structured_documents=claim1.metadata_extra["structured_documents"])
        print(f"First Claim Verdict: {res1['decision']}")
        assert res1['decision'] == "APPROVED", f"Expected APPROVED for first claim, got {res1['decision']}"

        # Verify that MD5 bill hash was stored in metadata_extra
        db.refresh(claim1)
        stored_hash = claim1.metadata_extra.get("file_hashes", {}).get("bill")
        print(f"First Claim Saved Bill Hash: {stored_hash}")
        assert stored_hash is not None, "Bill hash was not stored in metadata_extra"

        # 2. Create a second claim with the exact same bill data but on a different date
        claim2 = Claim(
            id=uuid.uuid4(),
            claim_number=cn2,
            status=ClaimStatus.PENDING,
            member_id="EMP001",
            member_name="Rajesh Kumar",
            treatment_date="2024-11-02",
            claim_amount=1500,
            metadata_extra={
                "structured_documents": {
                    "prescription": {
                        "doctor_name": "Dr. Sharma",
                        "doctor_reg": "KA/45678/2015",
                        "diagnosis": "Viral fever",
                    },
                    "bill": {
                        "consultation_fee": 1000,
                        "diagnostic_tests": 500,
                    }
                }
            },
            document_paths={},
        )
        db.add(claim2)
        db.commit()
        db.refresh(claim2)

        print("Adjudicating second claim (duplicate bill)...")
        res2 = adjudicate_claim(db, claim2, structured_documents=claim2.metadata_extra["structured_documents"])
        print(f"Second Claim Verdict: {res2['decision']}")
        print(f"Second Claim Rejection Reasons: {res2.get('rejection_reasons')}")
        print(f"Second Claim Notes: {res2.get('notes')}")

        assert res2['decision'] == "REJECTED", f"Expected REJECTED for second claim, got {res2['decision']}"
        assert "DUPLICATE_CLAIM" in res2.get('rejection_reasons', []), f"Expected DUPLICATE_CLAIM reason, got {res2.get('rejection_reasons')}"
        assert "Duplicate bill detected" in res2.get('notes', ""), f"Expected duplicate note in notes, got {res2.get('notes')}"

        print("\nDuplicate Bill Check Verification: SUCCESS")

    finally:
        db.close()
        engine.dispose()
        # Clean up database file
        try:
            if os.path.exists("verification_temp.db"):
                os.remove("verification_temp.db")
        except Exception:
            pass


if __name__ == "__main__":
    run_verification()

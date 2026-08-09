# ClaimSense — Backend API

FastAPI gateway with deterministic rule engine, LLM-powered adjudication, and Postgres persistence.

## Architecture (current)

| Layer | Status |
|-------|--------|
| `POST /api/v1/claims` | Multipart upload + metadata, returns `claim_id` immediately |
| `GET /api/v1/claims/{id}` | Poll status + decision when ready |
| `GET /api/v1/claims/{id}/decision` | Decision JSON only |
| Rule engine | Deterministic rules (TC001–TC010) |
| OCR (Tesseract + OpenCV) | Wired when files uploaded |
| LLM extraction | OpenAI/Gemini if key set; else heuristics |
| Policy RAG | Keyword retrieval over policy + rules |
| Frontend | `../frontend` (Next.js) |

## Quick Start (with Docker Compose)

```powershell
# From project root
docker compose up --build -d
```

Once running, the backend API will be available at http://localhost:8000. Open the interactive API documentation at http://localhost:8000/docs.

## Manual Setup (without Docker Compose but with Postgres)

1. Ensure a PostgreSQL instance is running with the `pgvector` extension.
2. Configure your environment variables by copying `.env.example` to `.env` and setting `DATABASE_URL` appropriately.
3. Install dependencies and start the application:

```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --app-dir .
```

## Submit a claim (structured JSON for testing)

```bash
curl -X POST "http://localhost:8000/api/v1/claims" \
  -F "member_id=EMP001" \
  -F "member_name=Rajesh Kumar" \
  -F "treatment_date=2024-11-01" \
  -F "claim_amount=1500" \
  -F 'structured_documents={"prescription":{"doctor_name":"Dr. Sharma","doctor_reg":"KA/45678/2015","diagnosis":"Viral fever"},"bill":{"consultation_fee":1000,"diagnostic_tests":500}}'
```

Poll: `GET /api/v1/claims/{claim_id}`

## Run test cases offline

```bash
cd backend
python scripts/run_test_cases.py
```

## Environment

| Variable | Default |
|----------|---------|
| `DATABASE_URL` | `postgresql+psycopg2://claimsense:claimsense@localhost:5433/claimsense_db` |
| `UPLOAD_DIR` | `uploads` |

Policy files are read from the project root (`policy_terms.json`, `adjudication_rules.md`).

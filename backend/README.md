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

## Quick start (SQLite — no Docker)

```powershell
cd backend
pip install -r requirements.txt
# Optional: copy .env.example .env — defaults to SQLite

uvicorn app.main:app --reload --app-dir .
```

The API creates `backend/data/claimsense.db` on first start. Open http://127.0.0.1:8000/docs

Claims run **synchronously** if Redis is not running (Celery fallback).

## Postgres + Redis (optional, for pgvector / Celery)

```powershell
# From project root
docker compose up -d

cd backend
copy .env.example .env
# Edit .env: uncomment the Postgres DATABASE_URL line

uvicorn app.main:app --reload --app-dir .
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```

API docs: http://localhost:8000/docs

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
| `REDIS_URL` | `redis://localhost:6379/0` |
| `UPLOAD_DIR` | `uploads` |

Policy files are read from the project root (`policy_terms.json`, `adjudication_rules.md`).

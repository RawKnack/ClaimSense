# 🏥 ClaimSense — AI-Powered OPD Claim Adjudication Engine

> An AI-powered, end-to-end OPD insurance claim submission and automated adjudication system.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?style=flat&logo=next.js)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?style=flat&logo=postgresql)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker)](https://docker.com)

---

## 🎥 Live Application & Demo
- **Demo Video (YouTube):** [https://youtu.be/gW0DLJk8smc](https://youtu.be/gW0DLJk8smc) (Links to frontend, backend, and GitHub are also in the YouTube description)
- **Frontend (Vercel):** *(deploy and update URL)*
- **Backend API (Render):** *(deploy and update URL)*
- **GitHub Repository:** *(update with your repo URL)*
---

## 📖 Table of Contents

1. [Architecture Diagram](#1-architecture-diagram)
2. [System Architecture — Detailed Description](#2-system-architecture--detailed-description)
3. [Project Structure](#project-structure)
4. [API Documentation](#3-api-documentation)
5. [Decision Logic Flowchart](#4-decision-logic-flowchart)
6. [Rule Engine — Detailed Decision Logic](#5-rule-engine--detailed-decision-logic)
7. [Database Schema](#6-database-schema)
8. [AI/LLM Integration](#7-aillm-integration)
9. [OCR & Document Processing Pipeline](#8-ocr--document-processing-pipeline)
10. [Policy RAG (Retrieval-Augmented Generation)](#9-policy-rag-retrieval-augmented-generation)
11. [Test Cases & Expected Outcomes](#10-test-cases--expected-outcomes)
12. [List of Assumptions](#11-list-of-assumptions)
13. [Quick Start (Local)](#quick-start-local)
14. [Environment Variables](#environment-variables)
15. [Member Registry](#member-registry)
16. [Deployment Architecture](#12-deployment-architecture)
17. [Technology Stack Summary](#13-technology-stack-summary)

---

## 1. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            CLAIMSENSE OPD CLAIM ADJUDICATION                         │
│                                  System Architecture                                │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────┐        HTTPS / REST          ┌──────────────────────────────┐
│                               │ ─────────────────────────▶   │                              │
│   FRONTEND (Vercel)           │                              │   BACKEND (Render)            │
│                               │ ◀─────────────────────────   │                              │
│   Next.js 15 / React 19      │        JSON Responses         │   FastAPI / Python 3.12      │
│   TypeScript                  │                              │   Uvicorn ASGI Server         │
│   TanStack Query v5           │                              │                              │
│                               │                              │   ┌────────────────────────┐ │
│   ┌─────────────────────────┐ │                              │   │   API Layer             │ │
│   │  Claim Submission Form  │ │                              │   │   /api/v1/claims        │ │
│   │  • Member details       │ │                              │   │   /api/v1/health        │ │
│   │  • Treatment info       │ │                              │   └──────────┬─────────────┘ │
│   │  • Document uploads     │ │                              │              │               │
│   │  • Structured JSON      │ │                              │              ▼               │
│   └─────────────────────────┘ │                              │   ┌────────────────────────┐ │
│                               │                              │   │  Processing Pipeline    │ │
│   ┌─────────────────────────┐ │                              │   │                        │ │
│   │  Status Polling Page    │ │                              │   │  ┌──────────────────┐  │ │
│   │  • Auto-poll every 2s   │ │                              │   │  │  OCR Service     │  │ │
│   │  • Decision display     │ │                              │   │  │  (Tesseract +    │  │ │
│   │  • Rule-by-rule results │ │                              │   │  │  Google Vision)  │  │ │
│   └─────────────────────────┘ │                              │   │  └────────┬─────────┘  │ │
│                               │                              │   │           │            │ │
└───────────────────────────────┘                              │   │           ▼            │ │
                                                               │   │  ┌──────────────────┐  │ │
                                                               │   │  │  LLM Extraction  │  │ │
                                                               │   │  │  (Gemini 2.5     │  │ │
                                                               │   │  │  Flash via       │  │ │
                                                               │   │  │  OpenAI SDK)     │  │ │
                                                               │   │  └────────┬─────────┘  │ │
                                                               │   │           │            │ │
                                                               │   │           ▼            │ │
                                                               │   │  ┌──────────────────┐  │ │
                                                               │   │  │  Rule Engine     │  │ │
                                                               │   │  │  (Deterministic) │  │ │
                                                               │   │  │  8 rule checks   │  │ │
                                                               │   │  └────────┬─────────┘  │ │
                                                               │   │           │            │ │
                                                               │   │           ▼            │ │
                                                               │   │  ┌──────────────────┐  │ │
                                                               │   │  │  LLM Adjudicat.  │  │ │
                                                               │   │  │  (Medical        │  │ │
                                                               │   │  │  Necessity &     │  │ │
                                                               │   │  │  Exclusion Chk)  │  │ │
                                                               │   │  └────────┬─────────┘  │ │
                                                               │   │           │            │ │
                                                               │   │           ▼            │ │
                                                               │   │  ┌──────────────────┐  │ │
                                                               │   │  │  Policy RAG      │  │ │
                                                               │   │  │  (pgvector or    │  │ │
                                                               │   │  │  keyword search) │  │ │
                                                               │   │  └──────────────────┘  │ │
                                                               │   └────────────────────────┘ │
                                                               │              │               │
                                                               │              ▼               │
                                                               │   ┌────────────────────────┐ │
                                                               │   │   PostgreSQL 16        │ │
                                                               │   │   + pgvector extension │ │
                                                               │   │                        │ │
                                                               │   │   Tables:              │ │
                                                               │   │   • claims             │ │
                                                               │   │   • decisions          │ │
                                                               │   │   • extracted_fields   │ │
                                                               │   │   • policy_embeddings  │ │
                                                               │   └────────────────────────┘ │
                                                               └──────────────────────────────┘
```

---


---

## 2. System Architecture — Detailed Description

The system follows a **three-tier architecture** with a clear separation of concerns:

### 2.1 Frontend (Presentation Layer)
- **Framework:** Next.js 15 with React 19 and TypeScript
- **State Management:** TanStack Query v5 for server-state caching and auto-polling
- **Pages:**
  - **Claim Submission (`/`):** Multi-field form accepting member details, treatment info, structured document JSON, and file uploads (prescription, bill, diagnostic report)
  - **Claim Status (`/claims/[id]`):** Auto-polls the backend every 2 seconds until a decision is rendered, then displays the full adjudication result including rule-by-rule breakdown

### 2.2 Backend (Application Layer)
- **Framework:** FastAPI (Python 3.12) running on Uvicorn ASGI server
- **Architecture:** Modular service-oriented design with clearly separated concerns:
  - `api/` — Route handlers and request validation
  - `services/` — Business logic (OCR, LLM, rule engine, document pipeline, policy RAG)
  - `db/` — SQLAlchemy ORM models and database session management
  - `schemas/` — Pydantic request/response validation models
  - `workers/` — Background task processing
  - `core/` — Application configuration and settings

### 2.3 Data Layer
- **Database:** PostgreSQL 16 with `pgvector` extension for vector similarity search
- **ORM:** SQLAlchemy 2.0 with mapped columns
- **Tables:** `claims`, `decisions`, `extracted_fields`, `policy_embeddings`

### 2.4 External Services
- **Google Gemini 2.5 Flash** (via OpenAI-compatible SDK) — Used for document field extraction and medical necessity reasoning
- **Tesseract OCR** — Primary OCR engine for document text extraction
- **Google Cloud Vision API** — Fallback OCR when Tesseract confidence is low

---


---

## Project Structure

## Project Structure

```
claimsense/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── claims.py        # POST /claims, GET /claims/{id}
│   │   │   │   └── health.py        # GET /health
│   │   │   ├── deps.py              # FastAPI dependency injection
│   │   │   └── router.py            # API router aggregator
│   │   ├── core/
│   │   │   └── config.py            # Pydantic Settings (env vars)
│   │   ├── db/
│   │   │   ├── database.py          # SQLAlchemy engine + session
│   │   │   └── models.py            # ORM models: Claim, Decision, etc.
│   │   ├── schemas/
│   │   │   └── claim.py             # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── adjudication_pipeline.py  # Orchestrates full pipeline
│   │   │   ├── rule_engine.py            # 8 deterministic adjudication rules
│   │   │   ├── document_pipeline.py      # OCR + extraction orchestration
│   │   │   ├── policy_loader.py          # Loads policy_terms.json
│   │   │   ├── policy_rag.py             # pgvector semantic search
│   │   │   ├── storage.py               # File save/path management
│   │   │   ├── llm/
│   │   │   │   ├── extraction.py         # LLM field extraction from OCR
│   │   │   │   └── adjudication.py       # LLM adjudication reasoning
│   │   │   └── ocr/
│   │   │       ├── service.py            # Tesseract + PyMuPDF OCR
│   │   │       └── preprocess.py         # Image preprocessing
│   │   ├── workers/
│   │   │   └── tasks.py             # Sync task runner (process_claim)
│   │   └── main.py                  # FastAPI app factory + lifespan
│   ├── scripts/
│   │   └── run_test_cases.py        # CLI runner for test_cases.json
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx                 # Claim submission form
│   │   ├── layout.tsx               # Root layout + metadata
│   │   ├── globals.css              # Global styles
│   │   ├── providers.tsx            # TanStack Query provider
│   │   └── claims/[id]/page.tsx    # Claim status + decision page
│   ├── lib/
│   │   └── api.ts                   # Typed API client (fetch wrappers)
│   ├── Dockerfile
│   ├── next.config.ts
│   └── package.json
│
├── policy_terms.json                # Policy rules & coverage config
├── adjudication_rules.md            # Human-readable adjudication spec
├── test_cases.json                  # 10 structured test scenarios
├── docker-compose.yml               # Postgres + Backend + Frontend
├── render.yaml                      # Render.com deployment blueprint
└── README.md
```

---

---

## 3. API Documentation

**Base URL:** `http://localhost:8000/api/v1`

### 3.1 Health Check

```
GET /api/v1/health
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "service": "ClaimSense API",
  "database": "ok"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"ok"` or `"degraded"` |
| `service` | string | Application name ("ClaimSense API") |
| `database` | string | `"ok"` or `"unavailable"` |

---

### 3.2 Submit a Claim

```
POST /api/v1/claims
Content-Type: multipart/form-data
```

**Request Body (Form Data):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `member_id` | string | ✅ | Employee/member identifier (e.g., `EMP001`) |
| `member_name` | string | ✅ | Full name of the claimant |
| `treatment_date` | string | ✅ | Date of treatment (`YYYY-MM-DD`) |
| `claim_amount` | float | ✅ | Total claim amount in INR |
| `member_join_date` | string | ❌ | Member's policy join date (`YYYY-MM-DD`), resolved from registry if omitted |
| `hospital` | string | ❌ | Hospital name (for cashless/network checks) |
| `cashless_request` | string | ❌ | `"true"` or `"false"` — whether cashless settlement is requested |
| `previous_claims_same_day` | int | ❌ | Number of prior claims on same treatment date (auto-computed from DB) |
| `structured_documents` | string (JSON) | ❌* | JSON blob containing prescription and bill data |
| `prescription` | File | ❌* | Uploaded prescription image/PDF |
| `bill` | File | ❌* | Uploaded bill/receipt image/PDF |
| `diagnostic_report` | File | ❌ | Uploaded diagnostic report image/PDF |

> *At least one of `structured_documents` or file uploads (`prescription`/`bill`) must be provided.

**Response (202 Accepted):**
```json
{
  "claim_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "claim_number": "CLM_4F8A2B1C",
  "status": "COMPLETED",
  "message": "Claim adjudicated. Use GET /claims/{claim_id} for full decision."
}
```

---

### 3.3 Get Claim Status & Decision

```
GET /api/v1/claims/{claim_id}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `claim_id` | UUID | The claim ID returned from the submit endpoint |

**Response (200 OK):**
```json
{
  "claim_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "claim_number": "CLM_4F8A2B1C",
  "status": "COMPLETED",
  "member_id": "EMP001",
  "member_name": "Rajesh Kumar",
  "treatment_date": "2024-11-01",
  "claim_amount": 1500.0,
  "created_at": "2026-06-05T01:30:00Z",
  "updated_at": "2026-06-05T01:30:02Z",
  "error_message": null,
  "decision": {
    "claim_id": "a1b2c3d4-...",
    "claim_number": "CLM_4F8A2B1C",
    "decision": "APPROVED",
    "approved_amount": 1350.0,
    "rejection_reasons": [],
    "rejected_items": [],
    "deductions": { "copay": 150.0 },
    "flags": [],
    "confidence_score": 0.95,
    "notes": "Claim approved per policy terms. ...",
    "next_steps": "Reimbursement within 7 business days",
    "rule_results": [
      { "rule_name": "duplicate_bill", "passed": true, "reason_code": null, "note": null },
      { "rule_name": "minimum_amount", "passed": true, "reason_code": null, "note": null },
      { "rule_name": "required_documents", "passed": true, "reason_code": null, "note": null },
      { "rule_name": "doctor_registration", "passed": true, "reason_code": null, "note": null },
      { "rule_name": "waiting_period", "passed": true, "reason_code": null, "note": null },
      { "rule_name": "exclusions", "passed": true, "reason_code": null, "note": null },
      { "rule_name": "pre_authorization", "passed": true, "reason_code": null, "note": null },
      { "rule_name": "fraud_indicators", "passed": true, "reason_code": null, "note": null }
    ],
    "cashless_approved": false,
    "network_discount": null,
    "medical_necessity_established": true,
    "exclusions_detected": []
  },
  "extracted_fields": {
    "documents": { "prescription": { ... }, "bill": { ... } },
    "member_id": "EMP001",
    "claim_amount": 1500.0
  }
}
```

---

### 3.4 Get Decision Only

```
GET /api/v1/claims/{claim_id}/decision
```

Returns only the `DecisionOutputSchema` portion. Returns `202` if adjudication is still in progress.

---

### 3.5 Synchronous Adjudication (Testing)

```
POST /api/v1/claims/{claim_id}/adjudicate-sync
```

Re-runs adjudication synchronously on an existing claim. Useful for local testing without background workers.

---

### 3.6 Decision Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `claim_id` | string | UUID of the claim |
| `claim_number` | string | Human-readable claim number (e.g., `CLM_4F8A2B1C`) |
| `decision` | enum | `APPROVED`, `REJECTED`, `PARTIAL`, or `MANUAL_REVIEW` |
| `approved_amount` | float | Amount approved for reimbursement (₹) |
| `rejection_reasons` | list[string] | Reason codes (e.g., `MISSING_DOCUMENTS`, `WAITING_PERIOD`) |
| `rejected_items` | list[string] | Specific items rejected (e.g., cosmetic procedures) |
| `deductions` | dict | Breakdown of deductions (e.g., `{"copay": 150}`) |
| `flags` | list[string] | Fraud/review flags |
| `confidence_score` | float | System confidence in the decision (0.0–1.0) |
| `notes` | string | Detailed human-readable explanation of the decision |
| `next_steps` | string | Instructions for the claimant |
| `rule_results` | list | Per-rule pass/fail breakdown |
| `cashless_approved` | bool | Whether cashless settlement was approved |
| `network_discount` | float | Network discount amount applied (₹) |
| `medical_necessity_established` | bool | LLM assessment of medical necessity |
| `exclusions_detected` | list[string] | Policy exclusions detected by LLM |

---

### 3.7 Claim Status Lifecycle

| Status | Description |
|--------|-------------|
| `PENDING` | Claim received, queued for processing |
| `PROCESSING` | Adjudication pipeline is actively running |
| `COMPLETED` | Decision rendered (APPROVED / REJECTED / PARTIAL) |
| `MANUAL_REVIEW` | Flagged for human review (fraud indicators) |
| `FAILED` | Processing error (no documents, system failure) |

---

### 3.8 Error Responses

| HTTP Code | Scenario |
|-----------|----------|
| `400` | Invalid input (bad date format, missing documents, invalid JSON) |
| `404` | Claim ID not found |
| `202` | Decision not yet ready (adjudication in progress) |
| `500` | Internal server error during adjudication |

---


---

## 4. Decision Logic Flowchart

```
                        ┌──────────────────────┐
                        │   Claim Submitted     │
                        │   (POST /claims)      │
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │  Save to Database     │
                        │  Status → PENDING     │
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │  Prepare Documents    │
                        │  (Structured JSON     │
                        │   or OCR Pipeline)    │
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │  Status → PROCESSING  │
                        └──────────┬───────────┘
                                   │
                                   ▼
               ┌───────────────────────────────────────┐
               │         RULE ENGINE (Deterministic)   │
               │                                       │
               │  ┌─────────────────────────────────┐  │
               │  │ 1. Duplicate Bill Check         │──┼──▶ FAIL → REJECTED (DUPLICATE_CLAIM)
               │  └─────────────┬───────────────────┘  │
               │                │ PASS                 │
               │                ▼                      │
               │  ┌─────────────────────────────────┐  │
               │  │ 2. Minimum Amount Check (≥₹500) │──┼──▶ FAIL → REJECTED (BELOW_MIN_AMOUNT)
               │  └─────────────┬───────────────────┘  │
               │                │ PASS                 │
               │                ▼                      │
               │  ┌─────────────────────────────────┐  │
               │  │ 3. Required Documents Check     │──┼──▶ FAIL → REJECTED (MISSING_DOCUMENTS)
               │  │    (Prescription + Bill)        │  │
               │  └─────────────┬───────────────────┘  │
               │                │ PASS                 │
               │                ▼                      │
               │  ┌─────────────────────────────────┐  │
               │  │ 4. Doctor Registration Check    │──┼──▶ FAIL → REJECTED (DOCTOR_REG_INVALID)
               │  │    (Format: XX/NNNNN/YYYY)      │  │
               │  └─────────────┬───────────────────┘  │
               │                │ PASS                 │
               │                ▼                      │
               │  ┌─────────────────────────────────┐  │
               │  │ 5. Waiting Period Check         │──┼──▶ FAIL → REJECTED (WAITING_PERIOD)
               │  │    (Initial: 30d, Diabetes: 90d │  │
               │  │     Hypertension: 90d, etc.)    │  │
               │  └─────────────┬───────────────────┘  │
               │                │ PASS                 │
               │                ▼                      │
               │  ┌─────────────────────────────────┐  │
               │  │ 6. Exclusions Check             │──┼──▶ FAIL → REJECTED (SERVICE_NOT_COVERED)
               │  │    (Obesity, weight loss, etc.) │  │
               │  └─────────────┬───────────────────┘  │
               │                │ PASS                 │
               │                ▼                      │
               │  ┌─────────────────────────────────┐  │
               │  │ 7. Pre-Authorization Check      │──┼──▶ FAIL → REJECTED (PRE_AUTH_MISSING)
               │  │    (MRI/CT > ₹10,000)           │  │
               │  └─────────────┬───────────────────┘  │
               │                │ PASS                 │
               │                ▼                      │
               │  ┌─────────────────────────────────┐  │
               │  │ 8. Fraud Indicators Check       │──┼──▶ ≥3 claims same day → MANUAL_REVIEW
               │  │    (Multiple claims same day)   │  │
               │  └─────────────┬───────────────────┘  │
               │                │ PASS                 │
               │                ▼                      │
               │  ┌──────────────────────────── ────┐  │
               │  │ 9. Cosmetic Items Check         │──┼──▶ Cosmetic items found → PARTIAL
               │  │    (Whitening, cosmetic procs)  │  │     (Exclude cosmetic, approve rest)
               │  └─────────────┬───────────────────┘  │
               │                │ NO COSMETIC ITEMS    │
               │                ▼                      │
               │  ┌─────────────────────────────────┐  │
               │  │ 10. Per-Claim Limit Check       │──┼──▶ FAIL → REJECTED (PER_CLAIM_EXCEEDED)
               │  │     (Max ₹5,000 per claim)      │  │
               │  └─────────────┬───────────────────┘  │
               │                │ PASS                 │
               │                ▼                      │
               │  ┌─────────────────────────────────┐  │
               │  │ 11. Compute Approved Amount     │  │
               │  │     • Apply co-pay (10%)        │  │
               │  │     • Apply network discount    │  │
               │  │     • Apply sub-limits          │  │
               │  │     • Cap at per-claim limit    │  │
               │  └─────────────┬───────────────────┘  │
               │                │                      │
               │                ▼                      │
               │        PRELIMINARY → APPROVED         │
               └───────────────┬───────────────────────┘
                               │
                               ▼
               ┌───────────────────────────────────────┐
               │     LLM ADJUDICATION (Gemini 2.5)     │
               │                                       │
               │  • Evaluate medical necessity         │
               │  • Detect policy exclusions           │
               │  • Verify rule engine decision        │
               │  • Generate detailed notes            │
               │                                       │
               │  Can OVERRIDE rule engine:            │
               │  APPROVED → REJECTED (if excluded)    │
               │  APPROVED → MANUAL_REVIEW             │
               └───────────────┬───────────────────────┘
                               │
                               ▼
               ┌───────────────────────────────────────┐
               │         FINAL DECISION                │
               │                                       │
               │  APPROVED  → Status: COMPLETED        │
               │  REJECTED  → Status: COMPLETED        │
               │  PARTIAL   → Status: COMPLETED        │
               │  MANUAL_REVIEW → Status: MANUAL_REVIEW│
               └───────────────────────────────────────┘
```

---


---

## 5. Rule Engine — Detailed Decision Logic

The rule engine (`rule_engine.py`) executes **deterministic, auditable checks** in a strict sequential order. Any rule failure causes an **immediate rejection** (fail-fast), except for cosmetic checks and fraud indicators which have special handling.

### 5.1 Rule Execution Order

| # | Rule | What It Checks | Fail Action | Reason Code |
|---|------|----------------|-------------|-------------|
| 1 | **Duplicate Bill** | MD5 hash of bill data compared against all previous claims in DB | REJECT | `DUPLICATE_CLAIM` |
| 2 | **Minimum Amount** | `claim_amount >= ₹500` (configurable in policy_terms.json) | REJECT | `BELOW_MIN_AMOUNT` |
| 3 | **Required Documents** | Both `prescription` and `bill` must be present in the documents | REJECT | `MISSING_DOCUMENTS` |
| 4 | **Doctor Registration** | Registration number must match format `XX/NNNNN/YYYY` or `AYUR/XX/NNNNN/YYYY` | REJECT | `DOCTOR_REG_INVALID` |
| 5 | **Waiting Period** | Initial waiting: 30 days. Specific ailments: diabetes (90d), hypertension (90d), joint replacement (730d) | REJECT | `WAITING_PERIOD` |
| 6 | **Exclusions** | Keywords: obesity, weight loss, bariatric, diet plan | REJECT | `SERVICE_NOT_COVERED` |
| 7 | **Pre-Authorization** | MRI/CT scans with claim amount > ₹10,000 require pre-auth | REJECT | `PRE_AUTH_MISSING` |
| 8 | **Fraud Indicators** | ≥3 claims from same member on same treatment date | MANUAL_REVIEW | — |
| 9 | **Cosmetic Items** | Teeth whitening, cosmetic procedures detected in bill/prescription | PARTIAL | Cosmetic items excluded |
| 10 | **Per-Claim Limit** | `claim_amount <= ₹5,000` (skipped for dental claims with cosmetic deductions) | REJECT | `PER_CLAIM_EXCEEDED` |

### 5.2 Amount Computation Logic

After all rules pass, the approved amount is computed:

1. **Start** with `claim_amount`
2. **Subtract** cosmetic items (if any)
3. **Cap** at per-claim limit (₹5,000)
4. **Apply co-pay** (10% on consultation fees)
5. **Network discount** (20% if hospital is in-network + cashless requested)
6. **Alternative medicine sub-limit** (₹8,000 for Ayurveda/Panchakarma)

### 5.3 Confidence Scores

| Decision Type | Confidence |
|---------------|-----------|
| Missing documents rejection | 1.00 |
| Per-claim limit exceeded | 0.98 |
| Standard rejection (waiting period, exclusion, etc.) | 0.96 |
| Standard approval | 0.95 |
| Network/cashless approval | 0.93 |
| Partial approval (cosmetic excluded) | 0.92 |
| Alternative medicine approval | 0.89 |
| Manual review (fraud detected) | 0.65 |

---


---

## 6. Database Schema

### 6.1 Entity Relationship

```
┌──────────────────────┐       1:1       ┌──────────────────────┐
│       claims         │ ────────────▶  │      decisions       │
│                      │                 │                      │
│  id (PK, UUID)       │                 │  id (PK, UUID)       │
│  claim_number        │                 │  claim_id (FK, UUID) │
│  status              │                 │  decision_payload    │
│  member_id           │                 │  created_at          │
│  member_name         │                 └──────────────────────┘
│  member_join_date    │
│  treatment_date      │       1:1       ┌──────────────────────┐
│  claim_amount        │ ────────────▶   │  extracted_fields    │
│  hospital            │                 │                      │
│  cashless_request    │                 │  id (PK, UUID)       │
│  previous_claims     │                 │  claim_id (FK, UUID) │
│  metadata_extra      │                 │  ocr_result (JSON)   │
│  document_paths      │                 │  extracted_data      │
│  error_message       │                 │  field_confidence    │
│  created_at          │                 │  created_at          │
│  updated_at          │                 └──────────────────────┘
└──────────────────────┘

┌──────────────────────┐
│  policy_embeddings   │   (Standalone — policy RAG)
│                      │
│  id (PK, UUID)       │
│  chunk_id (unique)   │
│  source              │
│  text                │
│  embedding (384-dim) │   ← pgvector Vector(384)
│  created_at          │
└──────────────────────┘
```

### 6.2 Table Details

#### `claims`
Stores every submitted claim and its lifecycle status.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | Auto-generated |
| `claim_number` | VARCHAR(32) | Unique, format: `CLM_XXXXXXXX` |
| `status` | ENUM | `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`, `MANUAL_REVIEW` |
| `member_id` | VARCHAR(64) | Indexed for lookup |
| `member_name` | VARCHAR(255) | |
| `member_join_date` | VARCHAR(32) | Nullable, resolved from registry if not provided |
| `treatment_date` | VARCHAR(32) | `YYYY-MM-DD` |
| `claim_amount` | FLOAT | In INR |
| `hospital` | VARCHAR(255) | Nullable |
| `cashless_request` | BOOLEAN | Default: false |
| `metadata_extra` | JSON | Stores structured documents, file hashes |
| `document_paths` | JSON | Paths to uploaded files |
| `error_message` | TEXT | Nullable, populated on FAILED status |
| `created_at` | TIMESTAMP | Server-generated |
| `updated_at` | TIMESTAMP | Auto-updated |

#### `decisions`
Stores the full adjudication decision payload for each claim.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | Auto-generated |
| `claim_id` | UUID (FK) | One-to-one with `claims` |
| `decision_payload` | JSON | Full decision output (verdict, amounts, rule results, notes) |
| `created_at` | TIMESTAMP | |

#### `extracted_fields`
Stores OCR output and extracted structured data.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | Auto-generated |
| `claim_id` | UUID (FK) | One-to-one with `claims` |
| `ocr_result` | JSON | Raw OCR output (nullable) |
| `extracted_data` | JSON | Structured extraction (documents, member_id, claim_amount) |
| `field_confidence` | JSON | Per-field confidence scores |
| `created_at` | TIMESTAMP | |

#### `policy_embeddings`
Stores chunked policy text with vector embeddings for semantic retrieval (RAG).

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | Auto-generated |
| `chunk_id` | VARCHAR(64) | Unique identifier for each chunk |
| `source` | VARCHAR(128) | Source file (e.g., `policy_terms.json`, `adjudication_rules.md`) |
| `text` | TEXT | Chunk content |
| `embedding` | VECTOR(384) | 384-dimensional vector (all-MiniLM-L6-v2 model) |
| `created_at` | TIMESTAMP | |

---

---

## 7. AI/LLM Integration

### 7.1 Two-Stage AI Pipeline

The system uses AI at two distinct stages:

#### Stage 1: Document Field Extraction (`llm/extraction.py`)
- **Purpose:** Extract structured fields (doctor name, registration, diagnosis, medicines, bill items) from raw OCR text
- **Model:** Gemini 2.5 Flash (via OpenAI-compatible SDK)
- **Fallback:** Regex-based heuristic extraction when no API key is configured
- **Output Schema:**
  ```json
  {
    "prescription": {
      "doctor_name": "str|null",
      "doctor_reg": "str|null",
      "diagnosis": "str|null",
      "medicines_prescribed": ["str"]
    },
    "bill": { "<line_item>": number },
    "field_confidence": { "<field_path>": 0.0-1.0 }
  }
  ```
#### Stage 2: Adjudication Reasoning (`llm/adjudication.py`)
- **Purpose:** Evaluate medical necessity, detect policy exclusions, and provide detailed reasoning
- **Input:** Claim details + rule engine preliminary outcome + retrieved policy context (RAG)
- **Model:** Gemini 2.5 Flash
- **Override Logic:** LLM can escalate a rule-engine APPROVED decision to REJECTED or MANUAL_REVIEW if it detects excluded conditions or lack of medical necessity
- **Fallback:** If no API key or LLM call fails, the system returns the deterministic rule engine outcome with a system info note

### 7.2 Graceful Degradation

The system is designed to work **without any API key**:
1. OCR falls back to Tesseract-only (no Google Vision fallback)
2. Field extraction falls back to regex/heuristic patterns
3. LLM adjudication is skipped; the deterministic rule engine outcome is used directly
4. Structured JSON input bypasses OCR + LLM extraction entirely

---


---

## 8. OCR & Document Processing Pipeline

### 8.1 Pipeline Flow

```
Uploaded File (Image/PDF)
         │
         ▼
┌─────────────────────────┐
│   File Loading           │
│   • Images: OpenCV       │
│   • PDFs: PyMuPDF        │
│     (renders each page   │
│      at 200 DPI)         │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Preprocessing         │
│   • Grayscale conversion│
│   • Noise denoising     │
│   • Adaptive threshold  │
│   • Deskew correction   │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Tesseract OCR         │
│   • Full text extraction│
│   • Per-word confidence │
│   • Average confidence  │
│     calculation         │
└────────────┬────────────┘
             │
             ▼
        confidence < 0.60
        OR text too short?
         │            │
        YES           NO
         │            │
         ▼            ▼
┌─────────────┐  ┌──────────┐
│ Google       │  │ Use      │
│ Vision API   │  │ Tesseract│
│ Fallback     │  │ result   │
└──────┬──────┘  └────┬─────┘
       │               │
       └───────┬───────┘
               │
               ▼
┌─────────────────────────┐
│   LLM Field Extraction   │
│   (Gemini 2.5 Flash)     │
│   OR Heuristic fallback  │
└─────────────────────────┘
```

### 8.2 Supported File Types
- **Images:** `.jpg`, `.jpeg`, `.png`, `.webp`, `.tiff`
- **Documents:** `.pdf` (multi-page support via PyMuPDF)
- **Max file size:** 10 MB

---


---

## 9. Policy RAG (Retrieval-Augmented Generation)

### 9.1 What It Does

The Policy RAG system provides **contextual policy information** to the LLM during adjudication. Instead of sending the entire policy document, it retrieves the most relevant policy chunks based on the claim's diagnosis and treatment.

### 9.2 How It Works

1. **Chunking:** On startup, `policy_terms.json` and `adjudication_rules.md` are split into overlapping chunks (~100 words each)
2. **Embedding:** Each chunk is embedded using the `all-MiniLM-L6-v2` sentence-transformer model (384-dimensional vectors)
3. **Storage:** Embeddings are stored in the `policy_embeddings` table using PostgreSQL's `pgvector` extension
4. **Retrieval:** During adjudication, the diagnosis/treatment text is embedded, and the top-3 most similar policy chunks are retrieved via cosine distance
5. **Fallback:** If pgvector is unavailable, keyword-overlap scoring is used

### 9.3 Retrieval Strategy

```
Claim: "Type 2 Diabetes treatment"
         │
         ▼
    Embed query text
         │
         ▼
    SELECT * FROM policy_embeddings
    ORDER BY embedding <=> query_vector
    LIMIT 3
         │
         ▼
    Returns: chunks about waiting periods,
             diabetes-specific waiting (90 days),
             covered services
```

---


---

## 10. Test Cases & Expected Outcomes

The system is designed to handle all 10 test cases from `test_cases.json`:

| Case | Name | Expected Decision | Key Check |
|------|------|-------------------|-----------|
| TC001 | Simple Consultation | ✅ APPROVED (₹1,350) | Standard flow with 10% copay |
| TC002 | Dental + Cosmetic | ⚠️ PARTIAL (₹8,000) | Teeth whitening excluded, root canal approved |
| TC003 | Limit Exceeded | ❌ REJECTED | Claim ₹7,500 exceeds per-claim limit of ₹5,000 |
| TC004 | Missing Documents | ❌ REJECTED | No prescription submitted |
| TC005 | Diabetes Waiting Period | ❌ REJECTED | 90-day specific ailment waiting period not met |
| TC006 | Ayurvedic Treatment | ✅ APPROVED (₹4,000) | Alternative medicine within ₹8,000 sub-limit |
| TC007 | MRI Without Pre-Auth | ❌ REJECTED | MRI > ₹10,000 requires pre-authorization |
| TC008 | Fraud — Same Day Claims | 🔍 MANUAL_REVIEW | 3+ claims on same day triggers manual review |
| TC009 | Weight Loss Treatment | ❌ REJECTED | Obesity/bariatric/weight loss are excluded |
| TC010 | Network Hospital Cashless | ✅ APPROVED (₹3,600) | Apollo Hospitals → 20% network discount |

---

---


## 11. List of Assumptions

### 11.1 Member & Policy Assumptions
1. **Single Policy:** All members belong to a single employer policy (`OPD_POLICY_2024` — TechCorp Solutions Pvt Ltd) with identical terms
2. **Member Registry:** A hardcoded registry of 10 employees (EMP001–EMP010) is used for member verification and join date resolution. In production, this would be replaced by a database-backed member management system
3. **Policy Always Active:** The policy is assumed to be active throughout the claim dates in the test cases (effective from 2024-01-01). No explicit policy expiry check is implemented
4. **No Dependents Logic:** While the policy supports dependents, the current MVP does not implement dependent verification

### 11.2 Document Processing Assumptions
5. **Structured JSON is Trusted:** When structured document JSON is provided via the form, it is treated as a "pre-extracted" and trusted source (skipping OCR entirely). This simulates claims submitted via structured API integrations
6. **OCR Accuracy:** Tesseract OCR with OpenCV preprocessing is assumed to provide a reasonable baseline. A confidence threshold of 60% triggers the Google Vision API fallback
7. **Single Document Per Type:** Each claim can have at most one prescription, one bill, and one diagnostic report. Multiple prescriptions in a single claim are not supported
8. **PDF Multi-Page Support:** All pages of a PDF are OCR'd and concatenated. It is assumed that each uploaded PDF contains a single document type

### 11.3 Adjudication Logic Assumptions
9. **Fail-Fast Rule Engine:** Rules are evaluated sequentially. The first failing rule triggers an immediate rejection with a single reason code. Multiple simultaneous failures are not reported (only the first)
10. **Duplicate Detection by Bill Hash:** Duplicate bill detection uses MD5 hashing of the structured bill JSON or uploaded file. Visually identical bills with different file encodings may not be detected
11. **Same-Day Claims Auto-Count:** The number of same-day claims for fraud detection is automatically computed from the database by counting existing claims with the same `member_id` and `treatment_date`
12. **Doctor Registration Format:** Doctor registration numbers must match the pattern `XX/NNNNN/YYYY` (state code / number / year) or `AYUR/XX/NNNNN/YYYY` for Ayurvedic practitioners. Other valid formats may be incorrectly rejected
13. **Cosmetic Detection by Keyword:** Cosmetic procedures are detected by keyword matching (`whitening`, `cosmetic`) in bill item keys and prescription procedures. Subtle cosmetic procedures without these keywords may not be caught
14. **Per-Claim Limit vs. Dental:** The per-claim limit check (₹5,000) is skipped for dental claims that have cosmetic deductions, since the approved amount after deducting cosmetic items typically falls within limits
15. **Network Discount Overrides Co-pay:** When a claim qualifies for the 20% network discount (in-network hospital + cashless request), the co-pay deduction is not applied — the network discount replaces it

### 11.4 LLM & AI Assumptions
16. **LLM as a Safety Net:** The LLM adjudication layer can only escalate decisions (APPROVED → REJECTED or MANUAL_REVIEW), never downgrade a rejection. This ensures the deterministic rule engine remains the primary authority
17. **Gemini as OpenAI-Compatible:** The system uses the OpenAI Python SDK (`openai` package) pointed at Google's Gemini endpoint (`generativelanguage.googleapis.com/v1beta/openai/`). The `OPENAI_API_KEY` environment variable should contain a **Google Gemini API key**, not an OpenAI key
18. **Graceful Degradation Without API Key:** If no API key is set, both LLM extraction and LLM adjudication are skipped. The system falls back to heuristic extraction and deterministic rule engine outcomes. This ensures the application remains fully functional without external API dependencies

### 11.5 Infrastructure Assumptions
19. **Free Tier Limitations:** Render's free tier spins down web services after 15 minutes of inactivity. The first request after idle may take ~50 seconds as the container cold-starts
20. **No File Persistence on Free Tier:** Uploaded files are stored on the ephemeral container filesystem. On Render's free tier, files may be lost on container restart. For production, S3-compatible storage (configurable via `USE_S3` setting) should be enabled
21. **pgvector Availability:** The `pgvector` extension is required for semantic policy retrieval. If unavailable, the system gracefully removes the `PolicyEmbedding` table and falls back to keyword-overlap retrieval
22. **No Celery/Redis:** Background processing uses synchronous in-request execution (the `process_claim` function runs inline). In a production system, this would be replaced by a Celery + Redis task queue for true asynchronous processing

---


---

## Quick Start (Local)

## Quick Start (Local)

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- **OR** Python 3.12+ and Node.js 20+ for manual setup

---

### Option A: Docker Compose (Recommended)

Spin up PostgreSQL, the backend, and the frontend with a single command:

```powershell
# From the project root
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend UI | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| API Docs (ReDoc) | http://localhost:8000/redoc |

To stop all services:
```powershell
docker compose down
```

To wipe the database volume and start fresh:
```powershell
docker compose down -v
```

---

### Option B: Manual Setup

#### 1. Start PostgreSQL

```powershell
docker run -d --name claimsense-postgres `
  -e POSTGRES_USER=claimsense `
  -e POSTGRES_PASSWORD=claimsense `
  -e POSTGRES_DB=claimsense_db `
  -p 5433:5432 `
  pgvector/pgvector:pg16
```

#### 2. Backend

```powershell
cd backend

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env and set DATABASE_URL and optionally GEMINI_API_KEY

# Start the server
uvicorn app.main:app --reload --app-dir .
```

Backend available at: http://127.0.0.1:8000

#### 3. Frontend

```powershell
cd frontend

# Install dependencies
npm install

# Configure environment
echo "NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1" > .env.local

# Start the dev server
npm run dev
```

Frontend available at: http://localhost:3000

> Keep **both** terminals running simultaneously.

---

---

## Environment Variables

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://claimsense:claimsense@localhost:5433/claimsense_db` | PostgreSQL connection string. Use `sqlite:///./data/claimsense.db` for SQLite (no pgvector) |
| `UPLOAD_DIR` | `uploads` | Directory where uploaded claim documents are stored |
| `DEBUG` | `false` | Enable debug mode |
| `OPENAI_API_KEY` | *(empty)* | **Primary AI key**: Used for LLM extraction & adjudication (can be a Gemini key — the backend routes to Gemini's OpenAI-compatible endpoint) |
| `GEMINI_API_KEY` | *(empty)* | Alternative key specifically for Google Gemini |
| `GOOGLE_VISION_API_KEY` | *(empty)* | Alternative key if using Google Vision |
| `USE_S3` | `false` | Enable S3 file storage instead of local filesystem |
| `AWS_ACCESS_KEY_ID` | *(empty)* | AWS credentials for S3 storage |
| `AWS_SECRET_ACCESS_KEY` | *(empty)* | AWS credentials for S3 storage |
| `AWS_S3_BUCKET` | *(empty)* | S3 bucket name |
| `AWS_REGION` | `ap-south-1` | AWS region |
| `MAX_UPLOAD_SIZE_MB` | `10` | Maximum file size for document uploads |

> **Note on AI Keys**: Set `OPENAI_API_KEY` to your **Google Gemini API key**. The backend uses Gemini via the `https://generativelanguage.googleapis.com/v1beta/openai/` compatible endpoint with the `gemini-2.5-flash` model. If no key is provided, the system falls back to heuristic regex-based extraction and rule-only adjudication — no AI features will be active.

### Frontend (`frontend/.env.local`)

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000/api/v1` | Base URL of the backend API |

---

---

## Member Registry

## Member Registry

The system includes a built-in registry of 10 test employees with their policy join dates for waiting period validation:

| Member ID | Name | Join Date |
|---|---|---|
| `emp001` | Rajesh Kumar | 2024-01-01 |
| `emp002` | Priya Singh | 2024-01-01 |
| `emp003` | Amit Verma | 2024-01-01 |
| `emp004` | Sneha Reddy | 2024-01-01 |
| `emp005` | Vikram Joshi | 2024-09-01 *(shorter tenure)* |
| `emp006` | Kavita Nair | 2024-01-01 |
| `emp007` | Suresh Patil | 2024-01-01 |
| `emp008` | Ravi Menon | 2024-01-01 |
| `emp009` | Anita Desai | 2024-01-01 |
| `emp010` | Deepak Shah | 2024-01-01 |

> Members not in the registry will have waiting period checks skipped (join date unknown).

---

---

## 12. Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        INTERNET                             │
└───────────────────┬─────────────────────┬───────────────────┘
                    │                     │
                    ▼                     ▼
        ┌───────────────────┐  ┌────────────────────┐
        │     VERCEL        │  │      RENDER         │
        │                   │  │                    │
        │  Next.js 15       │  │  ┌──────────────┐  │
        │  Frontend         │  │  │ FastAPI      │  │
        │  (SSR + Static)   │  │  │ Backend      │  │
        │                   │  │  │ (Docker)     │  │
        │  ENV:             │  │  └──────┬───────┘  │
        │  NEXT_PUBLIC_     │  │         │          │
        │  API_URL ─────────┼──┼─────────┘          │
        │                   │  │                    │
        └───────────────────┘  │  ┌──────────────┐  │
                               │  │ PostgreSQL   │  │
                               │  │ 16 + pgvector│  │
                               │  │ (Managed)    │  │
                               │  └──────────────┘  │
                               │                    │
                               │  ENV:              │
                               │  DATABASE_URL      │
                               │  OPENAI_API_KEY    │
                               └────────────────────┘
```

### Local Development

For local development, `docker-compose.yml` provides a complete environment:
```bash
docker compose up
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# PostgreSQL: localhost:5433
```

---


---

## 13. Technology Stack Summary

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Frontend** | Next.js | 15 | React framework with SSR |
| | React | 19 | UI components |
| | TypeScript | 5.7+ | Type safety |
| | TanStack Query | 5 | Server-state caching & auto-polling |
| **Backend** | FastAPI | 0.115+ | Async Python web framework |
| | Python | 3.12 | Runtime |
| | Uvicorn | 0.32+ | ASGI server |
| | SQLAlchemy | 2.0+ | ORM |
| | Pydantic | 2.10+ | Request/response validation |
| **Database** | PostgreSQL | 16 | Relational database |
| | pgvector | 0.3.6+ | Vector similarity search |
| **AI/ML** | Google Gemini 2.5 Flash | — | LLM for extraction & reasoning |
| | OpenAI SDK | 1.55+ | API client (Gemini-compatible) |
| | sentence-transformers | 3.0+ | Embedding model for RAG |
| **OCR** | Tesseract | 5.x | Primary OCR engine |
| | OpenCV | 4.10+ | Image preprocessing |
| | PyMuPDF | 1.24+ | PDF rendering |
| | Pillow | 11+ | Image I/O |
| | Google Vision API | — | Fallback OCR (optional) |
| **DevOps** | Docker | — | Containerization |
| | docker-compose | — | Local multi-service orchestration |
| | Render | — | Backend + DB hosting (Blueprint) |
| | Vercel | — | Frontend hosting |

---

*Built as a personal project to demonstrate AI-powered insurance claim processing.*

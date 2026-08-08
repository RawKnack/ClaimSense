# ClaimSense — Frontend

Next.js UI for claim submission and status polling.

## Setup

```powershell
cd frontend
npm install
copy .env.local.example .env.local
npm run dev
```

Open http://localhost:3000 (API should run on http://127.0.0.1:8000).

## Pages

- `/` — Submit claim (JSON and/or file uploads)
- `/claims/[id]` — Poll status until `COMPLETED`, show decision

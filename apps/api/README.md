---
title: RankPilot AI API
emoji: 🚀
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# RankPilot AI — API

FastAPI backend for RankPilot AI. This single container runs **Redis**, the
**ARQ worker**, and the **API** together (see `Dockerfile` + `start.sh`), so it
deploys as one Hugging Face Docker Space.

## Deploy to a Hugging Face Docker Space

1. Create a new Space → **SDK: Docker** (blank template).
2. Push the contents of `apps/api/` to the Space repo (this folder, with the
   `Dockerfile`, `start.sh`, and `README.md`).
3. In **Settings → Variables and secrets**, add:

   | Name | Type | Example / notes |
   |------|------|-----------------|
   | `DATABASE_URL` | secret | `postgresql+psycopg://USER:PASS@HOST/db?sslmode=require` (Neon) |
   | `SECRET_KEY` | secret | long random string (signs the API's JWTs) |
   | `OPENAI_API_KEY` | secret | your OpenAI key |
   | `OPENAI_MODEL` | variable | `gpt-4o` (optional) |
   | `BACKEND_CORS_ORIGINS` | variable | your frontend URL, e.g. `https://yourapp.vercel.app` |

   Do **not** set `REDIS_URL` — it defaults to the in-container Redis
   (`redis://127.0.0.1:6379`).

4. The Space builds the image and starts everything. Health check:
   `https://<your-space>.hf.space/health` → `{"status":"ok"}`.

## Notes
- Redis here is **in-memory / ephemeral** (wiped on restart/sleep). That's fine
  for a job queue; durable data lives in Postgres. Free Spaces sleep on
  inactivity — the first request after sleep will be slow while it wakes.
- Point the frontend's `NEXT_PUBLIC_API_URL` (or equivalent) at the Space URL.

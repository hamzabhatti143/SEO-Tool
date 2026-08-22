# RankPilot AI

An AI-powered SEO SaaS platform. The MVP ships three core modules:

1. **Website Audit** — crawl a URL and check meta tags, heading
   structure, broken links, and page-speed basics (deterministic, no AI).
2. **Keyword Research** — given a seed keyword, an OpenAI agent generates
   related keywords, long-tail variations, and search intent.
3. **AI Content Studio** — generate an SEO-optimized blog post (title,
   meta description, Markdown body) from a topic and target keyword.

The AI logic (modules 2 and 3) is built on the **OpenAI Agents SDK** with
structured (typed) outputs.

This repository is a **monorepo** containing the web frontend, the API
backend, and shared code, so the whole product can be developed,
versioned, and reasoned about in one place.

## MVP modules → endpoints

| Module              | Endpoint                              | AI  | Stored |
| ------------------- | ------------------------------------- | --- | ------ |
| Website Audit       | `POST /api/v1/audits`                 | No  | Yes    |
| Core Web Vitals     | `POST /api/v1/audit/core-web-vitals`  | No  | Yes    |
| Platform Connectors | `POST …/connectors/wordpress/connect` · `…/shopify/install` · `…/shopify/callback` | No | Yes |
| CWV Fix Orchestration | `POST …/projects/{id}/cwv/fix-all` · `…/cwv/revert/{change_id}` | No | Yes |
| On-Page Optimizer   | `POST /api/v1/optimizer/analyze`      | Yes | No     |
| Keyword Research    | `POST /api/v1/keywords/research`      | Yes | Yes    |
| Competitor Intel    | `POST /api/v1/competitors/analyze`    | Yes | No     |
| Content Gap Analysis| `POST /api/v1/gap-analysis/analyze`   | Yes | No     |
| Internal Link Opt.  | `POST /api/v1/internal-links/crawl` · `GET …/analysis` | Yes | Yes |
| Rank Tracking       | `…/rank-tracking/keywords` · `…/history` · `…/refresh` | No  | Yes |
| Backlink Center     | `POST …/backlinks/profile` · `…/broken-links` | No  | No  |
| AI Content Studio   | `POST /api/v1/content/generate[/stream]` | Yes | Yes |
| Reports             | `GET …/reports/{id}/pdf` · `…/html`   | No  | —      |
| AI SEO Assistant    | `POST …/assistant/chat` (SSE)         | Yes | No     |
| Automation          | `…/automation/settings` · `…/run`     | No  | Yes    |
| Agency Mode         | `…/agency/*` · `…/invites/accept` · `…/public/share/*` | No | Yes |

AI frameworks: Keyword Research, the On-Page Optimizer's LSI/missing-keyword
suggestions, Competitor Intel, Content Gaps, and the AI SEO Assistant use the
**OpenAI Agents SDK**; the Content Studio uses **LangChain** (streamed via
SSE).

The AI SEO Assistant is a **chat sidebar** (floating widget on every
dashboard page) backed by the Agents SDK with **function-calling tools**.
Each tool (`get_latest_audit`, `get_tracked_rankings`, `get_keywords`,
`get_content`, `get_project_overview`) is scoped to the current project via
the agent run context and reads that project's real data from the DB — so
asking "why is my page not ranking?" pulls the actual audit issues and rank
history rather than guessing. Replies **stream over SSE**, and the UI shows
which data tool the assistant is using in real time.

Keyword Research also enriches results with **topic clustering**
(`text-embedding-3-small` embeddings + greedy cosine-similarity grouping,
with AI-generated cluster labels) and a **Google Trends** signal via
`pytrends` (a free alternative to paid volume data). Trends are
best-effort: pytrends is rate-limited, so it runs off the event loop in a
threadpool, batched 5 terms at a time and capped by
`KEYWORD_TREND_MAX_TERMS` — throttled terms simply come back without a
trend rather than failing the request.

Core Web Vitals extends the Website Audit module with a **performance
detection engine** backed by the **Google PageSpeed Insights (PSI) API v5** —
no local browser. `POST /audit/core-web-vitals` calls `…/runPagespeed` for the
URL requesting **all four categories** (`performance`, `accessibility`,
`best-practices`, `seo`), `strategy` `mobile` (default) or `desktop`, and
extracts:

- **Lab timing metrics** — **FCP, LCP, TBT, CLS, Speed Index** — from
  `lighthouseResult.audits` (`numericValue`). INP is **not** read from lab
  audits (it doesn't exist in simulated runs).
- **Field INP** — only from `loadingExperience.metrics.INTERACTION_TO_NEXT_PAINT`
  (real Chrome users). Shown as **"No field data available"** when absent —
  never a fake 0.
- **Four category scores** (each `score` ×100).
- **Insights / Diagnostics / Passed** — each category's `auditRefs` classified:
  opportunities-with-savings → Insights (with "Est savings"), other
  failing/informational → Diagnostics, `score == 1` → Passed.
- **Screenshots** — the load-timeline thumbnails and the final screenshot.

For accuracy the call runs **`PAGESPEED_RUNS` times (default 2)** and stores the
**median** of each metric plus every individual run for transparency. The scan
is **synchronous** (≈30–60s) and persists a `core_web_vitals` row (the median
metrics + four scores as columns, and the full report — insights, diagnostics,
passed, screenshots, metadata, runs — in `report_json`). The UI mirrors
pagespeed.web.dev: four color-coded score circles, a large Performance circle +
screenshot, a metrics grid, timeline thumbnails, and expandable
Insights/Diagnostics/Passed sections per category. Rate limits (free tier:
25k/day, 240/min) surface as HTTP 429 and are retried with backoff. Set
**`PAGESPEED_API_KEY`** in the environment (never hardcoded).

Platform Connectors link a project to **WordPress** or **Shopify** so
RankPilot can read/push SEO changes. A project carries a **`platform`** field
(`wordpress` | `shopify` | `custom`) and at most one **`credentials`** row,
whose secret is **encrypted at rest** with Fernet (`app.core.crypto`) and
never returned by the API. The unified **"Connect Your Site"** page offers a
WordPress/Shopify card, each leading to its flow:

- **WordPress**: the user installs the RankPilot plugin (in
  `wordpress-plugin/rankpilot-connector/` — see its README), which generates an
  API key shown under **Settings → RankPilot**. They paste the site URL + key,
  and `POST /connectors/wordpress/connect` verifies it by calling the plugin's
  health-check (`GET {site}/wp-json/rankpilot/v1/health` with the key as a
  Bearer token) — credentials are stored **only if the check passes**.
- **Shopify**: a standard **Admin API OAuth** install (scopes `read_themes`,
  `write_themes`, `read_products`, `write_products`). `POST
  /connectors/shopify/install` returns the authorize URL (state is a signed,
  short-lived JWT carrying the project id); Shopify redirects the browser to
  the public `GET /connectors/shopify/callback`, which **verifies the HMAC**
  and signed state, exchanges the code for an access token, stores the token +
  shop domain, and bounces back to the Connect page.

Shopify needs `SHOPIFY_API_KEY`/`SHOPIFY_API_SECRET` (Partner dashboard) and a
publicly reachable `APP_BASE_URL` for the OAuth `redirect_uri`; set
`CREDENTIALS_ENCRYPTION_KEY` in production (it's derived from `SECRET_KEY`
otherwise).

CWV Fix Orchestration applies (and reverts) automated Core Web Vitals fixes
across platforms. `POST /projects/{id}/cwv/fix-all` reads the project's
**`platform`** field and routes to the matching handler — **WordPress** or
**Shopify** — then triggers a **re-scan** (the shared `scan_and_store` write
path, so a new `core_web_vitals` row is stored) and records a **`change_log`**
row: the platform's revert handle (`external_change_id` = a WordPress change id
or a Shopify backup theme id), before/after snapshots, and the CWV score on
either side. `POST /projects/{id}/cwv/revert/{change_id}` routes the same way to
the revert handler and re-scans. The platform handlers are **stubbed** (mock
responses with clear TODOs) until the WordPress plugin and Shopify app expose
their fix endpoints — the orchestration flow (routing, logging, re-scan) is
complete and tested around them. The re-scan is **best-effort**: if it can't
run, the fix is still logged (`rescan_status: "failed"`) rather than lost.

The On-Page Optimizer is a **stateless** analysis endpoint (URL + target
keyword, authenticated but not persisted): it checks meta title/description,
H1–H6, keyword placement & density, internal/external links & anchor text,
image alt tags, and readability (via `textstat`), then returns a 0–100 score
with categorized suggestions plus AI LSI/missing-keyword recommendations.

Competitor Intel is also **stateless**: it does a bounded multi-page crawl
of a competitor (titles, headings, page count, internal-link structure, and
a best-effort `/sitemap.xml` count), then the OpenAI Agents SDK infers the
competitor's content strategy and topic focus and compares it against the
user's project keywords/content to surface **keyword gaps** and **content
gaps**. It uses **no paid API** — every traffic/authority figure is clearly
labeled **"AI Estimated"** in the UI, never presented as SEMrush/Ahrefs data.

Content Gap Analysis (**stateless**) crawls 2–3 competitors (reusing the
competitor crawler, concurrently), cross-references their coverage against
the project, and returns **missing topics**, **missing FAQs**, and a
prioritized set of **content briefs** (title, target keyword, outline, word-
count target). The UI is a **kanban board** grouped by priority; each
opportunity card deep-links into the AI Content Studio with the topic,
keyword, and content type pre-filled via query params.

Internal Link Optimizer is **stateful**: `POST /internal-links/crawl`
crawls the project's own site and persists each page (title, content
summary, `text-embedding-3-small` embedding, and outbound internal links)
to the `project_pages` table. `GET /internal-links/analysis` then builds the
internal-link graph, flags **orphan pages** (no inbound internal links), and
suggests **semantic linking opportunities** ("Page A → Page B" with anchor
text) via embedding cosine similarity. The UI renders the graph with
**react-flow** plus a suggestions table.

Automation is **stateful + scheduled**: per-project settings
(`automation_settings`) toggle a **weekly audit re-run**, **daily broken-link
monitoring**, and **weekly competitor content-change detection** (SHA-256
diff of crawled titles/headings). Three **ARQ cron jobs** (in the worker
process) run these alongside rank tracking — each opens its own session and
is best-effort per project. Running cron in the single worker (not the web
process) means they fire exactly once regardless of web-replica count. Email notifications go out via **Resend** for **rank drops > 5
positions**, **new broken links**, and a **weekly summary**; without a
`RESEND_API_KEY` emails are logged/skipped. A Settings page toggles
everything per project, with "Run now" buttons for on-demand execution.

Rank Tracking is **stateful + scheduled**: users add tracked keywords
(`tracked_keywords`), and an **ARQ** daily cron queries each
keyword's SERP position via **SerpApi** (ToS-compliant — no direct Google
scraping), storing a dated `rank_snapshots` row (date, position, url). A
`POST …/refresh` runs checks on demand. The UI charts rank trends over time
with **recharts** (Y axis reversed so #1 is on top). SerpApi requires an
API key — **free tier ~100 searches/month, paid beyond**; without a key,
keywords can be added but positions stay empty (the cron no-ops).

Reports aggregate the latest **Audit** + **Keyword Research** + **Content**
for a project into one branded report, rendered as **HTML** (Jinja2, always
available) or **PDF** (WeasyPrint — needs native libs; the PDF endpoint
returns a clear 503 if unavailable, and HTML/browser-print is the fallback).
**White-label**: Agency-plan users get their own logo/name/color (stored on
the project via `PATCH /projects/{id}`) instead of RankPilot AI branding;
other plans always get RankPilot branding. A "Generate Report" button on the
dashboard downloads the PDF.

Backlink Center (**stateless**) has two parts: a **backlink profile**
(referring domains, anchor-text distribution, follow/nofollow ratio) fetched
from a **free-tier provider** (OpenLinkProfiler by default, via a pluggable
provider abstraction), and a **Broken Link Building** helper that crawls a
page and flags broken outbound links to pitch replacement content. Free data
is **clearly labeled as limited** in the UI; a paid provider key
(Ahrefs/Semrush) can be configured later (`BACKLINK_*` settings) for full
data. If no provider URL is set, the profile degrades to an "unconfigured"
state — the aggregation and UI still work, they just have nothing to show.

Other modules also have `GET` list/detail routes, all scoped to the
authenticated user. Dashboard pages live under
`/dashboard/{audit,optimizer,keywords,content}` behind a sidebar nav and
are protected by NextAuth middleware.

## Agency Mode & access control

Agency Mode (Agency subscription tier only, enforced by the `require_agency`
dependency on the `/agency` router) adds **multi-tenant teams**: a project
owner invites members with roles — **admin** (manage team/settings), **editor**
(run audits, research, generate content), **viewer** (read-only). Access
across every module now goes through `ensure_project_access(project_id, user,
db, min_role=...)`: GET routes require `viewer`, write routes `editor`, and
management (branding, automation config, team) `admin`; the owner outranks
all. Invited teammates accept via `POST /invites/accept` (any plan — not
gated).

**Client access:** owners/admins mint read-only **share links**
(`client_share_links`); `GET /public/share/{token}/report` renders that
project's report with **no login**, honoring white-label branding.

**White-label** (logo, name, primary color, optional custom domain) is stored
per project and applied to both the dashboard (sidebar) and PDF/HTML reports
for Agency-tier owners.

## Authentication

Auth uses **NextAuth.js (Credentials provider) on the frontend and JWT
validation on FastAPI**. FastAPI is the single source of truth for users.

```
Browser ──login──▶ NextAuth (Credentials provider)
   └─▶ POST /api/v1/auth/login (FastAPI)
         └─▶ returns HS256 JWT signed with SECRET_KEY
NextAuth stores the JWT inside its session
Browser ──Authorization: Bearer <JWT>──▶ FastAPI
   └─▶ get_current_user validates with SECRET_KEY, loads the User
```

- **`POST /api/v1/auth/register`** — creates a user + a Free
  `Subscription`, returns a JWT (auto sign-in).
- **`POST /api/v1/auth/login`** — OAuth2 password form (`username` = email),
  returns a JWT + the user.
- **`GET /api/v1/auth/me`** — returns the authenticated user.

Two independent secrets: FastAPI's `SECRET_KEY` signs/validates the API
JWT (backend only); NextAuth's `NEXTAUTH_SECRET` signs its own session
cookie. The API JWT is simply carried inside the NextAuth session. Every
module route depends on `get_current_user` and verifies project
ownership, so users only ever touch their own data.

## Database schema

PostgreSQL via async SQLAlchemy 2.x. Tables (see `apps/api/app/models`):

- **users** — id, email, hashed_password, full_name, plan
  (denormalized active tier), timestamps
- **subscriptions** — id, user_id → users (1:1), tier (free/pro/agency),
  status (active/trialing/past_due/canceled), current_period_end,
  stripe_customer_id, stripe_subscription_id, timestamps
- **projects** — id, owner_id → users, name, domain, platform
  (wordpress/shopify/custom), timestamps
- **credentials** (Credentials) — id, project_id → projects (unique), platform,
  encrypted_api_key_or_token, site_url, connected_at, status, timestamps
- **change_log** (ChangeLog) — id, project_id → projects, platform, issue_type,
  external_change_id, before_snapshot/after_snapshot (JSONB),
  cwv_score_before/after, applied_at, status (applied/reverted), timestamps
- **audit_reports** (AuditReport) — id, project_id → projects, url, status,
  score, results (JSONB), completed_at, timestamps
- **core_web_vitals** (CoreWebVitals) — id, project_id → projects, url,
  strategy, fcp, lcp, tbt, cls, speed_index, field_inp, performance_score,
  accessibility_score, best_practices_score, seo_score, report_json (JSONB —
  insights/diagnostics/passed/screenshots/metadata/runs), scanned_at, timestamps
- **keywords** — id, project_id → projects, seed_keyword, term, kind
  (related/long_tail/question), search_intent, difficulty, search_volume,
  cluster_id, cluster_label, trend_score, trend_direction
- **content** (ContentPiece) — id, project_id → projects, topic,
  target_keyword, content_type, title, meta_description, body_markdown,
  status

Subscription is authoritative for billing state; `users.plan` mirrors the
active tier for fast authorization checks.

### Migrations (Alembic)

The schema is managed by **Alembic** (async), configured in
`apps/api/alembic/` with `alembic.ini`. The app no longer creates tables on
startup — run migrations explicitly:

```bash
cd apps/api
alembic upgrade head        # create/upgrade the schema
alembic revision --autogenerate -m "describe change"   # after model edits
alembic downgrade -1        # roll back one revision
```

`alembic/env.py` reads `DATABASE_URL` from settings and targets
`Base.metadata`, so `--autogenerate` sees every model. Revision
`0001_initial` is the baseline capturing the full current schema (the
project previously used `create_all`, so there is no prior migration
history to preserve — start from an empty database, or drop an existing
`create_all` dev database first).

---

## Architecture

```
rankpilot-ai/
├── apps/
│   ├── web/            # Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui
│   └── api/            # FastAPI (Python, async) backend
├── packages/
│   └── shared/         # Shared TypeScript types & constants (the API contract)
├── wordpress-plugin/   # RankPilot Connector — the WP plugin users install
├── package.json        # Root npm workspaces (web + packages)
└── README.md
```

### How the pieces fit together

```
        ┌───────────────────┐          HTTP / JSON          ┌───────────────────┐
        │   apps/web         │  ─────────────────────────▶  │   apps/api         │
        │   Next.js 14       │   /api/v1/*  (REST)          │   FastAPI (async)  │
        │   React / Tailwind │  ◀─────────────────────────  │   Pydantic schemas │
        └─────────┬─────────┘                               └─────────┬─────────┘
                  │                                                    │
                  │ imports types from                                │ mirrors types in
                  ▼                                                    ▼
        ┌─────────────────────────────────────────────────────────────────────┐
        │                    packages/shared (TypeScript)                       │
        │        Domain types + constants — the single source of truth          │
        └─────────────────────────────────────────────────────────────────────┘
```

- **`apps/web`** renders the UI and calls the backend. In local dev,
  `next.config.mjs` proxies `/api/backend/*` to the FastAPI server so the
  browser never hits CORS. It imports domain types from
  `@rankpilot/shared` so the frontend and the API contract can't drift.
- **`apps/api`** exposes a versioned REST API under `/api/v1`. It uses
  async FastAPI with Pydantic v2 for validation, SQLAlchemy 2.x
  (async) for persistence, and the OpenAI Agents SDK for the keyword and
  content modules.
- **`packages/shared`** holds the domain model as TypeScript types and
  constants. The Pydantic schemas in `apps/api/app/schemas` are kept
  intentionally aligned with these types — they are the same contract in
  two languages.

---

## Tech stack

| Layer     | Technology                                                        |
| --------- | ----------------------------------------------------------------- |
| Frontend  | Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui       |
| Backend   | FastAPI, Python 3.11+, async SQLAlchemy 2.x, Pydantic v2           |
| Database  | PostgreSQL (via `asyncpg`)                                         |
| Queue     | ARQ (async) over Redis — worker process for cron + heavy tasks     |
| AI        | OpenAI Agents SDK (`openai-agents`) with structured outputs        |
| Crawler   | httpx + BeautifulSoup (`lxml`)                                     |
| Shared    | TypeScript types & constants (`@rankpilot/shared`)                 |
| Tooling   | npm workspaces, Ruff, Pytest, ESLint                              |

---

## Getting started

### Prerequisites

- Node.js `>= 18.17`
- Python `>= 3.11`
- PostgreSQL (or update `DATABASE_URL` to point at your instance)

### 1. Frontend + shared (npm workspaces)

```bash
# from the repo root
npm install            # installs apps/web and packages/*
npm run dev:web        # starts Next.js on http://localhost:3000
```

To add shadcn/ui components (config lives in `apps/web/components.json`):

```bash
cd apps/web
npx shadcn@latest add card input dialog   # example
```

### 2. Infra (Postgres + Redis)

```bash
docker compose up -d          # starts postgres:5432 and redis:6379
```

### 3. Backend (FastAPI web + ARQ worker)

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .                   # register the `app` package (importable anywhere)
cp .env.example .env               # then fill in secrets
alembic upgrade head               # create the database schema
python run.py                      # launcher (sets Windows selector loop for psycopg3)
```

In a **second terminal**, run the worker (scheduled cron + heavy tasks):

```bash
cd apps/api && source .venv/bin/activate   # Windows: .venv\Scripts\activate
arq app.worker.WorkerSettings
```

The web process only *enqueues* jobs (audits, crawls, competitor/gap
analysis) and holds the Redis pool; the **worker** executes them and owns the
cron schedule — so scheduled jobs fire exactly once no matter how many web
replicas run. Heavy endpoints return `202 {job_id}`; clients poll
`GET /api/v1/jobs/{job_id}` for status + result.

- API docs (Swagger UI): http://localhost:8000/docs
- Health check: http://localhost:8000/health
- v1 ping: http://localhost:8000/api/v1/ping

From the repo root you can also use the convenience scripts:

```bash
npm run install:api     # pip install -r apps/api/requirements.txt
npm run dev:api         # python run.py                      # launcher (sets Windows selector loop for psycopg3)
```

---

## Project layout details

### `apps/web` (Next.js)

```
apps/web/
├── src/
│   ├── app/
│   │   ├── layout.tsx        # Root layout
│   │   ├── page.tsx          # Landing page
│   │   └── globals.css       # Tailwind + shadcn CSS variables
│   ├── components/ui/        # shadcn/ui components (e.g. button.tsx)
│   └── lib/utils.ts          # cn() class-merge helper
├── components.json           # shadcn/ui config
├── tailwind.config.ts
├── next.config.mjs           # transpiles @rankpilot/shared + API proxy
└── tsconfig.json             # path aliases: @/* and @rankpilot/shared
```

### `apps/api` (FastAPI)

```
apps/api/
├── app/
│   ├── main.py               # FastAPI app, CORS, lifespan, router mount
│   ├── core/config.py        # Settings from environment (pydantic-settings)
│   ├── api/v1/
│   │   ├── router.py         # Aggregates all v1 routes
│   │   └── routes/           # health, projects, audits
│   ├── schemas/              # Pydantic request/response models
│   ├── models/               # SQLAlchemy ORM models (to be added)
│   └── services/             # Business logic / service layer (to be added)
├── tests/                    # Pytest smoke tests
├── requirements.txt
└── pyproject.toml            # Ruff + Pytest config
```

### `packages/shared`

```
packages/shared/
└── src/
    ├── index.ts              # Public entry point
    ├── types/index.ts        # User, Project, Keyword, SeoAudit, ...
    └── constants.ts          # Plan labels, keyword limits, API prefix
```

---

## Keeping the contract in sync

The domain model exists twice — as TypeScript in `packages/shared` and as
Pydantic schemas in `apps/api/app/schemas`. When you change one, update the
other. The shared package is the source of truth for naming and shape.

---

## Testing

```bash
# Backend
cd apps/api && pytest

# Frontend type-check / lint
cd apps/web && npm run typecheck && npm run lint
```

"""Application settings loaded from environment variables."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # CORS (comma-separated string in env -> list)
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000"

    # Database (async driver)
    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/rankpilot"
    )

    # Security. SECRET_KEY signs and validates the API's own JWTs; it lives
    # only on the backend (the Next.js app just carries the token, it never
    # signs it — NextAuth signs its session cookie with NEXTAUTH_SECRET).
    SECRET_KEY: str = "change-me-in-production"
    # 7 days — kept in step with the NextAuth session maxAge.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # AI provider (OpenAI Agents SDK reads OPENAI_API_KEY from the env)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Keyword clustering: minimum cosine similarity to join a cluster.
    KEYWORD_CLUSTER_THRESHOLD: float = 0.5

    # Google Trends (pytrends) is rate-limited; keep the request bounded.
    KEYWORD_TREND_MAX_TERMS: int = 20
    KEYWORD_TREND_SLEEP: float = 1.0

    # Audit crawler tuning
    AUDIT_MAX_LINKS_CHECKED: int = 25
    AUDIT_REQUEST_TIMEOUT: float = 10.0

    # --- Platform connectors (WordPress + Shopify) ---
    # Public base URL of THIS FastAPI service — used to build the Shopify
    # OAuth redirect_uri (must be reachable by Shopify; use a tunnel in dev).
    APP_BASE_URL: str = "http://localhost:8000"
    # Public base URL of the Next.js app — where the OAuth callback bounces
    # the browser back to after storing the token.
    FRONTEND_URL: str = "http://localhost:3000"
    # Fernet key (32-byte url-safe base64) for encrypting stored credentials.
    # Leave blank to derive one from SECRET_KEY (fine for dev; set in prod).
    CREDENTIALS_ENCRYPTION_KEY: str = ""
    # WordPress: the RankPilot plugin exposes a health-check under this
    # namespace, i.e. GET {site}/wp-json/{ns}/health.
    WORDPRESS_API_NAMESPACE: str = "rankpilot/v1"
    WORDPRESS_CONNECT_TIMEOUT: float = 10.0
    # Shopify app credentials (from the Shopify Partner dashboard).
    SHOPIFY_API_KEY: str = ""
    SHOPIFY_API_SECRET: str = ""
    SHOPIFY_SCOPES: str = "read_themes,write_themes,read_products,write_products"
    SHOPIFY_API_VERSION: str = "2024-07"
    # OAuth install-state token lifetime (signed JWT carrying the project id).
    SHOPIFY_STATE_TTL_SECONDS: int = 600

    # --- Core Web Vitals (Google PageSpeed Insights API v5) ---
    # API key from https://developers.google.com/speed/docs/insights/v5/get-started
    # (env only — never hardcode). Optional for occasional calls, but required
    # for real quota (free tier: 25,000/day, 240/min).
    PAGESPEED_API_KEY: str = ""
    # Override the endpoint (tests/proxies); blank = the official URL.
    PAGESPEED_API_URL: str = ""
    # Google runs Lighthouse server-side, so a call can take 20–40s.
    PAGESPEED_TIMEOUT: float = 60.0
    # Retries on HTTP 429 (rate limit) / 5xx, with exponential backoff.
    PAGESPEED_MAX_RETRIES: int = 3
    PAGESPEED_RETRY_BASE_DELAY: float = 1.0
    # Runs per scan; the median of each metric is stored to reduce variance.
    # Each run is a separate API call (counts against quota).
    PAGESPEED_RUNS: int = 2

    # Competitor Intelligence: max pages to crawl per site.
    COMPETITOR_MAX_PAGES: int = 40
    # Concurrent page fetches during a crawl (bounded politeness + speed).
    COMPETITOR_MAX_CONCURRENCY: int = 6
    # Respect robots.txt Disallow rules for our user-agent.
    COMPETITOR_RESPECT_ROBOTS: bool = True
    # Sitemap discovery caps (sitemap-index recursion is bounded by these).
    COMPETITOR_MAX_SITEMAPS: int = 20
    COMPETITOR_MAX_SITEMAP_URLS: int = 5000
    # Content Gap Analysis crawls 2–3 competitors, so use a smaller per-site
    # cap to bound total work.
    GAP_MAX_PAGES_PER_COMPETITOR: int = 8

    # --- SEO data provider (real traffic/authority/backlinks) ---
    # No provider is wired by default: all such figures are AI-estimated and
    # labeled as such. Set SEO_PROVIDER (e.g. "dataforseo") + the matching
    # credentials below to have app.services.seo_data_provider return
    # first-party metrics instead. See that module for integration details.
    SEO_PROVIDER: str | None = None
    DATAFORSEO_LOGIN: str = ""
    DATAFORSEO_PASSWORD: str = ""
    AHREFS_API_TOKEN: str = ""
    SEMRUSH_API_KEY: str = ""

    # Internal Link Optimizer: crawl cap and semantic-suggestion tuning.
    INTERNAL_LINK_MAX_PAGES: int = 40
    INTERNAL_LINK_SIM_THRESHOLD: float = 0.35
    INTERNAL_LINK_TOP_K: int = 3

    # --- Rank Tracking (SerpApi) ---
    # SerpApi API key. Free tier is ~100 searches/month; paid beyond that.
    # Get one at https://serpapi.com/. Leave blank to disable live lookups.
    SERPAPI_API_KEY: str = ""
    SERPAPI_ENGINE: str = "google"
    # Google no longer honors num=100, so we paginate with `start` instead:
    # SERPAPI_PAGE_SIZE results per page, up to SERPAPI_MAX_PAGES pages.
    # Each page is ONE SerpApi search — keep MAX_PAGES low on the free tier
    # (e.g. 3 pages ≈ top 30 ≈ 3 searches per keyword per check).
    SERPAPI_PAGE_SIZE: int = 10
    SERPAPI_MAX_PAGES: int = 3
    SERPAPI_LOCATION: str = "United States"  # e.g. "United States"
    # Country / language / domain — pin these for consistent regional results.
    # (location alone can be partial; gl+hl+google_domain make US results
    # match what a US searcher sees.)
    SERPAPI_GL: str = "us"  # country code
    SERPAPI_HL: str = "en"  # UI language
    SERPAPI_GOOGLE_DOMAIN: str = "google.com"
    # Daily cron (APScheduler): run the tracking job at this hour (server TZ).
    RANK_TRACKING_ENABLED: bool = True
    RANK_TRACKING_HOUR: int = 3

    # --- Queue / worker (ARQ + Redis) ---
    # Scheduled cron jobs and heavy tasks run in a separate ARQ worker
    # process (see app.worker), so the web process never schedules or does
    # long crawls. Run the worker with:  arq app.worker.WorkerSettings
    REDIS_URL: str = "redis://localhost:6379"
    QUEUE_KEEP_RESULT: int = 3600  # seconds to retain job results in Redis
    JOB_POLL_TIMEOUT: int = 300

    # --- Automation (email notifications; cron runs in the ARQ worker) ---
    AUTOMATION_ENABLED: bool = True
    AUTOMATION_DAILY_HOUR: int = 6  # after rank tracking (3) so drops are fresh
    AUTOMATION_WEEKLY_DAY: str = "mon"  # mon|tue|...|sun
    AUTOMATION_WEEKLY_HOUR: int = 7
    RANK_DROP_THRESHOLD: int = 5  # notify when position worsens by more than this
    # Email via Resend (https://resend.com). Set EMAIL_PROVIDER="none" to
    # disable. Leave RESEND_API_KEY blank and emails are logged/skipped.
    EMAIL_PROVIDER: str = "resend"
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "RankPilot AI <noreply@rankpilot.ai>"

    # --- Backlink Center ---
    # Free-tier backlink data (OpenLinkProfiler by default). This is
    # intentionally limited; swap in a paid provider (ahrefs/semrush) with a
    # key later for full data. Leave BACKLINK_API_URL blank to disable live
    # lookups (the UI then shows "limited free data — not configured").
    BACKLINK_PROVIDER: str = "openlinkprofiler"
    BACKLINK_API_URL: str = ""  # e.g. OpenLinkProfiler API endpoint
    BACKLINK_API_KEY: str = ""
    BACKLINK_MAX: int = 200  # max backlinks to aggregate
    # Broken Link Building: max outbound links to check on a page.
    BACKLINK_MAX_LINKS_CHECKED: int = 40

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.BACKEND_CORS_ORIGINS.split(",")
            if origin.strip()
        ]


settings = Settings()

# The OpenAI Agents SDK and LangChain read OPENAI_API_KEY from the process
# environment, but we load it from .env into `settings`. Bridge it across so
# those libraries authenticate without requiring a separately-exported env var.
if settings.OPENAI_API_KEY and not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

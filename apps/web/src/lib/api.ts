/**
 * Typed client for the RankPilot AI backend.
 *
 * Requests go to `/api/backend/*`, which `next.config.mjs` rewrites to
 * the FastAPI server's `/api/v1/*` during local dev. Authenticated calls
 * attach the FastAPI JWT stored in the NextAuth session as a Bearer token.
 *
 * Long-running endpoints (a real Lighthouse scan takes 15–45s) are called
 * with `{ direct: true }`, which bypasses the Next.js dev rewrite proxy and
 * hits the backend directly via `NEXT_PUBLIC_API_BASE_URL`. The dev proxy
 * drops the upstream socket on long requests (ECONNRESET → a spurious 500);
 * a direct connection holds for the full scan. CORS is enabled on the API.
 */

import { getSession } from "next-auth/react";

const BASE = "/api/backend";
// Direct backend origin (…/api/v1). Falls back to the proxy when unset (prod).
const DIRECT_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? BASE;

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  plan: string;
  created_at: string;
}

export type Platform = "wordpress" | "shopify" | "custom";
export type ConnectionStatus = "connected" | "error" | "disconnected";

export interface Project {
  id: string;
  owner_id: string;
  name: string;
  domain: string;
  platform: Platform;
  brand_name: string | null;
  brand_logo_url: string | null;
  brand_color: string | null;
  custom_domain: string | null;
  created_at: string;
}

export interface ProjectUpdate {
  name?: string;
  domain?: string;
  brand_name?: string | null;
  brand_logo_url?: string | null;
  brand_color?: string | null;
  custom_domain?: string | null;
}

// --- Platform connectors (WordPress + Shopify) ---
export interface Credentials {
  id: string;
  project_id: string;
  platform: Platform;
  site_url: string | null;
  status: ConnectionStatus;
  connected_at: string | null;
  created_at: string;
}

// --- Agency Mode ---
export type AgencyRole = "admin" | "editor" | "viewer";

export interface Member {
  id: string;
  user_id: string;
  email: string;
  role: string;
  created_at: string;
}

export interface Invite {
  id: string;
  email: string;
  role: string;
  token: string;
  accepted: boolean;
  created_at: string;
}

export interface ShareLink {
  id: string;
  token: string;
  label: string | null;
  revoked: boolean;
  created_at: string;
}

export type AuditStatus = "queued" | "running" | "completed" | "failed";
export type IssueSeverity = "info" | "warning" | "critical";

export interface AuditIssue {
  code: string;
  severity: IssueSeverity;
  message: string;
  recommendation: string;
}

export interface BrokenLink {
  url: string;
  status_code: number | null;
  reason: string;
}

export interface AuditResults {
  meta: {
    title: string | null;
    title_length: number;
    meta_description: string | null;
    meta_description_length: number;
    has_canonical: boolean;
    has_viewport: boolean;
    has_open_graph: boolean;
    robots: string | null;
  };
  headings: {
    h1_count: number;
    h2_count: number;
    h3_count: number;
    h4_count: number;
    h5_count: number;
    h6_count: number;
    h1_texts: string[];
  };
  images: {
    total: number;
    missing_alt: number;
    missing_alt_samples: string[];
  };
  links: {
    internal_count: number;
    external_count: number;
    checked: number;
    broken: BrokenLink[];
  };
  page_speed: {
    response_time_ms: number;
    page_size_kb: number;
    request_count_estimate: number;
    status_code: number;
  };
  issues: AuditIssue[];
}

export interface Audit {
  id: string;
  project_id: string;
  url: string;
  status: AuditStatus;
  score: number | null;
  results: AuditResults | null;
  created_at: string;
  completed_at: string | null;
}

// --- Core Web Vitals (PageSpeed Insights) ---
export type CWVStrategy = "mobile" | "desktop";
export type CWVCategoryKey =
  | "performance"
  | "accessibility"
  | "best_practices"
  | "seo";

export interface CWVAuditItem {
  id: string;
  title: string;
  description: string;
  score: number | null;
  display_value: string | null;
  savings_ms: number | null;
  savings_bytes: number | null;
}

export interface CWVCategoryAudits {
  score: number | null;
  insights: CWVAuditItem[];
  diagnostics: CWVAuditItem[];
  passed_count: number;
  passed_titles: string[];
}

export interface CWVLabMetrics {
  fcp: number | null;
  lcp: number | null;
  tbt: number | null;
  cls: number | null;
  speed_index: number | null;
}

export interface CWVRunMetrics extends CWVLabMetrics {
  performance_score: number | null;
}

export interface CWVScreenshots {
  timeline: string[];
  final: string | null;
}

export interface CWVMetadata {
  lighthouse_version: string | null;
  form_factor: string | null;
  throttling_method: string | null;
  fetch_time: string | null;
  final_url: string | null;
}

export interface CoreWebVitalsReport {
  strategy: CWVStrategy;
  metrics: CWVLabMetrics;
  field_inp: number | null;
  categories: Record<CWVCategoryKey, CWVCategoryAudits>;
  screenshots: CWVScreenshots;
  metadata: CWVMetadata;
  runs: CWVRunMetrics[];
  lcp_element: string | null;
}

export interface CoreWebVitals {
  id: string;
  project_id: string;
  url: string;
  strategy: CWVStrategy;
  fcp: number | null;
  lcp: number | null;
  tbt: number | null;
  cls: number | null;
  speed_index: number | null;
  field_inp: number | null;
  performance_score: number | null;
  accessibility_score: number | null;
  best_practices_score: number | null;
  seo_score: number | null;
  report: CoreWebVitalsReport | null;
  scanned_at: string;
  created_at: string;
}

// --- CWV fix orchestration ---
export type ChangeStatus = "applied" | "reverted";
export type RescanStatus = "completed" | "failed" | "skipped";

export interface ChangeLog {
  id: string;
  project_id: string;
  platform: Platform;
  issue_type: string;
  external_change_id: string | null;
  before_snapshot: Record<string, unknown> | null;
  after_snapshot: Record<string, unknown> | null;
  cwv_score_before: number | null;
  cwv_score_after: number | null;
  applied_at: string;
  status: ChangeStatus;
  created_at: string;
}

export interface FixResponse {
  change: ChangeLog;
  new_scan: CoreWebVitals | null;
  rescan_status: RescanStatus;
  detail: string | null;
}

export type KeywordKind = "related" | "long_tail" | "question";
export type KeywordDifficulty = "low" | "medium" | "high";
export type KeywordIntent = "informational" | "commercial" | "transactional";

export type TrendDirection = "rising" | "falling" | "flat";

export interface Keyword {
  id: string;
  project_id: string;
  seed_keyword: string;
  term: string;
  kind: KeywordKind;
  search_intent: KeywordIntent | null;
  difficulty: KeywordDifficulty | null;
  search_volume: number | null;
  cluster_id: number | null;
  cluster_label: string | null;
  trend_score: number | null;
  trend_direction: TrendDirection | null;
  created_at: string;
}

export type ContentType = "blog" | "product_description" | "landing_page";

export interface Content {
  id: string;
  project_id: string;
  topic: string;
  target_keyword: string;
  content_type: ContentType;
  title: string;
  meta_description: string | null;
  body_markdown: string;
  status: string;
  created_at: string;
}

export interface DensityReport {
  keyword: string;
  occurrences: number;
  word_count: number;
  density_pct: number;
  assessment: "low" | "optimal" | "high";
  recommendation: string;
}

export interface ContentStreamHandlers {
  onPhase?: (phase: string) => void;
  onOutline?: (sections: string[]) => void;
  onSection?: (index: number, title: string) => void;
  onToken?: (text: string) => void;
  onSeo?: (data: {
    meta_title: string;
    meta_description: string;
    density: DensityReport;
  }) => void;
  onDone?: (contentId: string) => void;
  onError?: (detail: string) => void;
}

// --- On-Page SEO Optimizer ---
export type OptimizerSeverity = "critical" | "warning" | "info";
export type OptimizerCategory =
  | "meta_title"
  | "meta_description"
  | "headings"
  | "keyword_placement"
  | "keyword_density"
  | "links"
  | "images"
  | "readability"
  | "ai";

export interface AnchorSample {
  text: string;
  href: string;
  kind: "internal" | "external";
  generic: boolean;
  location: string;
}

export interface OnPageChecks {
  meta_title: {
    text: string | null;
    length: number;
    has_keyword: boolean;
    keyword_at_start: boolean;
  };
  meta_description: {
    text: string | null;
    length: number;
    has_keyword: boolean;
  };
  headings: {
    h1_count: number;
    h2_count: number;
    h3_count: number;
    h4_count: number;
    h5_count: number;
    h6_count: number;
    h1_has_keyword: boolean;
    subheading_has_keyword: boolean;
    h1_texts: string[];
  };
  keyword_placement: {
    in_title: boolean;
    in_meta_description: boolean;
    in_h1: boolean;
    in_subheadings: boolean;
    in_first_paragraph: boolean;
    in_url: boolean;
    in_image_alt: boolean;
    placement_score: number;
  };
  keyword_density: {
    keyword: string;
    occurrences: number;
    word_count: number;
    density_pct: number;
    assessment: "low" | "optimal" | "high";
  };
  links: {
    internal_count: number;
    external_count: number;
    generic_anchor_count: number;
    samples: AnchorSample[];
  };
  images: { total: number; missing_alt: number; with_keyword_alt: number };
  readability: {
    flesch_reading_ease: number | null;
    grade_level: number | null;
    assessment: string;
  };
}

export interface OptimizerSuggestion {
  category: OptimizerCategory;
  severity: OptimizerSeverity;
  message: string;
  recommendation: string;
}

export interface OptimizeResponse {
  url: string;
  target_keyword: string;
  score: number;
  checks: OnPageChecks;
  ai_suggestions: {
    lsi_keywords: string[];
    missing_keywords: string[];
    notes: string;
  };
  suggestions: OptimizerSuggestion[];
}

// --- Competitor Intelligence ---
// Page counts, links, sitemap URLs and topic overlap are MEASURED from a
// crawl; traffic/authority are AI-estimated (or provider-sourced) — the
// `*_source` fields say which.
export type MetricSource = "ai_estimate" | "provider";

export interface CrawlStatus {
  ok: boolean;
  reason: string;
  detail: string;
}

export interface CrawledSite {
  url: string;
  domain: string;
  crawl_status: CrawlStatus;
  sample_titles: string[];
  top_headings: string[];
  structure: {
    pages_crawled: number;
    pages_discovered: number;
    sitemap_url_count: number | null;
    total_internal_links: number;
    avg_internal_links_per_page: number;
    avg_word_count: number;
    indexable_pages: number;
    duplicate_pages_collapsed: number;
    disallowed_by_robots: number;
    top_hub_pages: { url: string; inbound_links: number }[];
  };
  pages: {
    url: string;
    status_code: number | null;
    title: string | null;
    h1: string | null;
    meta_description: string | null;
    canonical: string | null;
    heading_count: number;
    word_count: number;
    internal_link_count: number;
    external_link_count: number;
    indexable: boolean;
  }[];
}

export interface CompetitorReport {
  competitor: CrawledSite;
  user_site: CrawledSite;
  user_project: {
    project_name: string;
    domain: string;
    keyword_count: number;
    content_count: number;
    top_keywords: string[];
    top_topics: string[];
  };
  comparison: {
    user_topics: string[];
    competitor_topics: string[];
    shared_topics: string[];
    keyword_gaps: string[];
    user_advantages: string[];
  };
  analysis: {
    content_strategy: string;
    topic_focus_areas: {
      topic: string;
      emphasis: "low" | "medium" | "high";
      note: string;
    }[];
    estimated_traffic_band: string;
    traffic_source: MetricSource;
    estimated_authority: number;
    authority_source: MetricSource;
    user_estimated_traffic_band: string;
    user_traffic_source: MetricSource;
    user_estimated_authority: number;
    user_authority_source: MetricSource;
    keyword_gaps: string[];
    content_gaps: { topic: string; rationale: string }[];
    shared_topics: string[];
    recommendations: string[];
  };
  ai_estimated: boolean;
  disclaimer: string;
}

// --- Content Gap Analysis ---
export type GapPriority = "high" | "medium" | "low";

export interface ContentBrief {
  title: string;
  target_keyword: string;
  content_type: ContentType;
  outline: string[];
  word_count_target: number;
  priority: GapPriority;
  rationale: string;
}

export interface GapAnalysisResponse {
  user_project: {
    project_name: string;
    domain: string;
    keyword_count: number;
    content_count: number;
    top_keywords: string[];
    top_topics: string[];
  };
  competitors: {
    url: string;
    domain: string;
    pages_crawled: number;
    sample_titles: string[];
  }[];
  missing_topics: string[];
  missing_faqs: string[];
  content_briefs: ContentBrief[];
}

// --- Internal Link Optimizer ---
export interface InternalLinkPage {
  id: string;
  url: string;
  title: string | null;
  content_summary: string | null;
  word_count: number;
}

export interface GraphNode {
  id: string;
  label: string;
  url: string;
  inbound: number;
  outbound: number;
  is_orphan: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface LinkSuggestion {
  from_url: string;
  from_title: string;
  to_url: string;
  to_title: string;
  anchor_text: string;
  similarity: number;
}

export interface InternalLinkAnalysis {
  page_count: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  suggestions: LinkSuggestion[];
  orphans: InternalLinkPage[];
}

// --- Automation ---
export interface AutomationSettings {
  id: string;
  project_id: string;
  weekly_audit: boolean;
  broken_link_monitoring: boolean;
  competitor_monitoring: boolean;
  email_notifications: boolean;
  notify_rank_drops: boolean;
  notify_broken_links: boolean;
  weekly_summary: boolean;
  audit_url: string | null;
  monitor_url: string | null;
  competitor_urls: string[] | null;
  notification_email: string | null;
}

export type AutomationSettingsUpdate = Partial<
  Omit<AutomationSettings, "id" | "project_id">
>;

// --- Backlink Center ---
export interface AnchorCount {
  anchor: string;
  count: number;
  percentage: number;
}

export interface SampleBacklink {
  source_url: string;
  source_domain: string;
  anchor: string;
  nofollow: boolean;
}

export interface BacklinkProfile {
  domain: string;
  data_source: string;
  limited: boolean;
  referring_domains: number;
  total_backlinks: number;
  follow_count: number;
  nofollow_count: number;
  nofollow_ratio: number;
  anchor_distribution: AnchorCount[];
  sample_backlinks: SampleBacklink[];
  note: string;
}

export interface BrokenOutboundLink {
  url: string;
  anchor: string;
  status_code: number | null;
  reason: string;
  kind: "internal" | "external";
}

export interface BrokenLinkResult {
  url: string;
  links_checked: number;
  broken_count: number;
  broken_links: BrokenOutboundLink[];
}

async function request<T>(
  path: string,
  init?: RequestInit & { auth?: boolean; direct?: boolean }
): Promise<T> {
  const { auth = true, direct = false, ...rest } = init ?? {};

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(rest.headers as Record<string, string> | undefined),
  };

  if (auth) {
    const session = await getSession();
    if (session?.accessToken) {
      headers.Authorization = `Bearer ${session.accessToken}`;
    }
  }

  const res = await fetch(`${direct ? DIRECT_BASE : BASE}${path}`, {
    ...rest,
    headers,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    // An invalid/expired backend token: sign out and send to login rather
    // than crashing the app with an unhandled error.
    if (res.status === 401 && auth && typeof window !== "undefined") {
      const { signOut } = await import("next-auth/react");
      await signOut({ callbackUrl: "/login" });
    }
    throw new Error(detail);
  }
  // 204 No Content (e.g. DELETE) has no body to parse.
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// --- Background jobs (ARQ queue) ---
export interface JobEnqueued {
  job_id: string;
  status: string;
}

export interface JobStatusResponse<T = unknown> {
  job_id: string;
  status: "queued" | "running" | "complete" | "failed" | "not_found";
  result: T | null;
  error: string | null;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Enqueue a job then poll /jobs/{id} until it finishes, returning the result.
 * `onStatus` reports "queued"/"running"/… so the UI can show progress.
 */
export async function runJob<T>(
  enqueue: () => Promise<JobEnqueued>,
  opts?: {
    onStatus?: (status: string) => void;
    intervalMs?: number;
    timeoutMs?: number;
  }
): Promise<T> {
  const { job_id } = await enqueue();
  const interval = opts?.intervalMs ?? 1500;
  const timeout = opts?.timeoutMs ?? 240000;
  const start = Date.now();

  for (;;) {
    await sleep(interval);
    const job = await request<JobStatusResponse<T>>(`/jobs/${job_id}`);
    opts?.onStatus?.(job.status);
    if (job.status === "complete") return job.result as T;
    if (job.status === "failed") throw new Error(job.error ?? "Job failed");
    if (job.status === "not_found") throw new Error("Job not found");
    if (Date.now() - start > timeout) throw new Error("Job timed out");
  }
}

/** Fetch a binary response (PDF/HTML report) with the auth Bearer token. */
async function authBlob(path: string): Promise<Blob> {
  const session = await getSession();
  const headers: Record<string, string> = {};
  if (session?.accessToken) {
    headers.Authorization = `Bearer ${session.accessToken}`;
  }
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON */
    }
    throw new Error(detail);
  }
  return res.blob();
}

export const api = {
  // Auth
  register: (data: {
    email: string;
    password: string;
    full_name?: string | null;
  }) =>
    request<{ access_token: string; user: User }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
      auth: false,
    }),
  me: () => request<User>("/auth/me"),

  // Projects
  listProjects: () => request<Project[]>("/projects"),
  createProject: (data: { name: string; domain: string }) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateProject: (id: string, data: ProjectUpdate) =>
    request<Project>(`/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  // Platform connectors (WordPress + Shopify)
  getConnection: (projectId: string) =>
    request<Credentials | null>(`/connectors?project_id=${projectId}`),
  connectWordPress: (data: {
    project_id: string;
    site_url: string;
    api_key: string;
  }) =>
    request<Credentials>("/connectors/wordpress/connect", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  // Returns the Shopify OAuth URL; the caller redirects the browser there.
  shopifyInstall: (data: { project_id: string; shop: string }) =>
    request<{ authorize_url: string }>("/connectors/shopify/install", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  disconnect: (projectId: string) =>
    request<void>(`/connectors?project_id=${projectId}`, { method: "DELETE" }),

  // Website Audit (enqueue → poll → fetch by id)
  enqueueAudit: (data: { project_id: string; url: string }) =>
    request<JobEnqueued>("/audits", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getAudit: (auditId: string) => request<Audit>(`/audits/${auditId}`),
  listAudits: (projectId: string) =>
    request<Audit[]>(`/audits?project_id=${projectId}`),

  // Core Web Vitals (synchronous Lighthouse scan → stored + returned)
  runCoreWebVitals: (data: {
    project_id: string;
    url: string;
    strategy?: CWVStrategy;
  }) =>
    request<CoreWebVitals>("/audit/core-web-vitals", {
      method: "POST",
      body: JSON.stringify(data),
      direct: true, // PageSpeed Insights call is slow — bypass the dev proxy
    }),
  listCoreWebVitals: (projectId: string) =>
    request<CoreWebVitals[]>(`/audit/core-web-vitals?project_id=${projectId}`),
  getCoreWebVitals: (scanId: string) =>
    request<CoreWebVitals>(`/audit/core-web-vitals/${scanId}`),

  // CWV fix orchestration (platform-routed; triggers a re-scan)
  fixAllCwv: (projectId: string, url?: string) =>
    request<FixResponse>(`/projects/${projectId}/cwv/fix-all`, {
      method: "POST",
      body: JSON.stringify({ url: url ?? null }),
      direct: true, // fix + re-scan is long — bypass the dev proxy
    }),
  revertCwvFix: (projectId: string, changeId: string) =>
    request<FixResponse>(`/projects/${projectId}/cwv/revert/${changeId}`, {
      method: "POST",
      direct: true, // revert + re-scan is long — bypass the dev proxy
    }),
  listCwvChanges: (projectId: string) =>
    request<ChangeLog[]>(`/projects/${projectId}/cwv/changes`),

  // Keyword Research
  enqueueKeywordResearch: (data: {
    project_id: string;
    seed_keyword: string;
  }) =>
    request<JobEnqueued>("/keywords/research", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listKeywords: (projectId: string) =>
    request<Keyword[]>(`/keywords?project_id=${projectId}`),

  // AI Content Studio
  generateContent: (data: {
    project_id: string;
    topic: string;
    target_keyword: string;
    content_type?: ContentType;
    tone?: string;
    word_count?: number;
  }) =>
    request<Content>("/content/generate", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  generateContentStream: streamContent,
  listContent: (projectId: string) =>
    request<Content[]>(`/content?project_id=${projectId}`),

  // On-Page SEO Optimizer
  analyzeOnPage: (data: { url: string; target_keyword: string }) =>
    request<OptimizeResponse>("/optimizer/analyze", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Competitor Intelligence (enqueue → poll for report)
  enqueueCompetitor: (data: { project_id: string; competitor_url: string }) =>
    request<JobEnqueued>("/competitors/analyze", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Content Gap Analysis (enqueue → poll for report)
  enqueueGaps: (data: { project_id: string; competitor_urls: string[] }) =>
    request<JobEnqueued>("/gap-analysis/analyze", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Internal Link Optimizer (enqueue crawl → poll → GET analysis)
  enqueueInternalLinkCrawl: (projectId: string) =>
    request<JobEnqueued>("/internal-links/crawl", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId }),
    }),
  getInternalLinkAnalysis: (projectId: string) =>
    request<InternalLinkAnalysis>(
      `/internal-links/analysis?project_id=${projectId}`
    ),

  // Backlink Center
  getBacklinkProfile: (domain: string) =>
    request<BacklinkProfile>("/backlinks/profile", {
      method: "POST",
      body: JSON.stringify({ domain }),
    }),
  enqueueBrokenLinks: (url: string) =>
    request<JobEnqueued>("/backlinks/broken-links", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  // Reports (binary responses)
  reportPdfBlob: (projectId: string) =>
    authBlob(`/reports/${projectId}/pdf`),
  reportHtmlBlob: (projectId: string) =>
    authBlob(`/reports/${projectId}/html`),

  // AI SEO Assistant (SSE chat)
  streamAssistantChat,

  // Agency Mode — team members
  listMembers: (projectId: string) =>
    request<Member[]>(`/agency/projects/${projectId}/members`),
  updateMemberRole: (projectId: string, memberId: string, role: AgencyRole) =>
    request<Member>(`/agency/projects/${projectId}/members/${memberId}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),
  removeMember: (projectId: string, memberId: string) =>
    request<void>(`/agency/projects/${projectId}/members/${memberId}`, {
      method: "DELETE",
    }),
  // Agency Mode — invites
  listInvites: (projectId: string) =>
    request<Invite[]>(`/agency/projects/${projectId}/invites`),
  createInvite: (projectId: string, data: { email: string; role: AgencyRole }) =>
    request<Invite>(`/agency/projects/${projectId}/invites`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  acceptInvite: (token: string) =>
    request<{ project_id: string; role: string }>("/invites/accept", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  // Agency Mode — client share links
  listShareLinks: (projectId: string) =>
    request<ShareLink[]>(`/agency/projects/${projectId}/share-links`),
  createShareLink: (projectId: string, label?: string) =>
    request<ShareLink>(`/agency/projects/${projectId}/share-links`, {
      method: "POST",
      body: JSON.stringify({ label: label ?? null }),
    }),
  revokeShareLink: (projectId: string, linkId: string) =>
    request<void>(`/agency/projects/${projectId}/share-links/${linkId}`, {
      method: "DELETE",
    }),

  // Automation
  getAutomationSettings: (projectId: string) =>
    request<AutomationSettings>(
      `/automation/settings?project_id=${projectId}`
    ),
  updateAutomationSettings: (
    projectId: string,
    data: AutomationSettingsUpdate
  ) =>
    request<AutomationSettings>(
      `/automation/settings?project_id=${projectId}`,
      { method: "PUT", body: JSON.stringify(data) }
    ),
  runAutomation: (projectId: string, kind: "daily" | "weekly") =>
    request<{ status: string; kind: string }>(
      `/automation/run?project_id=${projectId}&kind=${kind}`,
      { method: "POST" }
    ),
};

export interface AssistantMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AssistantHandlers {
  onToken?: (text: string) => void;
  onTool?: (name: string, label: string) => void;
  onDone?: () => void;
  onError?: (detail: string) => void;
}

/** Stream an SEO Assistant reply over SSE (fetch, so we can send the token). */
async function streamAssistantChat(
  data: { project_id: string; messages: AssistantMessage[] },
  handlers: AssistantHandlers,
  signal?: AbortSignal
): Promise<void> {
  const session = await getSession();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (session?.accessToken) {
    headers.Authorization = `Bearer ${session.accessToken}`;
  }

  const res = await fetch(`${BASE}/assistant/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify(data),
    signal,
  });

  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    handlers.onError?.(detail);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);

      let event = "message";
      const dataLines: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (!dataLines.length) continue;
      const payload = JSON.parse(dataLines.join("\n"));
      if (event === "token") handlers.onToken?.(payload.text ?? "");
      else if (event === "tool")
        handlers.onTool?.(payload.name, payload.label ?? payload.name);
      else if (event === "done") handlers.onDone?.();
      else if (event === "error")
        handlers.onError?.(payload.detail ?? "Assistant error");
    }
  }
}

/**
 * Consume the SSE content stream. Uses a streaming `fetch` (not EventSource)
 * so we can send the Authorization Bearer header.
 */
async function streamContent(
  data: {
    project_id: string;
    topic: string;
    target_keyword: string;
    content_type?: ContentType;
    tone?: string;
    word_count?: number;
  },
  handlers: ContentStreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  const session = await getSession();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (session?.accessToken) {
    headers.Authorization = `Bearer ${session.accessToken}`;
  }

  const res = await fetch(`${BASE}/content/generate/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify(data),
    signal,
  });

  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    handlers.onError?.(detail);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (event: string, payload: string) => {
    const data = payload ? JSON.parse(payload) : {};
    switch (event) {
      case "phase":
        handlers.onPhase?.(data.phase);
        break;
      case "outline":
        handlers.onOutline?.(data.sections ?? []);
        break;
      case "section":
        handlers.onSection?.(data.index ?? 0, data.title ?? "");
        break;
      case "token":
        handlers.onToken?.(data.text ?? "");
        break;
      case "seo":
        handlers.onSeo?.(data);
        break;
      case "done":
        handlers.onDone?.(data.content_id);
        break;
      case "error":
        handlers.onError?.(data.detail ?? "Generation failed");
        break;
    }
  };

  // Parse SSE frames: blocks separated by a blank line, each with
  // `event:` and `data:` lines.
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);

      let event = "message";
      const dataLines: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (dataLines.length) dispatch(event, dataLines.join("\n"));
    }
  }
}

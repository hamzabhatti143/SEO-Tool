/**
 * Domain types shared across the RankPilot AI platform.
 *
 * Keep these in sync with the Pydantic models in
 * `apps/api/app/schemas`. These are the contract between the
 * frontend and the backend API.
 */

export type UUID = string;
export type ISODateString = string;

/** Subscription tiers offered by RankPilot AI. */
export type PlanTier = "free" | "pro" | "agency";

export type SubscriptionStatus =
  | "active"
  | "trialing"
  | "past_due"
  | "canceled";

export interface User {
  id: UUID;
  email: string;
  fullName: string | null;
  plan: PlanTier;
  createdAt: ISODateString;
}

export interface Subscription {
  id: UUID;
  userId: UUID;
  tier: PlanTier;
  status: SubscriptionStatus;
  currentPeriodEnd: ISODateString | null;
  createdAt: ISODateString;
}

/** CMS/commerce platform a project can be connected to. */
export type Platform = "wordpress" | "shopify" | "custom";
export type ConnectionStatus = "connected" | "error" | "disconnected";

/** A website / property being tracked for SEO. */
export interface Project {
  id: UUID;
  ownerId: UUID;
  name: string;
  domain: string;
  platform: Platform;
  createdAt: ISODateString;
}

/**
 * A project's connection to its platform. The secret (WordPress API key /
 * Shopify access token) is stored encrypted server-side and never exposed.
 */
export interface Credentials {
  id: UUID;
  projectId: UUID;
  platform: Platform;
  siteUrl: string | null;
  status: ConnectionStatus;
  connectedAt: ISODateString | null;
  createdAt: ISODateString;
}

export type KeywordKind = "related" | "long_tail" | "question";
export type KeywordDifficulty = "low" | "medium" | "high";
export type KeywordIntent = "informational" | "commercial" | "transactional";
export type TrendDirection = "rising" | "falling" | "flat";

/** A keyword surfaced by AI keyword research within a project. */
export interface Keyword {
  id: UUID;
  projectId: UUID;
  seedKeyword: string;
  term: string;
  kind: KeywordKind;
  difficulty: KeywordDifficulty | null;
  searchIntent: KeywordIntent | null;
  searchVolume: number | null;
  /** Topic cluster (embeddings + cosine similarity). */
  clusterId: number | null;
  clusterLabel: string | null;
  /** Google Trends signal (best-effort). */
  trendScore: number | null;
  trendDirection: TrendDirection | null;
  createdAt: ISODateString;
}

export type AuditStatus = "queued" | "running" | "completed" | "failed";

/** Result of an AI-driven SEO audit run against a project. */
export interface SeoAudit {
  id: UUID;
  projectId: UUID;
  status: AuditStatus;
  score: number | null;
  issues: SeoIssue[];
  createdAt: ISODateString;
  completedAt: ISODateString | null;
}

export type IssueSeverity = "info" | "warning" | "critical";

export interface SeoIssue {
  code: string;
  severity: IssueSeverity;
  message: string;
  recommendation: string;
}

/** Core Web Vitals (Website Audit → Performance), via PageSpeed Insights. */
export type CWVStrategy = "mobile" | "desktop";
export type CWVCategoryKey =
  | "performance"
  | "accessibility"
  | "best_practices"
  | "seo";

/** A Lighthouse audit surfaced as an insight or diagnostic. */
export interface CWVAuditItem {
  id: string;
  title: string;
  description: string;
  score: number | null;
  displayValue: string | null;
  savingsMs: number | null;
  savingsBytes: number | null;
}

export interface CWVCategoryAudits {
  score: number | null;
  insights: CWVAuditItem[];
  diagnostics: CWVAuditItem[];
  passedCount: number;
  passedTitles: string[];
}

/** Lab timing metrics (median). ms except CLS (unitless). */
export interface CWVLabMetrics {
  fcp: number | null;
  lcp: number | null;
  tbt: number | null;
  cls: number | null;
  speedIndex: number | null;
}

export interface CWVRunMetrics extends CWVLabMetrics {
  performanceScore: number | null;
}

export interface CWVScreenshots {
  timeline: string[];
  final: string | null;
}

export interface CWVMetadata {
  lighthouseVersion: string | null;
  formFactor: string | null;
  throttlingMethod: string | null;
  fetchTime: string | null;
  finalUrl: string | null;
}

export interface CoreWebVitalsReport {
  strategy: CWVStrategy;
  metrics: CWVLabMetrics;
  /** Real-user INP (ms) from CrUX field data, or null when unavailable. */
  fieldInp: number | null;
  categories: Record<CWVCategoryKey, CWVCategoryAudits>;
  screenshots: CWVScreenshots;
  metadata: CWVMetadata;
  runs: CWVRunMetrics[];
  lcpElement: string | null;
}

/** A stored Core Web Vitals scan of a single URL. */
export interface CoreWebVitals {
  id: UUID;
  projectId: UUID;
  url: string;
  strategy: CWVStrategy;
  fcp: number | null;
  lcp: number | null;
  tbt: number | null;
  cls: number | null;
  speedIndex: number | null;
  fieldInp: number | null;
  performanceScore: number | null;
  accessibilityScore: number | null;
  bestPracticesScore: number | null;
  seoScore: number | null;
  report: CoreWebVitalsReport | null;
  scannedAt: ISODateString;
  createdAt: ISODateString;
}

/** CWV fix orchestration. */
export type ChangeStatus = "applied" | "reverted";
export type RescanStatus = "completed" | "failed" | "skipped";

/** A recorded, revertible automated fix applied to a connected platform. */
export interface ChangeLog {
  id: UUID;
  projectId: UUID;
  platform: Platform;
  issueType: string;
  /** WordPress change id or Shopify backup theme id. */
  externalChangeId: string | null;
  beforeSnapshot: Record<string, unknown> | null;
  afterSnapshot: Record<string, unknown> | null;
  cwvScoreBefore: number | null;
  cwvScoreAfter: number | null;
  appliedAt: ISODateString;
  status: ChangeStatus;
  createdAt: ISODateString;
}

export type ContentType = "blog" | "product_description" | "landing_page";
export type ContentStatus = "draft" | "published";

/** An AI-generated content piece produced by the Content Studio. */
export interface ContentPiece {
  id: UUID;
  projectId: UUID;
  topic: string;
  targetKeyword: string;
  contentType: ContentType;
  title: string;
  metaDescription: string | null;
  bodyMarkdown: string;
  status: ContentStatus;
  createdAt: ISODateString;
}

/** Standard error envelope returned by the API. */
export interface ApiError {
  detail: string;
  code?: string;
}

/** Generic paginated list response. */
export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

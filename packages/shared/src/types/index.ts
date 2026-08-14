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

/** A website / property being tracked for SEO. */
export interface Project {
  id: UUID;
  ownerId: UUID;
  name: string;
  domain: string;
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

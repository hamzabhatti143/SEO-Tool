/**
 * Constants shared between frontend and backend-facing tooling.
 */
import type { PlanTier } from "./types";

/** Human-readable labels for each subscription tier. */
export const PLAN_LABELS: Record<PlanTier, string> = {
  free: "Free",
  pro: "Pro",
  agency: "Agency",
};

/** Max number of tracked keywords allowed per plan. */
export const KEYWORD_LIMITS: Record<PlanTier, number> = {
  free: 10,
  pro: 1000,
  agency: Number.POSITIVE_INFINITY,
};

/** Default API version prefix. Mirrors `apps/api` routing. */
export const API_V1_PREFIX = "/api/v1";

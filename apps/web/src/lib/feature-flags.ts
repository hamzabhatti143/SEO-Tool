/**
 * Client-side mirror of the backend feature gating
 * (`apps/api/app/core/feature_flags.py`).
 *
 * Two tiers: "standard" and "premium". Standard is denied the premium-only
 * modules below; premium unlocks everything. Keep this list in sync with the
 * server — the server is authoritative and returns 403 for gated endpoints.
 */

export const PREMIUM_FEATURES = [
  "backlink_center",
  "automation",
  "agency_mode",
  "white_label",
] as const;

export type PremiumFeature = (typeof PREMIUM_FEATURES)[number];

export const FEATURE_LABELS: Record<PremiumFeature, string> = {
  backlink_center: "Backlink Center",
  automation: "Automation",
  agency_mode: "Agency Mode",
  white_label: "White-label reports",
};

/** Whether a tier may access a given premium feature. */
export function tierAllows(
  tier: string | undefined,
  feature: PremiumFeature
): boolean {
  if (tier === "premium") return true;
  return !PREMIUM_FEATURES.includes(feature);
}

/** Convenience: is this a premium-tier session? */
export function isPremium(tier: string | undefined): boolean {
  return tier === "premium";
}

"use client";

import * as React from "react";
import Link from "next/link";
import {
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  Loader2,
  Sparkles,
  Wand2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/admin/modal";
import {
  api,
  type FixConfidence,
  type TechnicalIssue,
} from "@/lib/api";

const CATEGORY: Record<string, string> = {
  broken_internal_link: "Broken Links",
  broken_external_link: "Broken Links",
  redirect_chain: "Redirects",
  missing_canonical: "Canonical Issues",
  incorrect_canonical: "Canonical Issues",
  duplicate_content: "Duplicate Content",
  orphan_pages: "Orphan Pages",
  mixed_content: "Mixed Content",
  missing_alt_text: "Missing Alt Text",
  missing_sitemap: "Sitemap",
  sitemap_errors: "Sitemap",
};

const CATEGORY_ORDER = [
  "Broken Links",
  "Redirects",
  "Canonical Issues",
  "Duplicate Content",
  "Orphan Pages",
  "Mixed Content",
  "Missing Alt Text",
  "Sitemap",
];

const CONFIDENCE_VARIANT: Record<
  FixConfidence,
  "success" | "warning" | "secondary"
> = { auto: "success", suggest: "warning", manual: "secondary" };

function d(issue: TechnicalIssue): Record<string, unknown> {
  return issue.details ?? {};
}

/** One-line summary of a finding. */
function summarize(issue: TechnicalIssue): string {
  const det = d(issue);
  switch (issue.issue_type) {
    case "broken_internal_link":
    case "broken_external_link":
      return `${issue.page_url} → HTTP ${det.status_code ?? "?"}`;
    case "redirect_chain":
      return `${issue.page_url} (${det.hops ?? "2+"} hops → ${det.final_url ?? "?"})`;
    case "missing_canonical":
      return `${issue.page_url} — no canonical tag`;
    case "incorrect_canonical":
      return `${issue.page_url} → canonical ${det.canonical ?? "elsewhere"}`;
    case "duplicate_content":
      return `${(det.urls as string[] | undefined)?.length ?? 0} near-identical pages`;
    case "orphan_pages":
      return `${issue.page_url} — 0 inbound internal links`;
    case "mixed_content":
      return `${issue.page_url} — ${(det.resources as unknown[] | undefined)?.length ?? 0} http:// resource(s)`;
    case "missing_alt_text":
      return `${issue.page_url} — ${det.missing_count ?? "?"} image(s) missing alt`;
    case "missing_sitemap":
      return `No /sitemap.xml found`;
    case "sitemap_errors":
      return `${(det.broken_urls as unknown[] | undefined)?.length ?? 0} sitemap URL(s) 404`;
    default:
      return issue.page_url;
  }
}

/** Exactly what an "Apply This Fix" will change (shown in the confirm dialog). */
function describeFix(issue: TechnicalIssue): string {
  const det = d(issue);
  switch (issue.issue_type) {
    case "redirect_chain":
      return `Add/update a redirect so ${issue.page_url} points straight to ${det.final_url}, collapsing the intermediate hops.`;
    case "missing_canonical":
    case "incorrect_canonical":
      return `Set the canonical URL of ${issue.page_url} to itself (self-referential canonical).`;
    case "missing_sitemap":
      return `Enable the site's XML sitemap.`;
    case "broken_internal_link":
      return `Replace the broken link ${issue.page_url} with ${det.suggested_replacement} in the page that references it.`;
    case "mixed_content":
      return `Upgrade ${(det.resources as unknown[] | undefined)?.length ?? 0} http:// resource(s) to https:// on ${issue.page_url}.`;
    case "missing_alt_text":
      return `Add alt text to the image(s) missing it on ${issue.page_url}.`;
    default:
      return `Apply the recommended fix for ${issue.page_url}.`;
  }
}

/** How to resolve a manual issue yourself. */
function guidance(issue: TechnicalIssue): string {
  const det = d(issue);
  switch (issue.issue_type) {
    case "broken_external_link":
      return "Update the link to a working URL, or remove it. External targets can't be auto-fixed.";
    case "duplicate_content":
      return `Pick one canonical URL and add rel="canonical" (or noindex the rest): ${((det.urls as string[]) ?? []).join(", ")}`;
    case "orphan_pages":
      return "Add internal links to this page from related, higher-authority pages so crawlers can find it.";
    case "incorrect_canonical":
      return "This canonical points to another domain — review whether that's intentional before changing it.";
    default:
      return "Review the detected details and fix this manually.";
  }
}

export function TechnicalIssues({ projectId }: { projectId: string }) {
  const [issues, setIssues] = React.useState<TechnicalIssue[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [busyId, setBusyId] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [message, setMessage] = React.useState<string | null>(null);
  const [confirmIssue, setConfirmIssue] = React.useState<TechnicalIssue | null>(
    null
  );

  const load = React.useCallback(async () => {
    try {
      setIssues(await api.listTechnicalIssues(projectId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load issues");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  React.useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  async function applyFix(issue: TechnicalIssue) {
    setBusyId(issue.id);
    setError(null);
    setMessage(null);
    try {
      const res = await api.fixTechnicalIssue(projectId, issue.id);
      setMessage(res.detail ?? "Fix applied.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Fix failed");
    } finally {
      setBusyId(null);
      setConfirmIssue(null);
    }
  }

  async function toggleResolved(issue: TechnicalIssue, resolved: boolean) {
    setBusyId(issue.id);
    try {
      await api.updateTechnicalIssueStatus(
        issue.id,
        resolved ? "ignored" : "open"
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setBusyId(null);
    }
  }

  const grouped = React.useMemo(() => {
    const map = new Map<string, TechnicalIssue[]>();
    for (const issue of issues) {
      const cat = CATEGORY[issue.issue_type] ?? "Other";
      (map.get(cat) ?? map.set(cat, []).get(cat)!).push(issue);
    }
    return CATEGORY_ORDER.filter((c) => map.has(c)).map(
      (c) => [c, map.get(c)!] as const
    );
  }, [issues]);

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading technical-SEO
        issues…
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl font-semibold">Technical SEO Issues</h2>
        <Button asChild variant="outline" size="sm">
          <Link href="/dashboard/fix-history">View Fix History</Link>
        </Button>
      </div>

      {message && (
        <p className="rounded-md border border-emerald-300 bg-emerald-50 p-2 text-sm text-emerald-800">
          {message}
        </p>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}

      {issues.length === 0 ? (
        <div className="flex items-center gap-2 rounded-lg border border-dashed bg-muted/20 p-6 text-sm text-muted-foreground">
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          No technical-SEO issues detected. Run a Website Audit to (re)scan.
        </div>
      ) : (
        grouped.map(([category, items]) => (
          <details
            key={category}
            open
            className="group rounded-lg border bg-card [&_summary::-webkit-details-marker]:hidden"
          >
            <summary className="flex cursor-pointer items-center justify-between p-4">
              <span className="flex items-center gap-2 font-medium">
                {category}
                <Badge variant="secondary">{items.length}</Badge>
              </span>
              <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
            </summary>
            <div className="divide-y border-t">
              {items.map((issue) => (
                <IssueRow
                  key={issue.id}
                  issue={issue}
                  busy={busyId === issue.id}
                  onAuto={() => applyFix(issue)}
                  onSuggest={() => setConfirmIssue(issue)}
                  onToggleResolved={(r) => toggleResolved(issue, r)}
                />
              ))}
            </div>
          </details>
        ))
      )}

      {/* "suggest" confirmation dialog */}
      <Modal
        open={confirmIssue !== null}
        onClose={() => setConfirmIssue(null)}
        title="Apply this fix?"
        description="Review exactly what will change before we apply it."
      >
        {confirmIssue && (
          <div className="space-y-4">
            <div className="rounded-md border bg-muted/40 p-3 text-sm">
              {describeFix(confirmIssue)}
            </div>
            <p className="text-xs text-muted-foreground">
              This is recorded in Fix History and can be reverted.
            </p>
            <div className="flex gap-2">
              <Button
                className="flex-1"
                disabled={busyId === confirmIssue.id}
                onClick={() => applyFix(confirmIssue)}
              >
                {busyId === confirmIssue.id && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Apply fix
              </Button>
              <Button
                variant="outline"
                onClick={() => setConfirmIssue(null)}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

function IssueRow({
  issue,
  busy,
  onAuto,
  onSuggest,
  onToggleResolved,
}: {
  issue: TechnicalIssue;
  busy: boolean;
  onAuto: () => void;
  onSuggest: () => void;
  onToggleResolved: (resolved: boolean) => void;
}) {
  const done = issue.status === "fixed" || issue.status === "ignored";
  return (
    <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={CONFIDENCE_VARIANT[issue.fix_confidence]}>
            {issue.fix_confidence}
          </Badge>
          {issue.status === "fixed" && (
            <Badge variant="success">Fixed</Badge>
          )}
          {issue.status === "ignored" && (
            <Badge variant="secondary">Resolved</Badge>
          )}
          <span className="break-all text-sm font-medium">
            {summarize(issue)}
          </span>
        </div>
        {issue.fix_confidence === "manual" && !done && (
          <p className="text-xs text-muted-foreground">{guidance(issue)}</p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {issue.status === "fixed" ? (
          <span className="text-xs text-muted-foreground">
            Revert in Fix History
          </span>
        ) : issue.fix_confidence === "auto" ? (
          <Button size="sm" disabled={busy} onClick={onAuto}>
            {busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Wand2 className="mr-2 h-4 w-4" />
            )}
            Fix Automatically
          </Button>
        ) : issue.fix_confidence === "suggest" ? (
          <Button size="sm" variant="outline" disabled={busy} onClick={onSuggest}>
            <Sparkles className="mr-2 h-4 w-4" />
            Apply This Fix
          </Button>
        ) : (
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={issue.status === "ignored"}
              disabled={busy}
              onChange={(e) => onToggleResolved(e.target.checked)}
            />
            Mark as Resolved
          </label>
        )}
        {issue.fix_confidence === "manual" && (
          <a
            href={issue.page_url}
            target="_blank"
            rel="noreferrer"
            className="text-muted-foreground hover:text-foreground"
            title="Open page"
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        )}
      </div>
    </div>
  );
}

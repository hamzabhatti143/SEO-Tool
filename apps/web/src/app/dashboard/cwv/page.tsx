"use client";

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Loader2,
  Monitor,
  Smartphone,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useProject } from "@/components/project-provider";
import {
  api,
  type CoreWebVitals,
  type CWVAuditItem,
  type CWVCategoryAudits,
  type CWVCategoryKey,
  type CWVStrategy,
  type FixResponse,
} from "@/lib/api";

// --- metric thresholds (Google): [good ≤, needs-improvement ≤] -------------
type MetricKey = "FCP" | "LCP" | "TBT" | "CLS" | "SI" | "INP";
const THRESHOLDS: Record<MetricKey, [number, number]> = {
  FCP: [1800, 3000],
  LCP: [2500, 4000],
  TBT: [200, 600],
  CLS: [0.1, 0.25],
  SI: [3400, 5800],
  INP: [200, 500],
};

type Rating = "good" | "ni" | "poor" | "unknown";

function rate(kind: MetricKey, v: number | null): Rating {
  if (v == null) return "unknown";
  const [g, n] = THRESHOLDS[kind];
  return v <= g ? "good" : v <= n ? "ni" : "poor";
}

const RATING_TEXT: Record<Rating, string> = {
  good: "text-emerald-600",
  ni: "text-amber-600",
  poor: "text-destructive",
  unknown: "text-muted-foreground",
};

function fmtMs(v: number): string {
  return v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`;
}

function fmtMetric(kind: MetricKey, v: number | null): string {
  if (v == null) return "—";
  return kind === "CLS" ? v.toFixed(3) : fmtMs(v);
}

/** Color for a 0–100 category score: green ≥90, orange 50–89, red <50. */
function scoreColor(score: number | null): { text: string; stroke: string } {
  if (score == null)
    return { text: "text-muted-foreground", stroke: "stroke-muted-foreground" };
  if (score >= 90)
    return { text: "text-emerald-600", stroke: "stroke-emerald-500" };
  if (score >= 50) return { text: "text-amber-600", stroke: "stroke-amber-500" };
  return { text: "text-destructive", stroke: "stroke-red-500" };
}

/** Strip Lighthouse markdown ([text](url), `code`) to readable text. */
function stripMd(s: string): string {
  return s
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/`([^`]+)`/g, "$1");
}

const CATEGORY_LABEL: Record<CWVCategoryKey, string> = {
  performance: "Performance",
  accessibility: "Accessibility",
  best_practices: "Best Practices",
  seo: "SEO",
};

export default function CoreWebVitalsPage() {
  const { currentProject } = useProject();
  const [url, setUrl] = React.useState("");
  const [strategy, setStrategy] = React.useState<CWVStrategy>("mobile");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [scan, setScan] = React.useState<CoreWebVitals | null>(null);
  const [history, setHistory] = React.useState<CoreWebVitals[]>([]);

  const [fixing, setFixing] = React.useState(false);
  const [fixError, setFixError] = React.useState<string | null>(null);
  const [fixResult, setFixResult] = React.useState<FixResponse | null>(null);

  const loadHistory = React.useCallback(async (projectId: string) => {
    try {
      setHistory(await api.listCoreWebVitals(projectId));
    } catch {
      /* best-effort */
    }
  }, []);

  const showScan = React.useCallback((s: CoreWebVitals | null) => {
    setScan(s);
    setFixResult(null);
    setFixError(null);
  }, []);

  React.useEffect(() => {
    showScan(null);
    if (currentProject) loadHistory(currentProject.id);
    else setHistory([]);
  }, [currentProject, loadHistory, showScan]);

  async function handleRun(e: React.FormEvent) {
    e.preventDefault();
    if (!currentProject) {
      setError("Select or create a project first.");
      return;
    }
    setBusy(true);
    setError(null);
    showScan(null);
    try {
      const result = await api.runCoreWebVitals({
        project_id: currentProject.id,
        url,
        strategy,
      });
      showScan(result);
      await loadHistory(currentProject.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleFixAll() {
    if (!currentProject || !scan) return;
    setFixing(true);
    setFixError(null);
    setFixResult(null);
    try {
      const result = await api.fixAllCwv(currentProject.id, scan.url);
      setFixResult(result);
      await loadHistory(currentProject.id);
    } catch (e) {
      setFixError(e instanceof Error ? e.message : "Fix failed");
    } finally {
      setFixing(false);
    }
  }

  const notConnected = currentProject?.platform === "custom";
  const report = scan?.report;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Core Web Vitals</h1>
        <p className="text-muted-foreground">
          Powered by the Google PageSpeed Insights API — the same lab + field
          data as pagespeed.web.dev.
        </p>
      </header>

      {/* URL + device toggle + analyze */}
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleRun} className="flex flex-wrap items-end gap-3">
            <div className="min-w-[240px] flex-1 space-y-2">
              <Label htmlFor="url">Page URL</Label>
              <Input
                id="url"
                placeholder="https://example.com/page"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label>Device</Label>
              <div className="flex rounded-md border p-0.5">
                {(
                  [
                    ["mobile", Smartphone],
                    ["desktop", Monitor],
                  ] as const
                ).map(([s, Icon]) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setStrategy(s)}
                    className={`flex items-center gap-1.5 rounded px-3 py-1.5 text-sm capitalize transition-colors ${
                      strategy === s
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {s}
                  </button>
                ))}
              </div>
            </div>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {busy ? "Analyzing…" : "Analyze"}
            </Button>
          </form>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
          {busy && (
            <p className="mt-3 text-sm text-muted-foreground">
              Running {strategy} analysis via PageSpeed Insights — this takes
              ~30–60 seconds (2 runs for a median).
            </p>
          )}
        </CardContent>
      </Card>

      {scan && report && (
        <>
          {/* Four category score circles */}
          <Card>
            <CardContent className="grid grid-cols-2 gap-4 pt-6 sm:grid-cols-4">
              <ScoreCircle
                label="Performance"
                score={scan.performance_score}
                size={84}
              />
              <ScoreCircle
                label="Accessibility"
                score={scan.accessibility_score}
                size={84}
              />
              <ScoreCircle
                label="Best Practices"
                score={scan.best_practices_score}
                size={84}
              />
              <ScoreCircle label="SEO" score={scan.seo_score} size={84} />
            </CardContent>
          </Card>

          {/* Performance: big circle + final screenshot */}
          <Card>
            <CardHeader>
              <CardTitle>Performance</CardTitle>
              <CardDescription>
                Lab metrics from a simulated {report.metadata.form_factor ??
                  strategy}{" "}
                load (median of {report.runs.length} run
                {report.runs.length === 1 ? "" : "s"}).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex flex-wrap items-center gap-6">
                <ScoreCircle
                  label="Performance"
                  score={scan.performance_score}
                  size={128}
                />
                {report.screenshots.final && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={report.screenshots.final}
                    alt="Final rendered screenshot"
                    className="max-h-40 rounded-md border"
                  />
                )}
              </div>

              {/* Metrics grid */}
              <div className="grid gap-3 sm:grid-cols-2">
                <MetricCard kind="FCP" label="First Contentful Paint" value={scan.fcp} />
                <MetricCard kind="LCP" label="Largest Contentful Paint" value={scan.lcp} />
                <MetricCard kind="TBT" label="Total Blocking Time" value={scan.tbt} />
                <MetricCard kind="CLS" label="Cumulative Layout Shift" value={scan.cls} />
                <MetricCard kind="SI" label="Speed Index" value={scan.speed_index} />
                <InpCard value={scan.field_inp} />
              </div>

              {/* Metadata */}
              <p className="text-xs text-muted-foreground">
                Captured{" "}
                {report.metadata.fetch_time
                  ? new Date(report.metadata.fetch_time).toLocaleString()
                  : new Date(scan.scanned_at).toLocaleString()}
                {" · "}Device: {report.metadata.form_factor ?? strategy}
                {" · "}Throttling: {report.metadata.throttling_method ?? "—"}
                {" · "}Lighthouse {report.metadata.lighthouse_version ?? "—"}
              </p>

              {/* Timeline screenshots */}
              {report.screenshots.timeline.length > 0 && (
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {report.screenshots.timeline.map((src, i) => (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      key={i}
                      src={src}
                      alt={`Load frame ${i + 1}`}
                      className="h-24 shrink-0 rounded border"
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Performance insights / diagnostics / passed */}
          <CategoryAuditCards
            title="Performance"
            audits={report.categories.performance}
            showScoreHeader={false}
          />

          {/* Auto-fix */}
          <Card>
            <CardHeader>
              <CardTitle>Auto-fix</CardTitle>
              <CardDescription>
                Apply fixes to your connected site
                {currentProject ? ` (${currentProject.platform})` : ""}, then
                re-analyze to measure the impact.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {fixResult ? (
                <BeforeAfter before={scan} result={fixResult} />
              ) : (
                <div className="space-y-2">
                  <Button onClick={handleFixAll} disabled={fixing || notConnected}>
                    {fixing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {fixing ? "Applying fixes & re-analyzing…" : "Fix All Issues"}
                  </Button>
                  {notConnected ? (
                    <p className="text-sm text-muted-foreground">
                      Connect your site to apply fixes.{" "}
                      <a href="/dashboard/connect" className="underline">
                        Connect Your Site →
                      </a>
                    </p>
                  ) : null}
                  {fixError && (
                    <p className="text-sm text-destructive">{fixError}</p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Accessibility / Best Practices / SEO */}
          {(["accessibility", "best_practices", "seo"] as const).map((key) => (
            <CategoryAuditCards
              key={key}
              title={CATEGORY_LABEL[key]}
              audits={report.categories[key]}
              showScoreHeader
            />
          ))}
        </>
      )}

      {history.length > 0 && (
        <ScanHistory scans={history} selectedId={scan?.id ?? null} onSelect={showScan} />
      )}
    </div>
  );
}

function ScoreCircle({
  label,
  score,
  size,
}: {
  label: string;
  score: number | null;
  size: number;
}) {
  const { text, stroke } = scoreColor(score);
  const r = 42;
  const circ = 2 * Math.PI * r;
  const dash = circ * ((score ?? 0) / 100);
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          <circle cx="50" cy="50" r={r} className="stroke-muted" strokeWidth="8" fill="none" />
          <circle
            cx="50"
            cy="50"
            r={r}
            className={stroke}
            strokeWidth="8"
            fill="none"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circ}`}
          />
        </svg>
        <div className={`absolute inset-0 flex items-center justify-center text-xl font-bold ${text}`}>
          {score ?? "—"}
        </div>
      </div>
      <span className="text-center text-xs font-medium">{label}</span>
    </div>
  );
}

function MetricCard({
  kind,
  label,
  value,
}: {
  kind: MetricKey;
  label: string;
  value: number | null;
}) {
  const color = RATING_TEXT[rate(kind, value)];
  return (
    <div className="flex items-center justify-between rounded-md border p-3">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`text-lg font-semibold ${color}`}>
        {fmtMetric(kind, value)}
      </span>
    </div>
  );
}

function InpCard({ value }: { value: number | null }) {
  return (
    <div className="flex items-center justify-between rounded-md border border-dashed p-3">
      <span className="text-sm text-muted-foreground">
        INP <span className="text-xs">(field)</span>
      </span>
      {value == null ? (
        <span className="text-sm text-muted-foreground">
          No field data available
        </span>
      ) : (
        <span className={`text-lg font-semibold ${RATING_TEXT[rate("INP", value)]}`}>
          {fmtMs(value)}
        </span>
      )}
    </div>
  );
}

function CategoryAuditCards({
  title,
  audits,
  showScoreHeader,
}: {
  title: string;
  audits: CWVCategoryAudits | undefined;
  showScoreHeader: boolean;
}) {
  if (!audits) return null;
  const hasInsights = audits.insights.length > 0;
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          {showScoreHeader && (
            <ScoreCircle label="" score={audits.score} size={56} />
          )}
          <CardTitle>{title}</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {hasInsights && (
          <AuditSection
            heading="Insights"
            items={audits.insights}
            defaultOpen
          />
        )}
        <AuditSection
          heading="Diagnostics"
          items={audits.diagnostics}
          defaultOpen={!hasInsights}
        />
        <PassedAudits count={audits.passed_count} titles={audits.passed_titles} />
        {!hasInsights &&
          audits.diagnostics.length === 0 &&
          audits.passed_count === 0 && (
            <p className="text-sm text-muted-foreground">No audits reported.</p>
          )}
      </CardContent>
    </Card>
  );
}

function AuditSection({
  heading,
  items,
  defaultOpen,
}: {
  heading: string;
  items: CWVAuditItem[];
  defaultOpen: boolean;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  if (items.length === 0) return null;
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between py-1 text-left"
      >
        <span className="text-sm font-semibold">
          {heading} ({items.length})
        </span>
        <ChevronDown
          className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="mt-1 space-y-1">
          {items.map((a) => (
            <AuditRow key={a.id} audit={a} />
          ))}
        </div>
      )}
    </div>
  );
}

function AuditRow({ audit }: { audit: CWVAuditItem }) {
  const [open, setOpen] = React.useState(false);
  // Dot color: worse score → redder; informational (null) → muted.
  const dot =
    audit.score == null
      ? "bg-muted-foreground"
      : audit.score < 0.5
        ? "bg-red-500"
        : audit.score < 0.9
          ? "bg-amber-500"
          : "bg-emerald-500";
  const savings =
    audit.display_value ??
    (audit.savings_ms != null
      ? `Est savings: ${fmtMs(audit.savings_ms)}`
      : audit.savings_bytes != null
        ? `Est savings: ${Math.round(audit.savings_bytes / 1024)} KB`
        : null);
  return (
    <div className="rounded-md border">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 p-3 text-left"
      >
        <span className={`h-2 w-2 shrink-0 rounded-full ${dot}`} />
        <span className="flex-1 text-sm">{audit.title}</span>
        {savings && (
          <span className="shrink-0 text-xs font-medium text-amber-600">
            {savings}
          </span>
        )}
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>
      {open && audit.description && (
        <p className="border-t px-3 py-2 text-xs text-muted-foreground">
          {stripMd(audit.description)}
        </p>
      )}
    </div>
  );
}

function PassedAudits({ count, titles }: { count: number; titles: string[] }) {
  const [open, setOpen] = React.useState(false);
  if (count === 0) return null;
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between py-1 text-left"
      >
        <span className="flex items-center gap-1.5 text-sm font-semibold text-emerald-600">
          <CheckCircle2 className="h-4 w-4" /> Passed Audits ({count})
        </span>
        <ChevronDown
          className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <ul className="mt-1 space-y-1">
          {titles.map((t, i) => (
            <li
              key={i}
              className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm text-muted-foreground"
            >
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
              {t}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function BeforeAfter({
  before,
  result,
}: {
  before: CoreWebVitals;
  result: FixResponse;
}) {
  const after = result.new_scan;
  return (
    <div className="space-y-4">
      {result.rescan_status !== "completed" && (
        <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{result.detail ?? "Fixes applied; re-analysis incomplete."}</span>
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-4">
        <Compare label="Performance" before={before.performance_score} after={after?.performance_score ?? null} higherBetter />
        <Compare label="LCP" kind="LCP" before={before.lcp} after={after?.lcp ?? null} />
        <Compare label="TBT" kind="TBT" before={before.tbt} after={after?.tbt ?? null} />
        <Compare label="CLS" kind="CLS" before={before.cls} after={after?.cls ?? null} />
      </div>
      <p className="text-xs text-muted-foreground">
        Change <code>{result.change.external_change_id ?? result.change.id}</code>{" "}
        · <Badge variant="success">{result.change.status}</Badge> — revert from{" "}
        <a href="/dashboard/fix-history" className="underline">
          Fix History
        </a>
        .
      </p>
    </div>
  );
}

function Compare({
  label,
  kind,
  before,
  after,
  higherBetter = false,
}: {
  label: string;
  kind?: MetricKey;
  before: number | null;
  after: number | null;
  higherBetter?: boolean;
}) {
  const fmt = (v: number | null) =>
    kind ? fmtMetric(kind, v) : v == null ? "—" : String(Math.round(v));
  const improved =
    before != null && after != null && (higherBetter ? after > before : after < before);
  const worse =
    before != null && after != null && (higherBetter ? after < before : after > before);
  const color = improved
    ? "text-emerald-600"
    : worse
      ? "text-destructive"
      : "text-muted-foreground";
  return (
    <div className="rounded-md border p-3">
      <p className="text-xs uppercase text-muted-foreground">{label}</p>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="text-sm text-muted-foreground">{fmt(before)}</span>
        <span className="text-muted-foreground">→</span>
        <span className={`text-lg font-bold ${color}`}>{fmt(after)}</span>
      </div>
    </div>
  );
}

function ScanHistory({
  scans,
  selectedId,
  onSelect,
}: {
  scans: CoreWebVitals[];
  selectedId: string | null;
  onSelect: (scan: CoreWebVitals) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Scan history ({scans.length})</CardTitle>
        <CardDescription>Select a past scan to view its report.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {scans.map((s) => {
          const selected = s.id === selectedId;
          const { text } = scoreColor(s.performance_score);
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => onSelect(s)}
              className={`flex w-full flex-wrap items-center gap-3 rounded-md border p-3 text-left transition-colors hover:bg-accent ${
                selected ? "border-primary bg-accent" : ""
              }`}
            >
              <span className={`text-lg font-bold ${text}`}>
                {s.performance_score ?? "—"}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{s.url}</p>
                <p className="text-xs text-muted-foreground">
                  {s.strategy} · {new Date(s.scanned_at).toLocaleString()}
                </p>
              </div>
              <span className="text-xs text-muted-foreground">
                LCP {fmtMetric("LCP", s.lcp)}
              </span>
            </button>
          );
        })}
      </CardContent>
    </Card>
  );
}

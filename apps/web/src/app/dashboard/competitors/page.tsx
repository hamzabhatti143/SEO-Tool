"use client";

import * as React from "react";
import { Info, Loader2 } from "lucide-react";

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
  runJob,
  type CompetitorReport,
  type CrawledSite,
} from "@/lib/api";

const EMPHASIS_VARIANT = {
  high: "destructive",
  medium: "warning",
  low: "secondary",
} as const;

/** Small inline marker for AI-estimated (non-measured) figures. */
function AiEstimated() {
  return (
    <Badge variant="outline" className="ml-2 align-middle text-[10px]">
      AI Estimated
    </Badge>
  );
}

/** Styled marker: accurate values for this metric require a paid data source. */
function PaidFeature() {
  return (
    <Badge className="ml-2 align-middle border-0 bg-gradient-to-r from-amber-500 to-yellow-400 text-[10px] font-semibold uppercase tracking-wide text-white shadow-sm">
      Paid Feature
    </Badge>
  );
}

/** Marker for figures measured directly from the crawl. */
function Measured() {
  return (
    <Badge
      variant="secondary"
      className="ml-2 align-middle text-[10px] font-normal"
    >
      Measured
    </Badge>
  );
}

/** Banner shown when a site could not be fully crawled. */
function CrawlStatusBanner({ site, label }: { site: CrawledSite; label: string }) {
  if (site.crawl_status.ok) {
    const s = site.structure;
    if (s.pages_crawled < s.pages_discovered) {
      return (
        <p className="text-xs text-muted-foreground">
          {label}: crawled {s.pages_crawled} of {s.pages_discovered} discovered
          pages{s.disallowed_by_robots > 0 ? ` (${s.disallowed_by_robots} disallowed by robots.txt)` : ""}.
        </p>
      );
    }
    return null;
  }
  return (
    <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
      <Info className="mt-0.5 h-4 w-4 shrink-0" />
      <span>
        <span className="font-medium">{label} could not be crawled</span> (
        {site.crawl_status.reason}). {site.crawl_status.detail}
      </span>
    </div>
  );
}

export default function CompetitorsPage() {
  const { currentProject } = useProject();
  const [url, setUrl] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [report, setReport] = React.useState<CompetitorReport | null>(null);

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault();
    if (!currentProject) {
      setError("Select or create a project first.");
      return;
    }
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      const res = await runJob<CompetitorReport>(() =>
        api.enqueueCompetitor({
          project_id: currentProject.id,
          competitor_url: url,
        })
      );
      setReport(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Competitor analysis failed");
    } finally {
      setBusy(false);
    }
  }

  const r = report;
  const a = r?.analysis;
  const comp = r?.competitor;
  const us = r?.user_site;
  const usr = r?.user_project;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">
          Competitor Intelligence
        </h1>
        <p className="text-muted-foreground">
          Crawl a competitor and compare their topic focus and content strategy
          against your project — surfacing keyword and content gaps.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Analyze a competitor</CardTitle>
          <CardDescription>
            Compared against{" "}
            <span className="font-medium">
              {currentProject?.name ?? "your project"}
            </span>
            {currentProject ? ` (${currentProject.domain})` : ""}.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAnalyze} className="flex items-end gap-3">
            <div className="flex-1 space-y-2">
              <Label htmlFor="url">Competitor URL</Label>
              <Input
                id="url"
                placeholder="https://competitor.com"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
              />
            </div>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {busy ? "Analyzing…" : "Analyze"}
            </Button>
          </form>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {r && a && comp && us && usr && (
        <>
          {/* Crawl status for each site (explicit reason if a crawl failed) */}
          <div className="space-y-2">
            <CrawlStatusBanner site={us} label="Your site" />
            <CrawlStatusBanner site={comp} label="Competitor" />
          </div>

          {/* Disclaimer */}
          <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{r.disclaimer}</span>
          </div>

          {/* Side-by-side comparison */}
          <Card>
            <CardHeader>
              <CardTitle>You vs. competitor</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto p-0">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/50 text-left">
                  <tr>
                    <th className="p-3 font-medium">Metric</th>
                    <th className="p-3 font-medium">
                      Your project
                      <div className="text-xs font-normal text-muted-foreground">
                        {usr.domain}
                      </div>
                    </th>
                    <th className="p-3 font-medium">
                      Competitor
                      <div className="text-xs font-normal text-muted-foreground">
                        {comp.domain}
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <CompareRow
                    metric="Pages (crawled / discovered)"
                    marker={<Measured />}
                    user={`${us.structure.pages_crawled} / ${us.structure.pages_discovered}`}
                    competitor={`${comp.structure.pages_crawled} / ${comp.structure.pages_discovered}`}
                  />
                  <CompareRow
                    metric="Sitemap URLs"
                    marker={<Measured />}
                    user={us.structure.sitemap_url_count?.toString() ?? "n/a"}
                    competitor={
                      comp.structure.sitemap_url_count?.toString() ?? "n/a"
                    }
                  />
                  <CompareRow
                    metric="Indexable pages crawled"
                    marker={<Measured />}
                    user={String(us.structure.indexable_pages)}
                    competitor={String(comp.structure.indexable_pages)}
                  />
                  <CompareRow
                    metric="Avg words / page"
                    marker={<Measured />}
                    user={String(us.structure.avg_word_count)}
                    competitor={String(comp.structure.avg_word_count)}
                  />
                  <CompareRow
                    metric="Avg internal links / page"
                    marker={<Measured />}
                    user={String(us.structure.avg_internal_links_per_page)}
                    competitor={String(
                      comp.structure.avg_internal_links_per_page
                    )}
                  />
                  <tr className="border-b">
                    <td className="p-3 text-muted-foreground">
                      Est. monthly traffic
                      {a.traffic_source === "provider" ? (
                        <Measured />
                      ) : (
                        <>
                          <AiEstimated />
                          <PaidFeature />
                        </>
                      )}
                    </td>
                    <td className="p-3 font-medium">
                      {a.user_estimated_traffic_band}
                    </td>
                    <td className="p-3 font-medium">
                      {a.estimated_traffic_band}
                    </td>
                  </tr>
                  <tr className="border-b">
                    <td className="p-3 text-muted-foreground">
                      Est. authority (0–100)
                      {a.authority_source === "provider" ? (
                        <Measured />
                      ) : (
                        <>
                          <AiEstimated />
                          <PaidFeature />
                        </>
                      )}
                    </td>
                    <td className="p-3 font-medium">
                      {a.user_estimated_authority}
                    </td>
                    <td className="p-3 font-medium">{a.estimated_authority}</td>
                  </tr>
                  <tr>
                    <td className="p-3 align-top text-muted-foreground">
                      Top topics
                      <Measured />
                    </td>
                    <td className="p-3 align-top">
                      <ChipList items={r.comparison.user_topics.slice(0, 12)} />
                    </td>
                    <td className="p-3 align-top">
                      <ChipList
                        items={r.comparison.competitor_topics.slice(0, 12)}
                      />
                    </td>
                  </tr>
                </tbody>
              </table>
            </CardContent>
          </Card>

          {/* Content strategy + topic focus */}
          <Card>
            <CardHeader>
              <CardTitle>
                Competitor content strategy
                <AiEstimated />
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {a.content_strategy}
              </p>
              <div className="space-y-2">
                {a.topic_focus_areas.map((t, i) => (
                  <div
                    key={i}
                    className="flex items-start justify-between gap-3 rounded-md border p-2"
                  >
                    <div>
                      <span className="text-sm font-medium">{t.topic}</span>
                      {t.note && (
                        <p className="text-xs text-muted-foreground">
                          {t.note}
                        </p>
                      )}
                    </div>
                    <Badge variant={EMPHASIS_VARIANT[t.emphasis]}>
                      {t.emphasis}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Gaps */}
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Keyword gaps</CardTitle>
                <CardDescription>
                  Keywords the competitor targets that you don&apos;t.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {a.keyword_gaps.length ? (
                  <ChipList items={a.keyword_gaps} variant="warning" />
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No notable keyword gaps found.
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Shared topics</CardTitle>
                <CardDescription>Covered by both sites.</CardDescription>
              </CardHeader>
              <CardContent>
                {a.shared_topics.length ? (
                  <ChipList items={a.shared_topics} variant="success" />
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No clear overlap detected.
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Content gaps</CardTitle>
              <CardDescription>
                Topics the competitor covers that your project is missing.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {a.content_gaps.length ? (
                a.content_gaps.map((g, i) => (
                  <div key={i} className="rounded-md border p-3">
                    <span className="text-sm font-medium">{g.topic}</span>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {g.rationale}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">
                  No content gaps found.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Recommendations */}
          {a.recommendations.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Recommendations</CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="list-decimal space-y-1 pl-5 text-sm">
                  {a.recommendations.map((rec, i) => (
                    <li key={i}>{rec}</li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function CompareRow({
  metric,
  user,
  competitor,
  marker,
}: {
  metric: string;
  user: string;
  competitor: string;
  marker?: React.ReactNode;
}) {
  return (
    <tr className="border-b">
      <td className="p-3 text-muted-foreground">
        {metric}
        {marker}
      </td>
      <td className="p-3">{user}</td>
      <td className="p-3">{competitor}</td>
    </tr>
  );
}

function ChipList({
  items,
  variant = "secondary",
}: {
  items: string[];
  variant?: "secondary" | "warning" | "success";
}) {
  if (!items.length) return <span className="text-muted-foreground">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((it, i) => (
        <Badge key={i} variant={variant}>
          {it}
        </Badge>
      ))}
    </div>
  );
}

"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import { Loader2, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useProject } from "@/components/project-provider";
import { api, runJob, type InternalLinkAnalysis } from "@/lib/api";

// react-flow touches the DOM, so load it client-only.
const LinkGraph = dynamic(() => import("@/components/link-graph"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[520px] items-center justify-center rounded-md border text-sm text-muted-foreground">
      Loading graph…
    </div>
  ),
});

export default function InternalLinksPage() {
  const { currentProject } = useProject();
  const [analysis, setAnalysis] = React.useState<InternalLinkAnalysis | null>(
    null
  );
  const [loading, setLoading] = React.useState(false);
  const [crawling, setCrawling] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const loadAnalysis = React.useCallback(async (projectId: string) => {
    setLoading(true);
    setError(null);
    try {
      setAnalysis(await api.getInternalLinkAnalysis(projectId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load analysis");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (currentProject) loadAnalysis(currentProject.id);
  }, [currentProject, loadAnalysis]);

  async function handleCrawl() {
    if (!currentProject) return;
    setCrawling(true);
    setError(null);
    try {
      await runJob(() => api.enqueueInternalLinkCrawl(currentProject.id));
      await loadAnalysis(currentProject.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Crawl failed");
    } finally {
      setCrawling(false);
    }
  }

  const empty = analysis && analysis.page_count === 0;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Internal Link Optimizer
          </h1>
          <p className="text-muted-foreground">
            Crawl your site, map its internal link graph, find orphan pages,
            and get semantic linking suggestions.
          </p>
        </div>
        <Button onClick={handleCrawl} disabled={crawling || !currentProject}>
          {crawling ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          {crawling ? "Crawling…" : "Crawl site"}
        </Button>
      </header>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && !analysis && (
        <p className="text-sm text-muted-foreground">Loading…</p>
      )}

      {empty && !crawling && (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            No pages crawled yet for{" "}
            <span className="font-medium">{currentProject?.name}</span>. Click{" "}
            <span className="font-medium">Crawl site</span> to build the link
            graph.
          </CardContent>
        </Card>
      )}

      {analysis && analysis.page_count > 0 && (
        <>
          {/* Stats */}
          <div className="grid gap-4 sm:grid-cols-3">
            <Stat label="Pages" value={analysis.page_count} />
            <Stat
              label="Orphan pages"
              value={analysis.orphans.length}
              tone={analysis.orphans.length > 0 ? "bad" : "good"}
            />
            <Stat label="Link suggestions" value={analysis.suggestions.length} />
          </div>

          {/* Graph */}
          <Card>
            <CardHeader>
              <CardTitle>Internal link graph</CardTitle>
              <CardDescription>
                Arrows show existing internal links. Red nodes are orphan pages
                (no internal links point to them).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <LinkGraph nodes={analysis.nodes} edges={analysis.edges} />
            </CardContent>
          </Card>

          {/* Orphans */}
          {analysis.orphans.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Orphan pages ({analysis.orphans.length})</CardTitle>
                <CardDescription>
                  These pages have no internal links pointing to them — add
                  links from related pages.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-1">
                {analysis.orphans.map((p) => (
                  <div key={p.id} className="text-sm">
                    <span className="font-medium">{p.title || p.url}</span>{" "}
                    <span className="text-muted-foreground">{p.url}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Suggestions */}
          <Card>
            <CardHeader>
              <CardTitle>
                Linking opportunities ({analysis.suggestions.length})
              </CardTitle>
              <CardDescription>
                Semantically-related pages that aren&apos;t linked yet.
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto p-0">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/50 text-left">
                  <tr>
                    <th className="p-3 font-medium">From page</th>
                    <th className="p-3 font-medium">Should link to</th>
                    <th className="p-3 font-medium">Suggested anchor</th>
                    <th className="p-3 font-medium">Similarity</th>
                  </tr>
                </thead>
                <tbody>
                  {analysis.suggestions.map((s, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="max-w-[220px] truncate p-3" title={s.from_url}>
                        {s.from_title}
                      </td>
                      <td className="max-w-[220px] truncate p-3" title={s.to_url}>
                        {s.to_title}
                      </td>
                      <td className="p-3">
                        <Badge variant="secondary">{s.anchor_text}</Badge>
                      </td>
                      <td className="p-3">{s.similarity.toFixed(2)}</td>
                    </tr>
                  ))}
                  {analysis.suggestions.length === 0 && (
                    <tr>
                      <td
                        colSpan={4}
                        className="p-6 text-center text-muted-foreground"
                      >
                        No linking opportunities found (need embeddings + at
                        least two related pages).
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "good" | "bad";
}) {
  const color =
    tone === "good"
      ? "text-emerald-600"
      : tone === "bad"
        ? "text-destructive"
        : "";
  return (
    <Card>
      <CardContent className="pt-6">
        <p className="text-xs uppercase text-muted-foreground">{label}</p>
        <p className={`text-2xl font-bold ${color}`}>{value}</p>
      </CardContent>
    </Card>
  );
}

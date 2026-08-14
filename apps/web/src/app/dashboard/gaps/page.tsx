"use client";

import * as React from "react";
import Link from "next/link";
import { Loader2, Plus, Sparkles, X } from "lucide-react";

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
  type ContentBrief,
  type GapAnalysisResponse,
  type GapPriority,
} from "@/lib/api";

const COLUMNS: { key: GapPriority; label: string; accent: string }[] = [
  { key: "high", label: "High priority", accent: "border-t-red-500" },
  { key: "medium", label: "Medium priority", accent: "border-t-amber-500" },
  { key: "low", label: "Low priority", accent: "border-t-slate-400" },
];

export default function GapsPage() {
  const { currentProject } = useProject();
  const [urls, setUrls] = React.useState<string[]>(["", ""]);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<GapAnalysisResponse | null>(null);

  function setUrl(i: number, value: string) {
    setUrls((prev) => prev.map((u, idx) => (idx === i ? value : u)));
  }

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault();
    if (!currentProject) {
      setError("Select or create a project first.");
      return;
    }
    const competitorUrls = urls.map((u) => u.trim()).filter(Boolean);
    if (competitorUrls.length === 0) {
      setError("Enter at least one competitor URL.");
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await runJob<GapAnalysisResponse>(() =>
        api.enqueueGaps({
          project_id: currentProject.id,
          competitor_urls: competitorUrls,
        })
      );
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gap analysis failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Content Gaps</h1>
        <p className="text-muted-foreground">
          Compare 2–3 competitors against your project to uncover content
          opportunities — each with a ready-to-use brief.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Analyze content gaps</CardTitle>
          <CardDescription>
            Compared against{" "}
            <span className="font-medium">
              {currentProject?.name ?? "your project"}
            </span>
            .
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAnalyze} className="space-y-3">
            {urls.map((u, i) => (
              <div key={i} className="flex items-end gap-2">
                <div className="flex-1 space-y-1">
                  <Label htmlFor={`url-${i}`} className="text-xs">
                    Competitor {i + 1}
                  </Label>
                  <Input
                    id={`url-${i}`}
                    placeholder="https://competitor.com"
                    value={u}
                    onChange={(e) => setUrl(i, e.target.value)}
                  />
                </div>
                {urls.length > 1 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() =>
                      setUrls((p) => p.filter((_, idx) => idx !== i))
                    }
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
            <div className="flex items-center gap-3">
              {urls.length < 3 && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setUrls((p) => [...p, ""])}
                >
                  <Plus className="mr-1 h-4 w-4" />
                  Add competitor
                </Button>
              )}
              <Button type="submit" disabled={busy}>
                {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {busy ? "Analyzing…" : "Find gaps"}
              </Button>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </form>
        </CardContent>
      </Card>

      {result && (
        <>
          {/* Missing topics / FAQs */}
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Missing topics</CardTitle>
                <CardDescription>
                  Covered by competitors, not by you.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ChipList items={result.missing_topics} variant="warning" />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Missing FAQs</CardTitle>
                <CardDescription>
                  People-Also-Ask questions to answer.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {result.missing_faqs.length ? (
                  <ul className="list-disc space-y-1 pl-5 text-sm">
                    {result.missing_faqs.map((q, i) => (
                      <li key={i}>{q}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">None found.</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Kanban board of content opportunities */}
          <div>
            <h2 className="mb-3 text-lg font-semibold">
              Content Opportunities ({result.content_briefs.length})
            </h2>
            <div className="grid gap-4 md:grid-cols-3">
              {COLUMNS.map((col) => {
                const briefs = result.content_briefs.filter(
                  (b) => b.priority === col.key
                );
                return (
                  <div key={col.key} className="space-y-3">
                    <div
                      className={`rounded-md border-t-4 bg-muted/40 p-2 text-sm font-medium ${col.accent}`}
                    >
                      {col.label} ({briefs.length})
                    </div>
                    {briefs.map((brief, i) => (
                      <BriefCard key={i} brief={brief} />
                    ))}
                    {briefs.length === 0 && (
                      <p className="px-1 text-xs text-muted-foreground">
                        No opportunities.
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function BriefCard({ brief }: { brief: ContentBrief }) {
  const href =
    `/dashboard/content?topic=${encodeURIComponent(brief.title)}` +
    `&target_keyword=${encodeURIComponent(brief.target_keyword)}` +
    `&content_type=${encodeURIComponent(brief.content_type)}`;

  return (
    <Card>
      <CardContent className="space-y-3 pt-4">
        <div>
          <h3 className="font-medium leading-snug">{brief.title}</h3>
          <p className="mt-1 text-xs text-muted-foreground">{brief.rationale}</p>
        </div>

        <div className="flex flex-wrap gap-1 text-xs">
          <Badge variant="secondary">{brief.target_keyword}</Badge>
          <Badge variant="outline">{brief.content_type}</Badge>
          <Badge variant="outline">~{brief.word_count_target} words</Badge>
        </div>

        <details className="group text-sm [&_summary::-webkit-details-marker]:hidden">
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
            Outline ({brief.outline.length}) ▾
          </summary>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
            {brief.outline.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </details>

        <Button asChild size="sm" className="w-full">
          <Link href={href}>
            <Sparkles className="mr-2 h-4 w-4" />
            Generate in Content Studio
          </Link>
        </Button>
      </CardContent>
    </Card>
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

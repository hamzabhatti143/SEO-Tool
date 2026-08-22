"use client";

import * as React from "react";
import { Check, ChevronDown, Loader2, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  api,
  type OptimizeResponse,
  type OptimizerCategory,
  type OptimizerSeverity,
  type OptimizerSuggestion,
} from "@/lib/api";

const SEVERITY_VARIANT: Record<
  OptimizerSeverity,
  "destructive" | "warning" | "secondary"
> = {
  critical: "destructive",
  warning: "warning",
  info: "secondary",
};

const SEVERITY_RANK: Record<OptimizerSeverity, number> = {
  critical: 3,
  warning: 2,
  info: 1,
};

export default function OptimizerPage() {
  const [url, setUrl] = React.useState("");
  const [keyword, setKeyword] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<OptimizeResponse | null>(null);

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.analyzeOnPage({ url, target_keyword: keyword });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  }

  const byCategory = React.useMemo(() => {
    const map: Partial<Record<OptimizerCategory, OptimizerSuggestion[]>> = {};
    result?.suggestions.forEach((s) => {
      (map[s.category] ??= []).push(s);
    });
    return map;
  }, [result]);

  const c = result?.checks;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">
          On-Page SEO Optimizer
        </h1>
        <p className="text-muted-foreground">
          Analyze a page against a target keyword: meta tags, headings, keyword
          placement &amp; density, links, images, readability, and AI keyword
          suggestions.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Analyze a page</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAnalyze} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
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
                <Label htmlFor="kw">Target keyword</Label>
                <Input
                  id="kw"
                  placeholder="ai seo tools"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  required
                />
              </div>
            </div>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {busy ? "Analyzing…" : "Analyze"}
            </Button>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </form>
        </CardContent>
      </Card>

      {result && c && (
        <>
          {/* Score + summary */}
          <Card>
            <CardContent className="flex flex-col items-center gap-6 pt-6 sm:flex-row">
              <ScoreGauge score={result.score} />
              <div className="flex-1 space-y-2">
                <p className="text-sm text-muted-foreground break-all">
                  {result.url}
                </p>
                <p className="text-sm">
                  Target keyword:{" "}
                  <span className="font-medium">{result.target_keyword}</span>
                </p>
                <div className="flex gap-4 text-sm">
                  <SummaryStat
                    label="Critical"
                    n={countSeverity(result.suggestions, "critical")}
                  />
                  <SummaryStat
                    label="Warnings"
                    n={countSeverity(result.suggestions, "warning")}
                  />
                  <SummaryStat
                    label="Info"
                    n={countSeverity(result.suggestions, "info")}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Expandable checks */}
          <div className="space-y-3">
            <Section
              title="Meta title"
              suggestions={byCategory.meta_title}
              defaultOpen
            >
              <Row label="Title" value={c.meta_title.text ?? "— missing —"} />
              <Row label="Length" value={`${c.meta_title.length} chars`} />
              <Bool label="Contains keyword" value={c.meta_title.has_keyword} />
              <Bool
                label="Keyword near start"
                value={c.meta_title.keyword_at_start}
              />
            </Section>

            <Section
              title="Meta description"
              suggestions={byCategory.meta_description}
            >
              <Row
                label="Description"
                value={c.meta_description.text ?? "— missing —"}
              />
              <Row label="Length" value={`${c.meta_description.length} chars`} />
              <Bool
                label="Contains keyword"
                value={c.meta_description.has_keyword}
              />
            </Section>

            <Section title="Heading structure" suggestions={byCategory.headings}>
              <div className="mb-3 grid grid-cols-6 gap-2 text-center">
                {(
                  [
                    ["H1", c.headings.h1_count],
                    ["H2", c.headings.h2_count],
                    ["H3", c.headings.h3_count],
                    ["H4", c.headings.h4_count],
                    ["H5", c.headings.h5_count],
                    ["H6", c.headings.h6_count],
                  ] as const
                ).map(([l, n]) => (
                  <div key={l} className="rounded-md border p-2">
                    <div className="text-xs text-muted-foreground">{l}</div>
                    <div className="text-lg font-semibold">{n}</div>
                  </div>
                ))}
              </div>
              <Bool label="Keyword in H1" value={c.headings.h1_has_keyword} />
              <Bool
                label="Keyword in a subheading"
                value={c.headings.subheading_has_keyword}
              />
            </Section>

            <Section
              title={`Keyword placement (${c.keyword_placement.placement_score}%)`}
              suggestions={byCategory.keyword_placement}
            >
              <Bool label="In title" value={c.keyword_placement.in_title} />
              <Bool
                label="In meta description"
                value={c.keyword_placement.in_meta_description}
              />
              <Bool label="In H1" value={c.keyword_placement.in_h1} />
              <Bool
                label="In subheadings"
                value={c.keyword_placement.in_subheadings}
              />
              <Bool
                label="In first paragraph"
                value={c.keyword_placement.in_first_paragraph}
              />
              <Bool label="In URL" value={c.keyword_placement.in_url} />
              <Bool
                label="In image alt text"
                value={c.keyword_placement.in_image_alt}
              />
            </Section>

            <Section
              title="Keyword density"
              suggestions={byCategory.keyword_density}
            >
              <Row
                label="Density"
                value={`${c.keyword_density.density_pct}% (${c.keyword_density.assessment})`}
              />
              <Row
                label="Occurrences"
                value={`${c.keyword_density.occurrences} in ${c.keyword_density.word_count} words`}
              />
            </Section>

            <Section title="Links & anchors" suggestions={byCategory.links}>
              <Row
                label="Internal / External"
                value={`${c.links.internal_count} / ${c.links.external_count}`}
              />
              <Row
                label="Generic anchors"
                value={String(c.links.generic_anchor_count)}
              />
              {c.links.samples.length > 0 && (
                <div className="mt-3 overflow-x-auto rounded-md border">
                  <table className="w-full text-xs">
                    <thead className="bg-muted/50 text-left">
                      <tr>
                        <th className="p-2 font-medium">Anchor text</th>
                        <th className="p-2 font-medium">Links to</th>
                        <th className="p-2 font-medium">Location</th>
                        <th className="p-2 font-medium">Type</th>
                      </tr>
                    </thead>
                    <tbody>
                      {c.links.samples.map((a, i) => (
                        <tr key={i} className="border-t align-top">
                          <td
                            className={`p-2 ${a.generic ? "text-amber-600" : ""}`}
                          >
                            {a.text}
                            {a.generic && (
                              <span className="ml-1 text-[10px] text-amber-600">
                                (generic)
                              </span>
                            )}
                          </td>
                          <td className="max-w-[220px] break-all p-2">
                            <a
                              href={a.href}
                              target="_blank"
                              rel="noreferrer"
                              className="text-primary hover:underline"
                            >
                              {a.href}
                            </a>
                          </td>
                          <td className="p-2 text-muted-foreground">
                            {a.location}
                          </td>
                          <td className="p-2">
                            <Badge variant="outline">{a.kind}</Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Section>

            <Section title="Images" suggestions={byCategory.images}>
              <Row label="Total images" value={String(c.images.total)} />
              <Row label="Missing alt" value={String(c.images.missing_alt)} />
              <Row
                label="Alt contains keyword"
                value={String(c.images.with_keyword_alt)}
              />
            </Section>

            <Section title="Readability" suggestions={byCategory.readability}>
              {c.readability.flesch_reading_ease === null ? (
                <Row
                  label="Readability"
                  value="Data not available (page has too little text to score)"
                />
              ) : (
                <>
                  <Row
                    label="Flesch reading ease"
                    value={`${c.readability.flesch_reading_ease} (${c.readability.assessment})`}
                  />
                  <Row
                    label="Grade level"
                    value={String(c.readability.grade_level)}
                  />
                </>
              )}
            </Section>

            <Section
              title="AI keyword suggestions"
              suggestions={byCategory.ai}
              defaultOpen
            >
              {result.ai_suggestions.notes && (
                <p className="mb-3 text-sm text-muted-foreground">
                  {result.ai_suggestions.notes}
                </p>
              )}
              <KeywordChips
                label="LSI / related"
                items={result.ai_suggestions.lsi_keywords}
              />
              <KeywordChips
                label="Missing keywords"
                items={result.ai_suggestions.missing_keywords}
                variant="warning"
              />
            </Section>
          </div>
        </>
      )}
    </div>
  );
}

function countSeverity(
  suggestions: OptimizerSuggestion[],
  severity: OptimizerSeverity
) {
  return suggestions.filter((s) => s.severity === severity).length;
}

function SummaryStat({ label, n }: { label: string; n: number }) {
  return (
    <div>
      <span className="text-lg font-bold">{n}</span>{" "}
      <span className="text-muted-foreground">{label}</span>
    </div>
  );
}

function ScoreGauge({ score }: { score: number }) {
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - score / 100);
  const color =
    score >= 80 ? "#059669" : score >= 50 ? "#d97706" : "#dc2626";
  return (
    <svg width="140" height="140" viewBox="0 0 140 140" className="shrink-0">
      <circle
        cx="70"
        cy="70"
        r={radius}
        fill="none"
        stroke="hsl(var(--muted))"
        strokeWidth="12"
      />
      <circle
        cx="70"
        cy="70"
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth="12"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform="rotate(-90 70 70)"
      />
      <text
        x="70"
        y="66"
        textAnchor="middle"
        className="fill-foreground text-3xl font-bold"
      >
        {Math.round(score)}
      </text>
      <text
        x="70"
        y="88"
        textAnchor="middle"
        className="fill-muted-foreground text-xs"
      >
        / 100
      </text>
    </svg>
  );
}

function Section({
  title,
  suggestions = [],
  defaultOpen = false,
  children,
}: {
  title: string;
  suggestions?: OptimizerSuggestion[];
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const worst = suggestions.reduce<OptimizerSeverity | null>(
    (acc, s) =>
      acc && SEVERITY_RANK[acc] >= SEVERITY_RANK[s.severity]
        ? acc
        : s.severity,
    null
  );
  return (
    <details
      open={defaultOpen}
      className="group rounded-lg border bg-card [&_summary::-webkit-details-marker]:hidden"
    >
      <summary className="flex cursor-pointer items-center justify-between p-4">
        <span className="font-medium">{title}</span>
        <span className="flex items-center gap-2">
          {worst ? (
            <Badge variant={SEVERITY_VARIANT[worst]}>
              {suggestions.length} issue{suggestions.length > 1 ? "s" : ""}
            </Badge>
          ) : (
            <Badge variant="success">OK</Badge>
          )}
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
        </span>
      </summary>
      <div className="space-y-1 border-t p-4 text-sm">
        {children}
        {suggestions.length > 0 && (
          <div className="mt-3 space-y-2">
            {suggestions.map((s, i) => (
              <div key={i} className="rounded-md bg-muted/50 p-2">
                <div className="flex items-center gap-2">
                  <Badge variant={SEVERITY_VARIANT[s.severity]}>
                    {s.severity}
                  </Badge>
                  <span className="font-medium">{s.message}</span>
                </div>
                <p className="mt-1 text-muted-foreground">{s.recommendation}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-3">
      <span className="w-44 shrink-0 text-muted-foreground">{label}</span>
      <span className="break-words">{value}</span>
    </div>
  );
}

function Bool({ label, value }: { label: string; value: boolean }) {
  return (
    <div className="flex items-center gap-2">
      {value ? (
        <Check className="h-4 w-4 text-emerald-600" />
      ) : (
        <X className="h-4 w-4 text-destructive" />
      )}
      <span>{label}</span>
    </div>
  );
}

function KeywordChips({
  label,
  items,
  variant = "secondary",
}: {
  label: string;
  items: string[];
  variant?: "secondary" | "warning";
}) {
  if (items.length === 0) return null;
  return (
    <div className="mb-3">
      <p className="mb-1 text-xs uppercase text-muted-foreground">{label}</p>
      <div className="flex flex-wrap gap-1">
        {items.map((k, i) => (
          <Badge key={i} variant={variant}>
            {k}
          </Badge>
        ))}
      </div>
    </div>
  );
}

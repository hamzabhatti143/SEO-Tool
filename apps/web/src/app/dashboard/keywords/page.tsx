"use client";

import * as React from "react";
import Papa from "papaparse";
import {
  Download,
  Loader2,
  Minus,
  Search,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { FadeIn } from "@/components/motion";
import { useProject } from "@/components/project-provider";
import {
  api,
  runJob,
  type Keyword,
  type KeywordDifficulty,
  type KeywordIntent,
  type KeywordKind,
} from "@/lib/api";

const KIND_LABEL: Record<KeywordKind, string> = {
  related: "Related",
  long_tail: "Long-tail",
  question: "Question",
};

const DIFFICULTY_VARIANT: Record<
  KeywordDifficulty,
  "success" | "warning" | "destructive"
> = {
  low: "success",
  medium: "warning",
  high: "destructive",
};

const DIFFICULTY_ORDER: Record<KeywordDifficulty, number> = {
  low: 1,
  medium: 2,
  high: 3,
};

const INTENT_LABEL: Record<KeywordIntent, string> = {
  informational: "Informational",
  commercial: "Commercial",
  transactional: "Transactional",
};

type KindFilter = KeywordKind | "all";
type DiffFilter = KeywordDifficulty | "all";
type IntentFilter = KeywordIntent | "all";

export default function KeywordsPage() {
  const { currentProject } = useProject();
  const [seed, setSeed] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [keywords, setKeywords] = React.useState<Keyword[]>([]);

  const [kind, setKind] = React.useState<KindFilter>("all");
  const [difficulty, setDifficulty] = React.useState<DiffFilter>("all");
  const [intent, setIntent] = React.useState<IntentFilter>("all");
  const [search, setSearch] = React.useState("");

  async function handleResearch(e: React.FormEvent) {
    e.preventDefault();
    if (!currentProject) {
      setError("Select or create a project first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const results = await runJob<Keyword[]>(() =>
        api.enqueueKeywordResearch({
          project_id: currentProject.id,
          seed_keyword: seed,
        })
      );
      setKeywords(results);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Keyword research failed");
    } finally {
      setBusy(false);
    }
  }

  const filtered = React.useMemo(
    () =>
      keywords.filter(
        (k) =>
          (kind === "all" || k.kind === kind) &&
          (difficulty === "all" || k.difficulty === difficulty) &&
          (intent === "all" || k.search_intent === intent) &&
          (search === "" ||
            k.term.toLowerCase().includes(search.toLowerCase()))
      ),
    [keywords, kind, difficulty, intent, search]
  );

  // The table sorts internally; it reports the current sorted (filtered) rows
  // here so the CSV export matches exactly what's on screen.
  const sortedRows = React.useRef<Keyword[]>([]);
  const handleSortedRows = React.useCallback((rows: Keyword[]) => {
    sortedRows.current = rows;
  }, []);

  function exportCsv() {
    const rows = sortedRows.current.length ? sortedRows.current : filtered;
    const data = rows.map((k) => ({
      Keyword: k.term,
      Cluster: k.cluster_label ?? "",
      Type: KIND_LABEL[k.kind],
      "Search Volume (est.)": k.search_volume ?? "",
      Difficulty: k.difficulty ? capitalize(k.difficulty) : "",
      "Search Intent": k.search_intent ? INTENT_LABEL[k.search_intent] : "",
      "Trend Score": k.trend_score ?? "",
      "Trend Direction": k.trend_direction ?? "",
    }));
    const csv = Papa.unparse(data);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const slug = slugify(currentProject?.name ?? "project");
    const date = new Date().toISOString().slice(0, 10);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${slug}-keywords-${date}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  const columns: Column<Keyword>[] = [
    {
      key: "term",
      header: "Keyword",
      cell: (k) => <span className="font-medium">{k.term}</span>,
      sortValue: (k) => k.term.toLowerCase(),
    },
    {
      key: "cluster",
      header: "Cluster",
      cell: (k) => (
        <span className="text-muted-foreground">
          {k.cluster_label ?? "—"}
        </span>
      ),
      sortValue: (k) => k.cluster_label ?? "",
    },
    {
      key: "kind",
      header: "Type",
      cell: (k) => <Badge variant="outline">{KIND_LABEL[k.kind]}</Badge>,
      sortValue: (k) => k.kind,
    },
    {
      key: "difficulty",
      header: "Difficulty",
      cell: (k) =>
        k.difficulty ? (
          <Badge variant={DIFFICULTY_VARIANT[k.difficulty]}>
            {capitalize(k.difficulty)}
          </Badge>
        ) : (
          "—"
        ),
      sortValue: (k) => (k.difficulty ? DIFFICULTY_ORDER[k.difficulty] : 0),
    },
    {
      key: "intent",
      header: "Intent",
      cell: (k) => (
        <span className="text-muted-foreground">
          {k.search_intent ? INTENT_LABEL[k.search_intent] : "—"}
        </span>
      ),
      sortValue: (k) => k.search_intent ?? "",
    },
    {
      key: "trend",
      header: "Trend",
      cell: (k) => <TrendCell keyword={k} />,
      sortValue: (k) => k.trend_score ?? -1,
      align: "right",
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Keyword Research"
        description="Related terms, long-tail variations, and People-Also-Ask questions, grouped into clusters with a Google Trends signal. Difficulty and intent are AI estimates."
      />

      <FadeIn delay={0.05}>
        <Card className="shadow-soft">
          <CardHeader>
            <CardTitle>Generate keywords</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleResearch} className="flex items-end gap-3">
              <div className="flex-1 space-y-2">
                <Label htmlFor="seed">Seed keyword</Label>
                <Input
                  id="seed"
                  placeholder="e.g. ai seo tools"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                  required
                />
              </div>
              <Button type="submit" disabled={busy}>
                {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {busy ? "Researching…" : "Research"}
              </Button>
            </form>
            {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
          </CardContent>
        </Card>
      </FadeIn>

      {keywords.length === 0 ? (
        <EmptyState
          icon={Search}
          title="No keywords yet"
          description="Enter a seed keyword above and run research to generate a clustered keyword list."
        />
      ) : (
        <FadeIn delay={0.1} className="space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap items-end gap-3">
            <FilterSelect
              label="Type"
              value={kind}
              onChange={(v) => setKind(v as KindFilter)}
              options={[
                ["all", "All types"],
                ["related", "Related"],
                ["long_tail", "Long-tail"],
                ["question", "Question"],
              ]}
            />
            <FilterSelect
              label="Difficulty"
              value={difficulty}
              onChange={(v) => setDifficulty(v as DiffFilter)}
              options={[
                ["all", "All"],
                ["low", "Low"],
                ["medium", "Medium"],
                ["high", "High"],
              ]}
            />
            <FilterSelect
              label="Intent"
              value={intent}
              onChange={(v) => setIntent(v as IntentFilter)}
              options={[
                ["all", "All"],
                ["informational", "Informational"],
                ["commercial", "Commercial"],
                ["transactional", "Transactional"],
              ]}
            />
            <div className="flex-1 space-y-1">
              <Label htmlFor="kw-search" className="text-xs">
                Search
              </Label>
              <Input
                id="kw-search"
                placeholder="Filter terms…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-9"
              />
            </div>
            <span className="pb-2 text-sm text-muted-foreground">
              {filtered.length}/{keywords.length}
            </span>
            <Button
              variant="outline"
              onClick={exportCsv}
              disabled={filtered.length === 0}
              className="ml-auto"
            >
              <Download className="mr-2 h-4 w-4" />
              Export CSV
            </Button>
          </div>

          <DataTable
            columns={columns}
            rows={filtered}
            getRowKey={(k) => k.id}
            pageSize={15}
            initialSort={{ key: "difficulty", dir: "asc" }}
            onSortedRowsChange={handleSortedRows}
            emptyState={
              <EmptyState
                title="No matches"
                description="No keywords match the current filters."
              />
            }
          />
        </FadeIn>
      )}
    </div>
  );
}

function TrendCell({ keyword }: { keyword: Keyword }) {
  if (keyword.trend_score === null) {
    return <span className="text-muted-foreground">—</span>;
  }
  const Icon =
    keyword.trend_direction === "rising"
      ? TrendingUp
      : keyword.trend_direction === "falling"
        ? TrendingDown
        : Minus;
  const color =
    keyword.trend_direction === "rising"
      ? "text-emerald-600"
      : keyword.trend_direction === "falling"
        ? "text-destructive"
        : "text-muted-foreground";
  return (
    <span className={`inline-flex items-center justify-end gap-1 ${color}`}>
      <Icon className="h-4 w-4" />
      {keyword.trend_score}
    </span>
  );
}

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function slugify(s: string) {
  return (
    s
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "project"
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <div className="space-y-1">
      <Label className="text-xs">{label}</Label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 rounded-md border border-input bg-background px-2 text-sm"
      >
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </div>
  );
}

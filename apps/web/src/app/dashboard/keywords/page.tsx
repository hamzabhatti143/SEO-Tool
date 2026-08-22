"use client";

import * as React from "react";
import {
  ChevronDown,
  Loader2,
  Minus,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

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

const INTENT_LABEL: Record<KeywordIntent, string> = {
  informational: "Informational",
  commercial: "Commercial",
  transactional: "Transactional",
};

const QUESTIONS_LABEL = "People Also Ask";

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

  // Group filtered keywords by cluster label; largest cluster first, with
  // "People Also Ask" pinned last.
  const groups = React.useMemo(() => {
    const map = new Map<string, Keyword[]>();
    for (const k of filtered) {
      const label = k.cluster_label ?? "Uncategorized";
      const bucket = map.get(label);
      if (bucket) bucket.push(k);
      else map.set(label, [k]);
    }
    return [...map.entries()].sort((a, b) => {
      if (a[0] === QUESTIONS_LABEL) return 1;
      if (b[0] === QUESTIONS_LABEL) return -1;
      return b[1].length - a[1].length;
    });
  }, [filtered]);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Keyword Research</h1>
        <p className="text-muted-foreground">
          Generate related terms, long-tail variations, and People-Also-Ask
          questions, auto-grouped into topic clusters with a Google Trends
          signal. Difficulty and intent are <strong>AI estimates</strong>, not
          Google Ads / keyword-tool data; the Trend column is real Google
          Trends interest.
        </p>
      </header>

      <Card>
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

      {keywords.length > 0 && (
        <>
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
          </div>

          {/* Cluster groups */}
          <div className="space-y-3">
            {groups.map(([label, items], i) => (
              <ClusterGroup
                key={label}
                label={label}
                items={items}
                defaultOpen={i < 3}
              />
            ))}
            {groups.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No keywords match the current filters.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function ClusterGroup({
  label,
  items,
  defaultOpen,
}: {
  label: string;
  items: Keyword[];
  defaultOpen: boolean;
}) {
  const isQuestions = label === QUESTIONS_LABEL;
  return (
    <details
      open={defaultOpen}
      className="group rounded-lg border bg-card [&_summary::-webkit-details-marker]:hidden"
    >
      <summary className="flex cursor-pointer items-center justify-between p-4">
        <span className="flex items-center gap-2 font-medium">
          {label}
          <Badge variant={isQuestions ? "default" : "secondary"}>
            {items.length}
          </Badge>
        </span>
        <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
      </summary>
      <div className="overflow-x-auto border-t">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left">
            <tr>
              <th className="p-3 font-medium">Keyword</th>
              <th className="p-3 font-medium">Type</th>
              <th className="p-3 font-medium">
                Difficulty{" "}
                <span className="font-normal text-muted-foreground">
                  (AI est.)
                </span>
              </th>
              <th className="p-3 font-medium">
                Intent{" "}
                <span className="font-normal text-muted-foreground">
                  (AI est.)
                </span>
              </th>
              <th className="p-3 font-medium">Trend</th>
            </tr>
          </thead>
          <tbody>
            {items.map((k) => (
              <tr key={k.id} className="border-t">
                <td className="p-3">{k.term}</td>
                <td className="p-3">
                  <Badge variant="outline">{KIND_LABEL[k.kind]}</Badge>
                </td>
                <td className="p-3">
                  {k.difficulty ? (
                    <Badge variant={DIFFICULTY_VARIANT[k.difficulty]}>
                      {capitalize(k.difficulty)}
                    </Badge>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="p-3 text-muted-foreground">
                  {k.search_intent ? INTENT_LABEL[k.search_intent] : "—"}
                </td>
                <td className="p-3">
                  <TrendCell keyword={k} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
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
    <span className={`flex items-center gap-1 ${color}`}>
      <Icon className="h-4 w-4" />
      {keyword.trend_score}
    </span>
  );
}

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
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

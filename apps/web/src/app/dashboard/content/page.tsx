"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
import { api, type ContentType, type DensityReport } from "@/lib/api";

const CONTENT_TYPES: [ContentType, string][] = [
  ["blog", "Blog post"],
  ["product_description", "Product description"],
  ["landing_page", "Landing page"],
];

const TONES = ["professional", "casual", "authoritative", "friendly"];

const PHASES: [string, string][] = [
  ["outline", "Outline"],
  ["drafting", "Drafting"],
  ["seo", "SEO pass"],
];

type SeoData = {
  meta_title: string;
  meta_description: string;
  density: DensityReport;
};

export default function ContentPage() {
  return (
    <React.Suspense fallback={null}>
      <ContentStudio />
    </React.Suspense>
  );
}

const CONTENT_TYPE_VALUES: ContentType[] = [
  "blog",
  "product_description",
  "landing_page",
];

function ContentStudio() {
  const { currentProject } = useProject();
  const params = useSearchParams();

  // Prefill from query params (e.g. deep-links from Content Gap Analysis).
  const initialType = params.get("content_type") as ContentType | null;
  const [topic, setTopic] = React.useState(params.get("topic") ?? "");
  const [targetKeyword, setTargetKeyword] = React.useState(
    params.get("target_keyword") ?? ""
  );
  const [contentType, setContentType] = React.useState<ContentType>(
    initialType && CONTENT_TYPE_VALUES.includes(initialType)
      ? initialType
      : "blog"
  );
  const [tone, setTone] = React.useState("professional");
  const [wordCount, setWordCount] = React.useState(900);

  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [phase, setPhase] = React.useState<string | null>(null);
  const [outline, setOutline] = React.useState<string[]>([]);
  const [body, setBody] = React.useState("");
  const [seo, setSeo] = React.useState<SeoData | null>(null);
  const [done, setDone] = React.useState(false);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (!currentProject) {
      setError("Select or create a project first.");
      return;
    }
    setBusy(true);
    setError(null);
    setPhase(null);
    setOutline([]);
    setBody("");
    setSeo(null);
    setDone(false);

    await api.generateContentStream(
      {
        project_id: currentProject.id,
        topic,
        target_keyword: targetKeyword,
        content_type: contentType,
        tone,
        word_count: wordCount,
      },
      {
        onPhase: (p) => setPhase(p),
        onOutline: (s) => setOutline(s),
        onToken: (t) => setBody((prev) => prev + t),
        onSeo: (data) => setSeo(data),
        onDone: () => {
          setDone(true);
          setBusy(false);
          setPhase(null);
        },
        onError: (detail) => {
          setError(detail);
          setBusy(false);
          setPhase(null);
        },
      }
    );
  }

  const phaseIndex = phase ? PHASES.findIndex(([p]) => p === phase) : -1;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">AI Content Studio</h1>
        <p className="text-muted-foreground">
          Generate SEO content through a LangChain pipeline: outline → section
          drafting → SEO optimization. Output streams live.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Generate content</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleGenerate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="topic">Topic</Label>
              <Input
                id="topic"
                placeholder="e.g. How AI is changing SEO in 2026"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-2">
                <Label htmlFor="kw">Target keyword</Label>
                <Input
                  id="kw"
                  placeholder="ai seo"
                  value={targetKeyword}
                  onChange={(e) => setTargetKeyword(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="type">Content type</Label>
                <select
                  id="type"
                  value={contentType}
                  onChange={(e) =>
                    setContentType(e.target.value as ContentType)
                  }
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  {CONTENT_TYPES.map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="tone">Tone</Label>
                <select
                  id="tone"
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  {TONES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="words">Word count</Label>
                <Input
                  id="words"
                  type="number"
                  min={300}
                  max={3000}
                  step={50}
                  value={wordCount}
                  onChange={(e) =>
                    setWordCount(
                      Math.min(
                        3000,
                        Math.max(300, Number(e.target.value) || 300)
                      )
                    )
                  }
                />
              </div>
            </div>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {busy ? "Generating…" : "Generate"}
            </Button>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </form>
        </CardContent>
      </Card>

      {/* Pipeline progress */}
      {(busy || done) && (
        <div className="flex gap-6">
          {PHASES.map(([p, label], i) => {
            const active = phase === p;
            const complete = done || (phaseIndex >= 0 && i < phaseIndex);
            return (
              <div key={p} className="flex items-center gap-2 text-sm">
                {complete ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                ) : active ? (
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                ) : (
                  <Circle className="h-4 w-4 text-muted-foreground" />
                )}
                <span className={active ? "font-medium" : "text-muted-foreground"}>
                  {label}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Outline */}
      {outline.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Outline</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="list-decimal space-y-1 pl-5 text-sm">
              {outline.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      {/* SEO summary */}
      {seo && (
        <Card>
          <CardHeader>
            <CardTitle>SEO optimization</CardTitle>
            <CardDescription>{seo.meta_title}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <span className="text-muted-foreground">Meta description: </span>
              {seo.meta_description}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-muted-foreground">Keyword density:</span>
              <Badge
                variant={
                  seo.density.assessment === "optimal"
                    ? "success"
                    : seo.density.assessment === "high"
                      ? "destructive"
                      : "warning"
                }
              >
                {seo.density.density_pct}% · {seo.density.assessment}
              </Badge>
              <span className="text-muted-foreground">
                ({seo.density.occurrences}× in {seo.density.word_count} words)
              </span>
            </div>
            <p className="text-muted-foreground">
              {seo.density.recommendation}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Live body */}
      {body && (
        <Card>
          <CardHeader>
            <CardTitle>Draft</CardTitle>
          </CardHeader>
          <CardContent>
            <article className="prose prose-sm max-w-none dark:prose-invert prose-headings:font-semibold prose-headings:tracking-tight">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
              {busy && <span className="animate-pulse">▍</span>}
            </article>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

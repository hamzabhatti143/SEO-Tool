"use client";

import * as React from "react";
import {
  AlertTriangle,
  Bot,
  Braces,
  CheckCircle2,
  ChevronDown,
  FileText,
  Gauge,
  Loader2,
  XCircle,
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
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { FadeIn } from "@/components/motion";
import { useProject } from "@/components/project-provider";
import { TechnicalIssues } from "@/components/technical-issues";
import {
  api,
  runJob,
  type Audit,
  type AuditIssue,
  type IssueSeverity,
  type RobotsAudit,
  type SchemaAudit,
  type TechnicalSeoResponse,
} from "@/lib/api";

const SEVERITY_VARIANT: Record<
  IssueSeverity,
  "destructive" | "warning" | "secondary"
> = {
  critical: "destructive",
  warning: "warning",
  info: "secondary",
};

const SEVERITY_LABEL: Record<IssueSeverity, string> = {
  critical: "Critical",
  warning: "Warning",
  info: "Info",
};

export default function AuditPage() {
  const { currentProject } = useProject();
  const [url, setUrl] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [audit, setAudit] = React.useState<Audit | null>(null);
  const [tech, setTech] = React.useState<TechnicalSeoResponse | null>(null);

  async function handleRun(e: React.FormEvent) {
    e.preventDefault();
    if (!currentProject) {
      setError("Select or create a project first.");
      return;
    }
    setBusy(true);
    setError(null);
    setAudit(null);
    setTech(null);
    try {
      const { audit_id } = await runJob<{ audit_id: string; score: number }>(
        () => api.enqueueAudit({ project_id: currentProject.id, url })
      );
      setAudit(await api.getAudit(audit_id));
      // Structured data / robots.txt / llms.txt run as part of the same scan.
      try {
        setTech(await api.getTechnicalSeo(currentProject.id));
      } catch {
        /* technical-SEO extras are best-effort */
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Audit failed");
    } finally {
      setBusy(false);
    }
  }

  const results = audit?.results;

  const counts = React.useMemo(() => {
    const base = { critical: 0, warning: 0, info: 0 };
    results?.issues.forEach((i) => (base[i.severity] += 1));
    return base;
  }, [results]);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader
        title="Website Audit"
        description="Crawl a page and check title & meta tags, H1–H6 structure, image alt text, broken internal links, and page-load basics."
      />

      <FadeIn delay={0.05}>
        <Card className="shadow-soft">
          <CardHeader>
            <CardTitle>Run an audit</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleRun} className="flex items-end gap-3">
              <div className="flex-1 space-y-2">
                <Label htmlFor="url">Page URL</Label>
                <Input
                  id="url"
                  placeholder="https://example.com/page"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  required
                />
              </div>
              <Button type="submit" disabled={busy}>
                {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {busy ? "Auditing…" : "Run audit"}
              </Button>
            </form>
            {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
          </CardContent>
        </Card>
      </FadeIn>

      {!audit && !busy && !error && (
        <EmptyState
          icon={Gauge}
          title="No audit yet"
          description="Enter a page URL above and run an audit to see SEO score, issues, and technical-SEO checks."
        />
      )}

      {results && audit && (
        <>
          {/* Score + headline stats */}
          <div className="grid gap-4 sm:grid-cols-4">
            <ScoreCard value={audit.score ?? 0} />
            <StatCard
              label="Load time"
              value={`${results.page_speed.response_time_ms.toFixed(0)} ms`}
            />
            <StatCard
              label="Broken links"
              value={String(results.links.broken.length)}
              tone={results.links.broken.length > 0 ? "bad" : "good"}
            />
            <StatCard
              label="Images w/o alt"
              value={`${results.images.missing_alt}/${results.images.total}`}
              tone={results.images.missing_alt > 0 ? "warn" : "good"}
            />
          </div>

          {/* Issue category summary */}
          <div className="grid gap-4 sm:grid-cols-3">
            <CategoryCard
              label="Critical"
              count={counts.critical}
              variant="destructive"
            />
            <CategoryCard
              label="Warning"
              count={counts.warning}
              variant="warning"
            />
            <CategoryCard label="Info" count={counts.info} variant="secondary" />
          </div>

          {/* Meta */}
          <Card>
            <CardHeader>
              <CardTitle>Title &amp; meta</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Row
                label="Title"
                value={
                  results.meta.title
                    ? `${results.meta.title}  (${results.meta.title_length} chars)`
                    : "— missing —"
                }
              />
              <Row
                label="Meta description"
                value={
                  results.meta.meta_description
                    ? `${results.meta.meta_description}  (${results.meta.meta_description_length} chars)`
                    : "— missing —"
                }
              />
              <Row
                label="Viewport / Canonical / OG"
                value={`${yn(results.meta.has_viewport)} / ${yn(
                  results.meta.has_canonical
                )} / ${yn(results.meta.has_open_graph)}`}
              />
              <Row label="Robots" value={results.meta.robots ?? "—"} />
            </CardContent>
          </Card>

          {/* Headings + links */}
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Heading structure</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-6 gap-2 text-center">
                  {(
                    [
                      ["H1", results.headings.h1_count],
                      ["H2", results.headings.h2_count],
                      ["H3", results.headings.h3_count],
                      ["H4", results.headings.h4_count],
                      ["H5", results.headings.h5_count],
                      ["H6", results.headings.h6_count],
                    ] as const
                  ).map(([label, n]) => (
                    <div key={label} className="rounded-md border p-2">
                      <div className="text-xs text-muted-foreground">
                        {label}
                      </div>
                      <div className="text-lg font-semibold">{n}</div>
                    </div>
                  ))}
                </div>
                {results.headings.h1_texts.length > 0 && (
                  <p className="mt-3 text-xs text-muted-foreground">
                    H1: {results.headings.h1_texts.join(" · ")}
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Links</CardTitle>
                <CardDescription>
                  {results.links.internal_count} internal ·{" "}
                  {results.links.external_count} external ·{" "}
                  {results.links.checked} checked
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {results.links.broken.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No broken internal links found.
                  </p>
                ) : (
                  results.links.broken.map((l, i) => (
                    <div key={i} className="rounded-md border p-2 text-sm">
                      <span className="break-all">{l.url}</span>
                      <Badge variant="destructive" className="ml-2">
                        {l.reason}
                      </Badge>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </div>

          {/* Issues */}
          <Card>
            <CardHeader>
              <CardTitle>Issues ({results.issues.length})</CardTitle>
              <CardDescription>
                Findings categorized by severity with recommendations.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {results.issues.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No issues detected. Nice work!
                </p>
              )}
              {results.issues.map((issue, i) => (
                <IssueRow key={i} issue={issue} />
              ))}
            </CardContent>
          </Card>
        </>
      )}

      {tech && (
        <>
          <StructuredDataCard schemas={tech.schema_audits} />
          <RobotsCard robots={tech.robots} />
          <LlmsCard llms={tech.llms} />
        </>
      )}

      {currentProject && (
        <TechnicalIssues key={currentProject.id} projectId={currentProject.id} />
      )}
    </div>
  );
}

// --- Technical SEO sections ------------------------------------------------

function StructuredDataCard({ schemas }: { schemas: SchemaAudit[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Braces className="h-5 w-5 text-primary" /> Structured Data
        </CardTitle>
        <CardDescription>
          JSON-LD, Microdata &amp; RDFa schema.org markup and validation.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {schemas.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            None found — add schema markup (e.g. Organization, Article, Product)
            so search engines can show rich results.
          </div>
        ) : (
          schemas.map((s) => <SchemaRow key={s.id} schema={s} />)
        )}
      </CardContent>
    </Card>
  );
}

function SchemaRow({ schema }: { schema: SchemaAudit }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="rounded-md border">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 p-3 text-left"
      >
        {schema.is_valid ? (
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
        ) : (
          <XCircle className="h-4 w-4 shrink-0 text-destructive" />
        )}
        <span className="font-medium">{schema.schema_type}</span>
        <Badge variant="outline" className="uppercase">
          {schema.fmt}
        </Badge>
        <Badge variant={schema.is_valid ? "success" : "warning"}>
          {schema.is_valid ? "Valid" : "Has Issues"}
        </Badge>
        <ChevronDown
          className={`ml-auto h-4 w-4 text-muted-foreground transition-transform ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>
      <div className="px-3 pb-3">
        {schema.missing_properties.length > 0 && (
          <p className="text-sm text-destructive">
            Missing required: {schema.missing_properties.join(", ")}
          </p>
        )}
        {open && schema.raw_schema && (
          <pre className="mt-2 max-h-64 overflow-auto rounded bg-muted p-3 text-xs">
            {JSON.stringify(schema.raw_schema, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

function RobotsCard({ robots }: { robots: RobotsAudit | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-primary" /> Robots.txt
          {robots && (
            <Badge variant={robots.exists ? "success" : "warning"}>
              {robots.exists ? "Found" : "Not found"}
            </Badge>
          )}
        </CardTitle>
        <CardDescription>
          Crawl directives and Sitemap declarations for search engines.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {(robots?.issues_found?.length ?? 0) > 0 && (
          <div className="space-y-2">
            {robots!.issues_found.map((issue, i) => (
              <div
                key={i}
                className="flex items-start gap-2 rounded-md border p-2 text-sm"
              >
                <Badge
                  variant={
                    issue.severity === "critical"
                      ? "destructive"
                      : issue.severity === "warning"
                        ? "warning"
                        : "secondary"
                  }
                >
                  {issue.severity}
                </Badge>
                <span>{issue.message}</span>
              </div>
            ))}
          </div>
        )}
        {robots?.parsed_rules?.sitemaps &&
          robots.parsed_rules.sitemaps.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Sitemaps: {robots.parsed_rules.sitemaps.join(", ")}
            </p>
          )}
        {robots?.exists && robots.raw_content ? (
          <pre className="max-h-72 overflow-auto rounded bg-muted p-3 text-xs">
            {robots.raw_content}
          </pre>
        ) : (
          !robots?.exists && (
            <p className="text-sm text-muted-foreground">
              No robots.txt was found at the site root.
            </p>
          )
        )}
      </CardContent>
    </Card>
  );
}

function LlmsCard({ llms }: { llms: TechnicalSeoResponse["llms"] }) {
  const found = llms?.exists;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-primary" /> llms.txt
          <Badge variant={found ? "success" : "secondary"}>
            {found ? "Found" : "Not found"}
          </Badge>
        </CardTitle>
        <CardDescription>
          An emerging standard telling AI crawlers what to read on your site.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {found ? (
          <>
            <div className="flex items-center gap-2 text-sm">
              Spec format:
              <Badge variant={llms!.follows_spec_format ? "success" : "warning"}>
                {llms!.follows_spec_format ? "Compliant" : "Non-standard"}
              </Badge>
            </div>
            {llms!.raw_content && (
              <pre className="max-h-72 overflow-auto rounded bg-muted p-3 text-xs">
                {llms!.raw_content}
              </pre>
            )}
          </>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              <strong>llms.txt not implemented.</strong> This isn&apos;t an error
              — adoption is still emerging. A well-formed <code>llms.txt</code>{" "}
              helps AI assistants understand and cite your key pages.
            </p>
            <Button variant="outline" size="sm" asChild>
              <a href="/dashboard/content">Generate llms.txt</a>
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function yn(v: boolean) {
  return v ? "Yes" : "No";
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-3">
      <span className="w-52 shrink-0 text-muted-foreground">{label}</span>
      <span className="break-words">{value}</span>
    </div>
  );
}

function StatCard({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "good" | "warn" | "bad";
}) {
  const color =
    tone === "good"
      ? "text-emerald-600"
      : tone === "warn"
        ? "text-amber-600"
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

function ScoreCard({ value }: { value: number }) {
  const color =
    value >= 80
      ? "text-emerald-600"
      : value >= 50
        ? "text-amber-600"
        : "text-destructive";
  return (
    <Card>
      <CardContent className="pt-6">
        <p className="text-xs uppercase text-muted-foreground">SEO Score</p>
        <p className={`text-2xl font-bold ${color}`}>{value}/100</p>
      </CardContent>
    </Card>
  );
}

function CategoryCard({
  label,
  count,
  variant,
}: {
  label: string;
  count: number;
  variant: "destructive" | "warning" | "secondary";
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between pt-6">
        <Badge variant={variant}>{label}</Badge>
        <span className="text-2xl font-bold">{count}</span>
      </CardContent>
    </Card>
  );
}

function IssueRow({ issue }: { issue: AuditIssue }) {
  return (
    <div className="rounded-md border p-3">
      <div className="flex items-center gap-2">
        <Badge variant={SEVERITY_VARIANT[issue.severity]}>
          {SEVERITY_LABEL[issue.severity]}
        </Badge>
        <span className="text-sm font-medium">{issue.message}</span>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        {issue.recommendation}
      </p>
    </div>
  );
}

"use client";

import * as React from "react";
import { Loader2, Undo2 } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

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
import {
  api,
  type ChangeLog,
  type CoreWebVitals,
  type Platform,
} from "@/lib/api";

const PLATFORM_META: Record<
  Platform,
  { label: string; variant: "default" | "secondary" }
> = {
  wordpress: { label: "WordPress", variant: "default" },
  shopify: { label: "Shopify", variant: "default" },
  custom: { label: "Not connected", variant: "secondary" },
};

export default function FixHistoryPage() {
  const { currentProject } = useProject();
  const [changes, setChanges] = React.useState<ChangeLog[]>([]);
  const [scans, setScans] = React.useState<CoreWebVitals[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [revertingId, setRevertingId] = React.useState<string | null>(null);

  const load = React.useCallback(async (projectId: string) => {
    setLoading(true);
    setError(null);
    try {
      const [c, s] = await Promise.all([
        api.listCwvChanges(projectId),
        api.listCoreWebVitals(projectId),
      ]);
      setChanges(c);
      setScans(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load fix history");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (currentProject) load(currentProject.id);
    else {
      setChanges([]);
      setScans([]);
    }
  }, [currentProject, load]);

  async function handleRevert(changeId: string) {
    if (!currentProject) return;
    setRevertingId(changeId);
    setError(null);
    try {
      await api.revertCwvFix(currentProject.id, changeId);
      await load(currentProject.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Revert failed");
    } finally {
      setRevertingId(null);
    }
  }

  if (!currentProject) {
    return (
      <div className="mx-auto max-w-4xl">
        <p className="text-muted-foreground">
          Select or create a project first.
        </p>
      </div>
    );
  }

  const platform = PLATFORM_META[currentProject.platform];

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Fix History</h1>
          <p className="text-muted-foreground">
            Automated Core Web Vitals fixes applied to {currentProject.name}.
          </p>
        </div>
        <Badge variant={platform.variant}>{platform.label}</Badge>
      </header>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <ScoreTrend scans={scans} />

      <Card>
        <CardHeader>
          <CardTitle>Change log ({changes.length})</CardTitle>
          <CardDescription>
            Every applied fix, its CWV score impact, and revert control.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </div>
          )}
          {!loading && changes.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No fixes yet. Run a Core Web Vitals scan and use “Fix All Issues”.
            </p>
          )}
          {changes.map((change) => (
            <ChangeRow
              key={change.id}
              change={change}
              reverting={revertingId === change.id}
              onRevert={() => handleRevert(change.id)}
            />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function ScoreTrend({ scans }: { scans: CoreWebVitals[] }) {
  // Recharts measures the DOM, so only render after mount to avoid SSR/hydration
  // width warnings.
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const data = React.useMemo(
    () =>
      [...scans]
        .filter((s) => s.performance_score != null)
        .sort(
          (a, b) =>
            new Date(a.scanned_at).getTime() - new Date(b.scanned_at).getTime()
        )
        .map((s) => ({
          date: new Date(s.scanned_at).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          }),
          score: s.performance_score as number,
        })),
    [scans]
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Performance score trend</CardTitle>
        <CardDescription>
          Lighthouse performance score across historical scans.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {data.length < 2 ? (
          <p className="text-sm text-muted-foreground">
            Need at least two scans to chart a trend.
          </p>
        ) : (
          <div className="h-64 w-full">
            {mounted && (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={data}
                  margin={{ top: 8, right: 16, bottom: 0, left: -16 }}
                >
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 12 }}
                    className="text-muted-foreground"
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fontSize: 12 }}
                    className="text-muted-foreground"
                  />
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 8,
                      border: "1px solid hsl(var(--border))",
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="score"
                    name="Performance"
                    stroke="hsl(var(--primary))"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ChangeRow({
  change,
  reverting,
  onRevert,
}: {
  change: ChangeLog;
  reverting: boolean;
  onRevert: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border p-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">
            {change.issue_type.replace(/_/g, " ")}
          </span>
          <Badge variant={change.status === "applied" ? "success" : "secondary"}>
            {change.status}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          {new Date(change.applied_at).toLocaleString()}
          {change.external_change_id && (
            <>
              {" · "}
              <code>{change.external_change_id}</code>
            </>
          )}
        </p>
      </div>

      <ScoreDelta
        before={change.cwv_score_before}
        after={change.cwv_score_after}
      />

      {change.status === "applied" && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRevert}
          disabled={reverting}
        >
          {reverting ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Undo2 className="mr-2 h-4 w-4" />
          )}
          Revert
        </Button>
      )}
    </div>
  );
}

function ScoreDelta({
  before,
  after,
}: {
  before: number | null;
  after: number | null;
}) {
  const improved = before != null && after != null && after > before;
  const worse = before != null && after != null && after < before;
  const color = improved
    ? "text-emerald-600"
    : worse
      ? "text-destructive"
      : "text-muted-foreground";
  return (
    <div className="flex items-baseline gap-1.5 text-sm">
      <span className="text-muted-foreground">{before ?? "—"}</span>
      <span className="text-muted-foreground">→</span>
      <span className={`font-semibold ${color}`}>{after ?? "—"}</span>
      <span className="text-xs text-muted-foreground">CWV</span>
    </div>
  );
}

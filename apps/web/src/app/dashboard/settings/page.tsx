"use client";

import * as React from "react";
import { Loader2, Play, Save } from "lucide-react";

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
import { Textarea } from "@/components/ui/textarea";
import { useProject } from "@/components/project-provider";
import { api, type AutomationSettings } from "@/lib/api";

function Toggle({
  label,
  description,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4 py-2">
      <span>
        <span className="text-sm font-medium">{label}</span>
        {description && (
          <span className="block text-xs text-muted-foreground">
            {description}
          </span>
        )}
      </span>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-4 w-4 shrink-0 accent-primary"
      />
    </label>
  );
}

export default function SettingsPage() {
  const { currentProject } = useProject();
  const [s, setS] = React.useState<AutomationSettings | null>(null);
  const [competitorText, setCompetitorText] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [running, setRunning] = React.useState<"daily" | "weekly" | null>(null);
  const [msg, setMsg] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!currentProject) return;
    setLoading(true);
    setError(null);
    api
      .getAutomationSettings(currentProject.id)
      .then((data) => {
        setS(data);
        setCompetitorText((data.competitor_urls ?? []).join("\n"));
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load settings")
      )
      .finally(() => setLoading(false));
  }, [currentProject]);

  function patch(update: Partial<AutomationSettings>) {
    setS((prev) => (prev ? { ...prev, ...update } : prev));
  }

  async function save() {
    if (!currentProject || !s) return;
    setSaving(true);
    setMsg(null);
    setError(null);
    try {
      const competitor_urls = competitorText
        .split("\n")
        .map((u) => u.trim())
        .filter(Boolean);
      const updated = await api.updateAutomationSettings(currentProject.id, {
        weekly_audit: s.weekly_audit,
        broken_link_monitoring: s.broken_link_monitoring,
        competitor_monitoring: s.competitor_monitoring,
        email_notifications: s.email_notifications,
        notify_broken_links: s.notify_broken_links,
        weekly_summary: s.weekly_summary,
        audit_url: s.audit_url || null,
        monitor_url: s.monitor_url || null,
        competitor_urls,
        notification_email: s.notification_email || null,
      });
      setS(updated);
      setMsg("Settings saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function runNow(kind: "daily" | "weekly") {
    if (!currentProject) return;
    setRunning(kind);
    setMsg(null);
    setError(null);
    try {
      await api.runAutomation(currentProject.id, kind);
      setMsg(`Ran ${kind} automations.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed");
    } finally {
      setRunning(null);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Automation Settings</h1>
        <p className="text-muted-foreground">
          Choose which automations run for{" "}
          {currentProject?.name ?? "your project"} and how you&apos;re notified.
        </p>
      </header>

      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}

      {s && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Scheduled automations</CardTitle>
              <CardDescription>
                Run automatically in the background.
              </CardDescription>
            </CardHeader>
            <CardContent className="divide-y">
              <Toggle
                label="Weekly audit re-run"
                description="Re-audit the page below every week."
                checked={s.weekly_audit}
                onChange={(v) => patch({ weekly_audit: v })}
              />
              {s.weekly_audit && (
                <div className="space-y-2 py-2">
                  <Label htmlFor="audit_url">Audit URL (defaults to homepage)</Label>
                  <Input
                    id="audit_url"
                    placeholder={`https://${currentProject?.domain ?? ""}`}
                    value={s.audit_url ?? ""}
                    onChange={(e) => patch({ audit_url: e.target.value })}
                  />
                </div>
              )}
              <Toggle
                label="Broken link monitoring (daily)"
                description="Check a page daily and alert on new broken links."
                checked={s.broken_link_monitoring}
                onChange={(v) => patch({ broken_link_monitoring: v })}
              />
              {s.broken_link_monitoring && (
                <div className="space-y-2 py-2">
                  <Label htmlFor="monitor_url">Monitor URL (defaults to homepage)</Label>
                  <Input
                    id="monitor_url"
                    placeholder={`https://${currentProject?.domain ?? ""}`}
                    value={s.monitor_url ?? ""}
                    onChange={(e) => patch({ monitor_url: e.target.value })}
                  />
                </div>
              )}
              <Toggle
                label="Competitor content monitoring (weekly)"
                description="Weekly diff of competitor pages; alerts on changes."
                checked={s.competitor_monitoring}
                onChange={(v) => patch({ competitor_monitoring: v })}
              />
              {s.competitor_monitoring && (
                <div className="space-y-2 py-2">
                  <Label htmlFor="competitors">
                    Competitor URLs (one per line)
                  </Label>
                  <Textarea
                    id="competitors"
                    placeholder={"https://competitor-a.com\nhttps://competitor-b.com"}
                    value={competitorText}
                    onChange={(e) => setCompetitorText(e.target.value)}
                  />
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Email notifications</CardTitle>
              <CardDescription>
                Requires an email provider configured on the server (Resend).
              </CardDescription>
            </CardHeader>
            <CardContent className="divide-y">
              <Toggle
                label="Enable email notifications"
                checked={s.email_notifications}
                onChange={(v) => patch({ email_notifications: v })}
              />
              <Toggle
                label="New broken links found"
                checked={s.notify_broken_links}
                disabled={!s.email_notifications}
                onChange={(v) => patch({ notify_broken_links: v })}
              />
              <Toggle
                label="Weekly summary report"
                checked={s.weekly_summary}
                disabled={!s.email_notifications}
                onChange={(v) => patch({ weekly_summary: v })}
              />
              <div className="space-y-2 py-2">
                <Label htmlFor="email">
                  Notification email (defaults to your account email)
                </Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="alerts@youragency.com"
                  value={s.notification_email ?? ""}
                  onChange={(e) => patch({ notification_email: e.target.value })}
                />
              </div>
            </CardContent>
          </Card>

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={save} disabled={saving}>
              {saving ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              Save settings
            </Button>
            <Button
              variant="outline"
              onClick={() => runNow("daily")}
              disabled={running !== null}
            >
              {running === "daily" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              Run daily now
            </Button>
            <Button
              variant="outline"
              onClick={() => runNow("weekly")}
              disabled={running !== null}
            >
              {running === "weekly" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              Run weekly now
            </Button>
            {msg && <span className="text-sm text-emerald-600">{msg}</span>}
          </div>
        </>
      )}
    </div>
  );
}

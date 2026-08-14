"use client";

import * as React from "react";
import { Info, Link2, Loader2 } from "lucide-react";

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
  type BacklinkProfile,
  type BrokenLinkResult,
} from "@/lib/api";

export default function BacklinksPage() {
  const { currentProject } = useProject();

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Backlink Center</h1>
        <p className="text-muted-foreground">
          Basic backlink data plus a broken-link-building helper.
        </p>
      </header>

      {/* Global "limited free data" notice */}
      <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          Backlink data uses a <strong>free-tier source</strong> and is limited
          and incomplete. Add an <strong>Ahrefs or Semrush API key</strong>{" "}
          later (server config) for full, accurate data.
        </span>
      </div>

      <BacklinkProfileCard defaultDomain={currentProject?.domain ?? ""} />
      <BrokenLinkCard />
    </div>
  );
}

function BacklinkProfileCard({ defaultDomain }: { defaultDomain: string }) {
  const [domain, setDomain] = React.useState(defaultDomain);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [profile, setProfile] = React.useState<BacklinkProfile | null>(null);

  React.useEffect(() => setDomain(defaultDomain), [defaultDomain]);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setProfile(null);
    try {
      setProfile(await api.getBacklinkProfile(domain));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch backlinks");
    } finally {
      setBusy(false);
    }
  }

  const unconfigured =
    profile &&
    (profile.data_source === "unconfigured" ||
      profile.data_source === "error");

  return (
    <Card>
      <CardHeader>
        <CardTitle>Backlink profile</CardTitle>
        <CardDescription>
          Referring domains, anchor text distribution, and follow/nofollow
          ratio for a domain.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={run} className="flex items-end gap-3">
          <div className="flex-1 space-y-2">
            <Label htmlFor="domain">Domain</Label>
            <Input
              id="domain"
              placeholder="example.com"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              required
            />
          </div>
          <Button type="submit" disabled={busy}>
            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Fetch
          </Button>
        </form>
        {error && <p className="text-sm text-destructive">{error}</p>}

        {unconfigured && (
          <p className="text-sm text-muted-foreground">
            No backlink provider is configured on the server
            (<code>BACKLINK_API_URL</code>), so live data is unavailable. The
            aggregation and UI are ready — configure OpenLinkProfiler (or a
            paid key) to populate this.
          </p>
        )}

        {profile && !unconfigured && (
          <>
            <div className="grid gap-4 sm:grid-cols-4">
              <Stat label="Referring domains" value={profile.referring_domains} />
              <Stat label="Total backlinks" value={profile.total_backlinks} />
              <Stat label="Follow" value={profile.follow_count} />
              <Stat
                label="Nofollow"
                value={`${Math.round(profile.nofollow_ratio * 100)}%`}
              />
            </div>

            <div>
              <p className="mb-2 text-sm font-medium">Anchor text distribution</p>
              <div className="space-y-1">
                {profile.anchor_distribution.map((a, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <span className="w-48 truncate" title={a.anchor}>
                      {a.anchor}
                    </span>
                    <div className="h-2 flex-1 rounded bg-muted">
                      <div
                        className="h-2 rounded bg-primary"
                        style={{ width: `${a.percentage}%` }}
                      />
                    </div>
                    <span className="w-16 text-right text-muted-foreground">
                      {a.count} ({a.percentage}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <p className="text-xs text-muted-foreground">
              Source: {profile.data_source}
              {profile.limited && " · limited free data"}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function BrokenLinkCard() {
  const [url, setUrl] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<BrokenLinkResult | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await runJob<BrokenLinkResult>(() => api.enqueueBrokenLinks(url))
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Broken link check failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Broken Link Building</CardTitle>
        <CardDescription>
          Paste a competitor (or resource) URL. We&apos;ll crawl it and flag
          broken outbound links — pitch your content as the replacement.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={run} className="flex items-end gap-3">
          <div className="flex-1 space-y-2">
            <Label htmlFor="bl-url">Page URL</Label>
            <Input
              id="bl-url"
              placeholder="https://competitor.com/resources"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
            />
          </div>
          <Button type="submit" disabled={busy}>
            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Find broken links
          </Button>
        </form>
        {error && <p className="text-sm text-destructive">{error}</p>}

        {result && (
          <>
            <p className="text-sm text-muted-foreground">
              Checked {result.links_checked} outbound links —{" "}
              <span className="font-medium text-foreground">
                {result.broken_count} broken
              </span>
              .
            </p>
            {result.broken_links.length > 0 ? (
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full text-sm">
                  <thead className="border-b bg-muted/50 text-left">
                    <tr>
                      <th className="p-3 font-medium">Broken URL</th>
                      <th className="p-3 font-medium">Anchor</th>
                      <th className="p-3 font-medium">Type</th>
                      <th className="p-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.broken_links.map((l, i) => (
                      <tr key={i} className="border-b last:border-0">
                        <td
                          className="max-w-[280px] truncate p-3"
                          title={l.url}
                        >
                          <Link2 className="mr-1 inline h-3 w-3" />
                          {l.url}
                        </td>
                        <td className="p-3">{l.anchor}</td>
                        <td className="p-3">
                          <Badge variant="outline">{l.kind}</Badge>
                        </td>
                        <td className="p-3">
                          <Badge variant="destructive">{l.reason}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No broken outbound links found.
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md border p-3">
      <p className="text-xs uppercase text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

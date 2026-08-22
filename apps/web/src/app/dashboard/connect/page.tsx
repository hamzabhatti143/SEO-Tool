"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Globe,
  Loader2,
  ShoppingBag,
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
import { useProject } from "@/components/project-provider";
import { api, type Credentials, type Platform } from "@/lib/api";

export default function ConnectPage() {
  return (
    <React.Suspense fallback={null}>
      <ConnectYourSite />
    </React.Suspense>
  );
}

type Choice = Platform | null;

function ConnectYourSite() {
  const { currentProject } = useProject();
  const params = useSearchParams();
  const [connection, setConnection] = React.useState<Credentials | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [choice, setChoice] = React.useState<Choice>(null);
  const [banner, setBanner] = React.useState<{
    kind: "success" | "error";
    text: string;
  } | null>(null);

  const load = React.useCallback(async (projectId: string) => {
    setLoading(true);
    try {
      setConnection(await api.getConnection(projectId));
    } catch {
      setConnection(null);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    setChoice(null);
    if (currentProject) load(currentProject.id);
    else setConnection(null);
  }, [currentProject, load]);

  // Surface the result of the Shopify OAuth callback redirect.
  React.useEffect(() => {
    if (params.get("platform") !== "shopify") return;
    const status = params.get("status");
    if (status === "connected") {
      setBanner({
        kind: "success",
        text: `Shopify store ${params.get("shop") ?? ""} connected.`,
      });
    } else if (status === "error") {
      setBanner({
        kind: "error",
        text: params.get("message") ?? "Shopify connection failed.",
      });
    }
  }, [params]);

  async function handleDisconnect() {
    if (!currentProject) return;
    await api.disconnect(currentProject.id);
    setConnection(null);
    setBanner(null);
  }

  if (!currentProject) {
    return (
      <div className="mx-auto max-w-3xl">
        <p className="text-muted-foreground">
          Select or create a project first.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Connect Your Site</h1>
        <p className="text-muted-foreground">
          Link {currentProject.name} to WordPress or Shopify so RankPilot can
          read and push SEO changes directly.
        </p>
      </header>

      {banner && (
        <div
          className={`flex items-center gap-2 rounded-md border p-3 text-sm ${
            banner.kind === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-red-200 bg-red-50 text-destructive"
          }`}
        >
          {banner.kind === "success" ? (
            <CheckCircle2 className="h-4 w-4 shrink-0" />
          ) : (
            <AlertCircle className="h-4 w-4 shrink-0" />
          )}
          <span>{banner.text}</span>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading connection…
        </div>
      ) : connection && connection.platform !== "custom" ? (
        <ConnectedCard connection={connection} onDisconnect={handleDisconnect} />
      ) : choice === "wordpress" ? (
        <WordPressForm
          projectId={currentProject.id}
          onBack={() => setChoice(null)}
          onConnected={(c) => {
            setConnection(c);
            setBanner({ kind: "success", text: "WordPress site connected." });
          }}
        />
      ) : choice === "shopify" ? (
        <ShopifyForm
          projectId={currentProject.id}
          onBack={() => setChoice(null)}
        />
      ) : (
        <PlatformPicker onPick={setChoice} />
      )}
    </div>
  );
}

const PLATFORM_META: Record<
  "wordpress" | "shopify",
  { label: string; icon: typeof Globe; blurb: string }
> = {
  wordpress: {
    label: "WordPress",
    icon: Globe,
    blurb:
      "Install the RankPilot plugin, then paste your site URL and API key.",
  },
  shopify: {
    label: "Shopify",
    icon: ShoppingBag,
    blurb: "Authorize RankPilot on your store via secure Shopify OAuth.",
  },
};

function PlatformPicker({ onPick }: { onPick: (p: Platform) => void }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {(["wordpress", "shopify"] as const).map((key) => {
        const { label, icon: Icon, blurb } = PLATFORM_META[key];
        return (
          <button
            key={key}
            type="button"
            onClick={() => onPick(key)}
            className="flex flex-col items-start gap-3 rounded-lg border bg-card p-6 text-left transition-colors hover:border-primary hover:bg-accent"
          >
            <Icon className="h-8 w-8 text-primary" />
            <div>
              <p className="text-lg font-semibold">{label}</p>
              <p className="mt-1 text-sm text-muted-foreground">{blurb}</p>
            </div>
            <span className="mt-auto text-sm font-medium text-primary">
              Connect {label} →
            </span>
          </button>
        );
      })}
    </div>
  );
}

function ConnectedCard({
  connection,
  onDisconnect,
}: {
  connection: Credentials;
  onDisconnect: () => void;
}) {
  const meta =
    connection.platform === "wordpress"
      ? PLATFORM_META.wordpress
      : PLATFORM_META.shopify;
  const Icon = meta.icon;
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <Icon className="h-6 w-6 text-primary" />
          <div>
            <CardTitle className="flex items-center gap-2">
              {meta.label}
              <Badge variant={connection.status === "connected" ? "success" : "destructive"}>
                {connection.status}
              </Badge>
            </CardTitle>
            <CardDescription>{connection.site_url}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {connection.connected_at
            ? `Connected ${new Date(connection.connected_at).toLocaleString()}`
            : "Connection saved."}
        </p>
        <Button variant="outline" size="sm" onClick={onDisconnect}>
          Disconnect
        </Button>
      </CardContent>
    </Card>
  );
}

function BackButton({ onBack }: { onBack: () => void }) {
  return (
    <button
      type="button"
      onClick={onBack}
      className="mb-4 flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="h-4 w-4" /> Choose a different platform
    </button>
  );
}

function WordPressForm({
  projectId,
  onBack,
  onConnected,
}: {
  projectId: string;
  onBack: () => void;
  onConnected: (c: Credentials) => void;
}) {
  const [siteUrl, setSiteUrl] = React.useState("");
  const [apiKey, setApiKey] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const cred = await api.connectWordPress({
        project_id: projectId,
        site_url: siteUrl,
        api_key: apiKey,
      });
      onConnected(cred);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connection failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <BackButton onBack={onBack} />
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-primary" /> Connect WordPress Site
          </CardTitle>
          <CardDescription>
            Install the RankPilot WordPress plugin, copy the API key it
            generates, then enter your details below. We&apos;ll verify the
            connection before saving.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="site_url">Site URL</Label>
              <Input
                id="site_url"
                placeholder="https://your-site.com"
                value={siteUrl}
                onChange={(e) => setSiteUrl(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="api_key">Plugin API key</Label>
              <Input
                id="api_key"
                type="password"
                placeholder="Paste the key from the RankPilot plugin"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                required
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {busy ? "Testing connection…" : "Test & connect"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function ShopifyForm({
  projectId,
  onBack,
}: {
  projectId: string;
  onBack: () => void;
}) {
  const [shop, setShop] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { authorize_url } = await api.shopifyInstall({
        project_id: projectId,
        shop,
      });
      // Hand off to Shopify's OAuth consent screen.
      window.location.href = authorize_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start Shopify OAuth");
      setBusy(false);
    }
  }

  return (
    <div>
      <BackButton onBack={onBack} />
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShoppingBag className="h-5 w-5 text-primary" /> Connect Shopify Store
          </CardTitle>
          <CardDescription>
            Enter your store domain. You&apos;ll be sent to Shopify to approve
            access (themes &amp; products), then returned here.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="shop">Store domain</Label>
              <Input
                id="shop"
                placeholder="my-store.myshopify.com"
                value={shop}
                onChange={(e) => setShop(e.target.value)}
                required
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {busy ? "Redirecting…" : "Continue to Shopify"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

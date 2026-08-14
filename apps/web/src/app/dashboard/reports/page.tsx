"use client";

import * as React from "react";
import { useSession } from "next-auth/react";
import { Download, Eye, Info, Loader2, Save } from "lucide-react";

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
import { api } from "@/lib/api";

function slugify(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export default function ReportsPage() {
  const { currentProject } = useProject();
  const { data: session } = useSession();
  const isAgency = session?.user?.tier === "agency";

  const [error, setError] = React.useState<string | null>(null);
  const [pdfBusy, setPdfBusy] = React.useState(false);
  const [htmlBusy, setHtmlBusy] = React.useState(false);

  async function generatePdf() {
    if (!currentProject) return;
    setPdfBusy(true);
    setError(null);
    try {
      const blob = await api.reportPdfBlob(currentProject.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `seo-report-${slugify(currentProject.name)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "PDF generation failed");
    } finally {
      setPdfBusy(false);
    }
  }

  async function previewHtml() {
    if (!currentProject) return;
    setHtmlBusy(true);
    setError(null);
    try {
      const blob = await api.reportHtmlBlob(currentProject.id);
      window.open(URL.createObjectURL(blob), "_blank");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setHtmlBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Reports</h1>
        <p className="text-muted-foreground">
          A single branded report aggregating Audit, Keyword Research, and
          Content for {currentProject?.name ?? "your project"}.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Generate report</CardTitle>
          <CardDescription>
            Download a branded PDF, or preview the HTML version.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-3">
            <Button onClick={generatePdf} disabled={pdfBusy || !currentProject}>
              {pdfBusy ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Download className="mr-2 h-4 w-4" />
              )}
              Generate Report (PDF)
            </Button>
            <Button
              variant="outline"
              onClick={previewHtml}
              disabled={htmlBusy || !currentProject}
            >
              {htmlBusy ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Eye className="mr-2 h-4 w-4" />
              )}
              Preview HTML
            </Button>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <p className="text-xs text-muted-foreground">
            PDF generation requires WeasyPrint on the server. If it isn&apos;t
            installed, use Preview HTML (or print to PDF from the browser).
          </p>
        </CardContent>
      </Card>

      <BrandingCard isAgency={isAgency} />
    </div>
  );
}

function BrandingCard({ isAgency }: { isAgency: boolean }) {
  const { currentProject } = useProject();
  const [brandName, setBrandName] = React.useState("");
  const [logoUrl, setLogoUrl] = React.useState("");
  const [color, setColor] = React.useState("#2563eb");
  const [customDomain, setCustomDomain] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [saved, setSaved] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (currentProject) {
      setBrandName(currentProject.brand_name ?? "");
      setLogoUrl(currentProject.brand_logo_url ?? "");
      setColor(currentProject.brand_color ?? "#2563eb");
      setCustomDomain(currentProject.custom_domain ?? "");
    }
  }, [currentProject]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!currentProject) return;
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await api.updateProject(currentProject.id, {
        brand_name: brandName || null,
        brand_logo_url: logoUrl || null,
        brand_color: color || null,
        custom_domain: customDomain || null,
      });
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save branding");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>White-label branding</CardTitle>
        <CardDescription>
          Replace RankPilot AI branding on reports with your own.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!isAgency && (
          <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              White-label reports are an <strong>Agency plan</strong> feature.
              You can save settings now, but reports stay RankPilot-branded
              until you upgrade.
            </span>
          </div>
        )}
        <form onSubmit={save} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="brand">Brand / agency name</Label>
            <Input
              id="brand"
              placeholder="Acme Agency"
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="logo">Logo URL</Label>
            <Input
              id="logo"
              placeholder="https://acme.com/logo.png"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="color">Brand color</Label>
            <div className="flex items-center gap-3">
              <input
                id="color"
                type="color"
                value={color}
                onChange={(e) => setColor(e.target.value)}
                className="h-10 w-14 rounded border border-input"
              />
              <Input
                value={color}
                onChange={(e) => setColor(e.target.value)}
                className="w-32"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="domain">Custom domain (optional)</Label>
            <Input
              id="domain"
              placeholder="reports.youragency.com"
              value={customDomain}
              onChange={(e) => setCustomDomain(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Stored for white-label use; DNS/hosting must point here
              separately.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={busy}>
              {busy ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              Save branding
            </Button>
            {saved && (
              <span className="text-sm text-emerald-600">Saved.</span>
            )}
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </form>
      </CardContent>
    </Card>
  );
}

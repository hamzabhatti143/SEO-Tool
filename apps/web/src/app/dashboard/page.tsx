"use client";

import * as React from "react";
import Link from "next/link";
import {
  Download,
  FileBarChart,
  FileText,
  Gauge,
  LayoutGrid,
  Link2,
  Loader2,
  Network,
  Search,
  SlidersHorizontal,
  Swords,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useProject } from "@/components/project-provider";
import { api } from "@/lib/api";

const MODULES = [
  {
    href: "/dashboard/audit",
    title: "Website Audit",
    description:
      "Crawl a URL and check meta tags, headings, broken links, and page-speed basics.",
    icon: Gauge,
  },
  {
    href: "/dashboard/optimizer",
    title: "On-Page Optimizer",
    description:
      "Score a page against a target keyword: placement, density, links, images, readability, and AI keyword suggestions.",
    icon: SlidersHorizontal,
  },
  {
    href: "/dashboard/keywords",
    title: "Keyword Research",
    description:
      "Generate related keywords, long-tail variations, and search intent from a seed keyword.",
    icon: Search,
  },
  {
    href: "/dashboard/competitors",
    title: "Competitor Intel",
    description:
      "Crawl a competitor and compare topic focus, keyword gaps, and content gaps against your project (AI-estimated).",
    icon: Swords,
  },
  {
    href: "/dashboard/gaps",
    title: "Content Gaps",
    description:
      "Compare 2–3 competitors against your project and get prioritized content opportunities with ready-to-use briefs.",
    icon: LayoutGrid,
  },
  {
    href: "/dashboard/internal-links",
    title: "Internal Links",
    description:
      "Crawl your site, visualize the internal link graph, find orphan pages, and get semantic linking suggestions.",
    icon: Network,
  },
  {
    href: "/dashboard/backlinks",
    title: "Backlink Center",
    description:
      "Basic backlink data (referring domains, anchors, follow ratio) plus a broken-link-building helper. Limited free data.",
    icon: Link2,
  },
  {
    href: "/dashboard/content",
    title: "AI Content Studio",
    description:
      "Generate an SEO-optimized blog post from a topic and target keyword.",
    icon: FileText,
  },
  {
    href: "/dashboard/reports",
    title: "Reports",
    description:
      "Aggregate Audit, Keywords, and Content into one branded PDF report (white-label on Agency).",
    icon: FileBarChart,
  },
];

export default function DashboardOverview() {
  const { currentProject, loading, error } = useProject();
  const [reportBusy, setReportBusy] = React.useState(false);
  const [reportError, setReportError] = React.useState<string | null>(null);

  async function generateReport() {
    if (!currentProject) return;
    setReportBusy(true);
    setReportError(null);
    try {
      const blob = await api.reportPdfBlob(currentProject.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `seo-report-${currentProject.name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "")}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setReportError(e instanceof Error ? e.message : "Report failed");
    } finally {
      setReportBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            {loading
              ? "Loading workspace…"
              : error
                ? `Error: ${error}`
                : currentProject
                  ? `Working on ${currentProject.name} (${currentProject.domain})`
                  : "Create a project in the sidebar to get started."}
          </p>
          {reportError && (
            <p className="mt-1 text-sm text-destructive">{reportError}</p>
          )}
        </div>
        <Button onClick={generateReport} disabled={reportBusy || !currentProject}>
          {reportBusy ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Download className="mr-2 h-4 w-4" />
          )}
          Generate Report
        </Button>
      </header>

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {MODULES.map(({ href, title, description, icon: Icon }) => (
          <Link key={href} href={href}>
            <Card className="h-full transition-colors hover:border-primary">
              <CardHeader>
                <Icon className="h-8 w-8 text-primary" />
                <CardTitle>{title}</CardTitle>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

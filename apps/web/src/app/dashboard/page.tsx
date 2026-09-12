"use client";

import * as React from "react";
import Link from "next/link";
import {
  Download,
  FileBarChart,
  FileText,
  FolderPlus,
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
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Stagger, StaggerItem, HoverLift } from "@/components/motion";
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
      "Aggregate Audit, Keywords, and Content into one branded PDF report (white-label on Premium).",
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
    <div className="space-y-8">
      <PageHeader
        title="Dashboard"
        description={
          loading
            ? "Loading workspace…"
            : error
              ? `Error: ${error}`
              : currentProject
                ? `Working on ${currentProject.name} · ${currentProject.domain}`
                : "Select a project from the top bar, or create one to get started."
        }
        actions={
          <Button
            onClick={generateReport}
            disabled={reportBusy || !currentProject}
          >
            {reportBusy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-2 h-4 w-4" />
            )}
            Generate Report
          </Button>
        }
      />

      {reportError && <p className="text-sm text-destructive">{reportError}</p>}

      {!loading && !error && !currentProject ? (
        <EmptyState
          icon={FolderPlus}
          title="No project yet"
          description="Create your first project to run audits, research keywords, and generate content."
        />
      ) : (
        <Stagger className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {MODULES.map(({ href, title, description, icon: Icon }) => (
            <StaggerItem key={href}>
              <HoverLift className="h-full">
                <Link href={href} className="block h-full">
                  <Card className="h-full shadow-soft transition-colors hover:border-primary/50 hover:shadow-card">
                    <CardContent className="space-y-3 p-5">
                      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                        <Icon className="h-5 w-5" />
                      </span>
                      <div className="space-y-1">
                        <h3 className="font-semibold leading-none tracking-tight">
                          {title}
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          {description}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              </HoverLift>
            </StaggerItem>
          ))}
        </Stagger>
      )}
    </div>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import {
  FileBarChart,
  FileText,
  Gauge,
  LayoutDashboard,
  LayoutGrid,
  Link2,
  LogOut,
  Network,
  Search,
  Settings,
  SlidersHorizontal,
  Swords,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ProjectPicker } from "@/components/project-picker";
import { useProject } from "@/components/project-provider";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/audit", label: "Website Audit", icon: Gauge },
  {
    href: "/dashboard/optimizer",
    label: "On-Page Optimizer",
    icon: SlidersHorizontal,
  },
  { href: "/dashboard/keywords", label: "Keyword Research", icon: Search },
  {
    href: "/dashboard/competitors",
    label: "Competitor Intel",
    icon: Swords,
  },
  {
    href: "/dashboard/gaps",
    label: "Content Gaps",
    icon: LayoutGrid,
  },
  {
    href: "/dashboard/internal-links",
    label: "Internal Links",
    icon: Network,
  },
  { href: "/dashboard/backlinks", label: "Backlink Center", icon: Link2 },
  { href: "/dashboard/content", label: "AI Content Studio", icon: FileText },
  { href: "/dashboard/reports", label: "Reports", icon: FileBarChart },
  { href: "/dashboard/settings", label: "Automation", icon: Settings },
  { href: "/dashboard/agency", label: "Agency Mode", icon: Users },
];

const TIER_LABEL: Record<string, string> = {
  free: "Free",
  pro: "Pro",
  agency: "Agency",
};

export function Sidebar() {
  const pathname = usePathname();
  const { data: session } = useSession();
  const { currentProject } = useProject();
  const tier = session?.user?.tier ?? "free";

  // White-label: Agency projects with branding replace RankPilot AI branding.
  const whiteLabel =
    tier === "agency" && currentProject?.brand_name
      ? {
          name: currentProject.brand_name,
          logo: currentProject.brand_logo_url,
          color: currentProject.brand_color ?? undefined,
        }
      : null;

  return (
    <aside className="flex w-64 shrink-0 flex-col gap-6 border-r bg-muted/30 p-4">
      <div className="px-2 py-2">
        <Link href="/dashboard" className="text-xl font-bold tracking-tight">
          {whiteLabel ? (
            whiteLabel.logo ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={whiteLabel.logo}
                alt={whiteLabel.name}
                className="max-h-8"
              />
            ) : (
              <span style={{ color: whiteLabel.color }}>{whiteLabel.name}</span>
            )
          ) : (
            <>
              RankPilot <span className="text-primary">AI</span>
            </>
          )}
        </Link>
      </div>

      <ProjectPicker />

      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/dashboard"
              ? pathname === href
              : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto space-y-3 border-t pt-4">
        <div className="flex items-center justify-between px-2">
          <span className="truncate text-sm text-muted-foreground">
            {session?.user?.email}
          </span>
          <Badge variant={tier === "free" ? "secondary" : "default"}>
            {TIER_LABEL[tier] ?? tier}
          </Badge>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start"
          onClick={() => signOut({ callbackUrl: "/login" })}
        >
          <LogOut className="mr-2 h-4 w-4" />
          Sign out
        </Button>
      </div>
    </aside>
  );
}

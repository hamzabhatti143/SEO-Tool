import {
  Activity,
  FileBarChart,
  FileText,
  Gauge,
  History,
  LayoutDashboard,
  LayoutGrid,
  Link2,
  Network,
  Plug,
  Search,
  Settings,
  SlidersHorizontal,
  Swords,
  Users,
  type LucideIcon,
} from "lucide-react";

import type { PremiumFeature } from "@/lib/feature-flags";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  feature?: PremiumFeature;
};

export type NavSection = { title?: string; items: NavItem[] };

/** Grouped navigation for the user dashboard sidebar + mobile drawer. */
export const NAV_SECTIONS: NavSection[] = [
  {
    items: [
      { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
      { href: "/dashboard/connect", label: "Connect Your Site", icon: Plug },
    ],
  },
  {
    title: "Analyze",
    items: [
      { href: "/dashboard/audit", label: "Website Audit", icon: Gauge },
      { href: "/dashboard/cwv", label: "Core Web Vitals", icon: Activity },
      { href: "/dashboard/fix-history", label: "Fix History", icon: History },
      {
        href: "/dashboard/optimizer",
        label: "On-Page Optimizer",
        icon: SlidersHorizontal,
      },
    ],
  },
  {
    title: "Research",
    items: [
      { href: "/dashboard/keywords", label: "Keyword Research", icon: Search },
      { href: "/dashboard/competitors", label: "Competitor Intel", icon: Swords },
      { href: "/dashboard/gaps", label: "Content Gaps", icon: LayoutGrid },
      { href: "/dashboard/internal-links", label: "Internal Links", icon: Network },
      {
        href: "/dashboard/backlinks",
        label: "Backlink Center",
        icon: Link2,
        feature: "backlink_center",
      },
    ],
  },
  {
    title: "Create & Grow",
    items: [
      { href: "/dashboard/content", label: "AI Content Studio", icon: FileText },
      { href: "/dashboard/reports", label: "Reports", icon: FileBarChart },
      {
        href: "/dashboard/settings",
        label: "Automation",
        icon: Settings,
        feature: "automation",
      },
      {
        href: "/dashboard/agency",
        label: "Agency Mode",
        icon: Users,
        feature: "agency_mode",
      },
    ],
  },
];

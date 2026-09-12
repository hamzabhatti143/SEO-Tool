"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import { Lock, PanelLeftClose, PanelLeftOpen, Rocket } from "lucide-react";

import { cn } from "@/lib/utils";
import { tierAllows } from "@/lib/feature-flags";
import { NAV_SECTIONS } from "@/components/nav-config";
import { Badge } from "@/components/ui/badge";
import { useProject } from "@/components/project-provider";

const TIER_LABEL: Record<string, string> = {
  standard: "Standard",
  premium: "Premium",
};

export function Sidebar({
  collapsed = false,
  onToggleCollapse,
  onNavigate,
}: {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const { data: session } = useSession();
  const { currentProject } = useProject();
  const tier = session?.user?.tier ?? "standard";

  const whiteLabel =
    tierAllows(tier, "white_label") && currentProject?.brand_name
      ? {
          name: currentProject.brand_name,
          logo: currentProject.brand_logo_url,
          color: currentProject.brand_color ?? undefined,
        }
      : null;

  return (
    <div className="flex h-full flex-col bg-card">
      {/* Brand */}
      <div
        className={cn(
          "flex h-16 items-center border-b px-4",
          collapsed && "justify-center px-0"
        )}
      >
        <Link
          href="/dashboard"
          onClick={onNavigate}
          className="flex items-center gap-2 overflow-hidden font-bold tracking-tight"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Rocket className="h-4 w-4" />
          </span>
          {!collapsed &&
            (whiteLabel ? (
              whiteLabel.logo ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={whiteLabel.logo}
                  alt={whiteLabel.name}
                  className="max-h-7"
                />
              ) : (
                <span style={{ color: whiteLabel.color }}>
                  {whiteLabel.name}
                </span>
              )
            ) : (
              <span className="text-lg">
                RankPilot <span className="text-primary">AI</span>
              </span>
            ))}
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-4 overflow-y-auto px-3 py-4">
        {NAV_SECTIONS.map((section, si) => (
          <div key={section.title ?? si} className="space-y-1">
            {section.title && !collapsed && (
              <p className="px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">
                {section.title}
              </p>
            )}
            {section.items.map(({ href, label, icon: Icon, feature }) => {
              const active =
                href === "/dashboard"
                  ? pathname === href
                  : pathname.startsWith(href);
              const locked = feature ? !tierAllows(tier, feature) : false;
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={onNavigate}
                  title={collapsed ? label : undefined}
                  className={cn(
                    "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    collapsed && "justify-center px-0",
                    active
                      ? "bg-primary text-primary-foreground shadow-soft"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                    locked && !active && "opacity-60"
                  )}
                >
                  <Icon className="h-[18px] w-[18px] shrink-0" />
                  {!collapsed && (
                    <>
                      <span className="flex-1 truncate">{label}</span>
                      {locked && (
                        <Lock className="h-3.5 w-3.5 shrink-0 opacity-70" />
                      )}
                    </>
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer: tier + collapse toggle */}
      <div
        className={cn(
          "flex items-center gap-2 border-t p-3",
          collapsed ? "flex-col" : "justify-between"
        )}
      >
        <Badge variant={tier === "standard" ? "secondary" : "default"}>
          {collapsed ? (TIER_LABEL[tier] ?? tier).charAt(0) : TIER_LABEL[tier] ?? tier}
        </Badge>
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="hidden rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground lg:block"
          >
            {collapsed ? (
              <PanelLeftOpen className="h-4 w-4" />
            ) : (
              <PanelLeftClose className="h-4 w-4" />
            )}
          </button>
        )}
      </div>
    </div>
  );
}

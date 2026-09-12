"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { MotionConfig } from "framer-motion";

import { cn } from "@/lib/utils";
import { FadeIn } from "@/components/motion";
import { Sidebar } from "@/components/sidebar";
import { TopBar } from "@/components/top-bar";
import { Sheet } from "@/components/ui/sheet";

const COLLAPSE_KEY = "rp_sidebar_collapsed";

export function DashboardChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = React.useState(false);
  const [mobileOpen, setMobileOpen] = React.useState(false);

  React.useEffect(() => {
    setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === "1");
  }, []);

  // Close the mobile drawer on navigation.
  React.useEffect(() => setMobileOpen(false), [pathname]);

  function toggleCollapse() {
    setCollapsed((c) => {
      const next = !c;
      window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      return next;
    });
  }

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-screen bg-muted/30">
        {/* Desktop rail */}
        <aside
          className={cn(
            "sticky top-0 hidden h-screen shrink-0 border-r transition-[width] duration-200 ease-out lg:block",
            collapsed ? "w-[4.5rem]" : "w-64"
          )}
        >
          <Sidebar collapsed={collapsed} onToggleCollapse={toggleCollapse} />
        </aside>

        {/* Mobile drawer */}
        <Sheet open={mobileOpen} onClose={() => setMobileOpen(false)}>
          <Sidebar onNavigate={() => setMobileOpen(false)} />
        </Sheet>

        {/* Main column */}
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar onOpenMobileNav={() => setMobileOpen(true)} />
          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
            <FadeIn key={pathname} className="mx-auto w-full max-w-6xl">
              {children}
            </FadeIn>
          </main>
        </div>
      </div>
    </MotionConfig>
  );
}

"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { MotionConfig } from "framer-motion";
import { LogOut, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { FadeIn } from "@/components/motion";
import { adminApi, isAdminAuthed } from "@/lib/admin-api";

/**
 * Chrome + client-side auth guard for authenticated admin pages. Its own
 * distinct header — deliberately no shared nav with the user dashboard.
 */
export function AdminShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = React.useState(false);

  React.useEffect(() => {
    if (!isAdminAuthed()) {
      router.replace("/admin/login");
    } else {
      setReady(true);
    }
  }, [router]);

  if (!ready) return null;

  function signOut() {
    adminApi.logout();
    router.replace("/admin/login");
  }

  return (
    <MotionConfig reducedMotion="user">
      <div className="min-h-screen">
        <header className="sticky top-0 z-30 border-b border-slate-800 bg-slate-900 text-slate-50">
          <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
            <div className="flex items-center gap-2.5 font-semibold">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <ShieldCheck className="h-4 w-4" />
              </span>
              <span>
                RankPilot <span className="text-primary">Admin</span>
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="text-slate-200 hover:bg-slate-800 hover:text-slate-50"
              onClick={signOut}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </Button>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
          <FadeIn>{children}</FadeIn>
        </main>
      </div>
    </MotionConfig>
  );
}

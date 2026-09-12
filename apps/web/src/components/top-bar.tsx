"use client";

import Link from "next/link";
import { signOut, useSession } from "next-auth/react";
import { Bell, KeyRound, LogOut, Menu } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Dropdown, DropdownItem } from "@/components/ui/dropdown";
import { ProjectSelector } from "@/components/project-selector";

function initials(nameOrEmail: string): string {
  const base = nameOrEmail.split("@")[0];
  const parts = base.split(/[.\s_-]+/).filter(Boolean);
  return (parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "");
}

export function TopBar({ onOpenMobileNav }: { onOpenMobileNav: () => void }) {
  const { data: session } = useSession();
  const email = session?.user?.email ?? "";
  const tier = session?.user?.tier ?? "standard";

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <button
        type="button"
        onClick={onOpenMobileNav}
        aria-label="Open menu"
        className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground lg:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      <ProjectSelector />

      <div className="ml-auto flex items-center gap-1">
        {/* Notifications */}
        <Dropdown
          trigger={({ toggle }) => (
            <button
              type="button"
              onClick={toggle}
              aria-label="Notifications"
              className="relative rounded-full p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              <Bell className="h-5 w-5" />
            </button>
          )}
        >
          {() => (
            <div className="w-72">
              <p className="px-2.5 py-1.5 text-sm font-semibold">
                Notifications
              </p>
              <div className="border-t px-3 py-8 text-center text-sm text-muted-foreground">
                You&apos;re all caught up.
              </div>
            </div>
          )}
        </Dropdown>

        {/* User menu */}
        <Dropdown
          trigger={({ toggle }) => (
            <button
              type="button"
              onClick={toggle}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-sm font-semibold uppercase text-primary-foreground transition-opacity hover:opacity-90"
              aria-label="Account menu"
            >
              {initials(email) || "U"}
            </button>
          )}
        >
          {({ close }) => (
            <div className="w-60">
              <div className="px-2.5 py-2">
                <p className="truncate text-sm font-medium">{email}</p>
                <Badge
                  variant={tier === "standard" ? "secondary" : "default"}
                  className="mt-1"
                >
                  {tier === "premium" ? "Premium" : "Standard"} plan
                </Badge>
              </div>
              <div className="my-1 border-t" />
              <Link
                href="/set-password"
                onClick={close}
                className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                <KeyRound className="h-4 w-4" />
                Change password
              </Link>
              <DropdownItem
                onClick={() => signOut({ callbackUrl: "/login" })}
                className="text-destructive"
              >
                <LogOut className="h-4 w-4" />
                Sign out
              </DropdownItem>
            </div>
          )}
        </Dropdown>
      </div>
    </header>
  );
}

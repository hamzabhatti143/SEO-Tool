"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { isAdminAuthed } from "@/lib/admin-api";

/** Bounce /admin to the accounts dashboard (or login if not authenticated). */
export default function AdminIndexPage() {
  const router = useRouter();
  React.useEffect(() => {
    router.replace(isAdminAuthed() ? "/admin/accounts" : "/admin/login");
  }, [router]);
  return null;
}

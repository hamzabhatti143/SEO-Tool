"use client";

import * as React from "react";
import { useParams } from "next/navigation";

/**
 * Public, read-only client report view (no login). The report HTML is served
 * by the backend's public share endpoint and embedded in a sandboxed iframe.
 */
export default function SharedReportPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const src = `/api/backend/public/share/${token}/report`;

  return (
    <main className="min-h-screen bg-muted/30">
      <div className="border-b bg-background px-6 py-3 text-sm text-muted-foreground">
        Shared SEO report · read-only
      </div>
      <iframe
        title="SEO report"
        src={src}
        className="h-[calc(100vh-49px)] w-full border-0 bg-white"
      />
    </main>
  );
}

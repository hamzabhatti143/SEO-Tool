import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-24">
      <h1 className="text-4xl font-bold tracking-tight">
        RankPilot <span className="text-primary">AI</span>
      </h1>
      <p className="max-w-md text-center text-muted-foreground">
        AI-powered SEO: website audits, keyword research, and an AI content
        studio — all in one dashboard.
      </p>
      <Button asChild>
        <Link href="/dashboard">Open dashboard</Link>
      </Button>
    </main>
  );
}

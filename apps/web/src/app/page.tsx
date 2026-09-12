import Link from "next/link";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Check,
  FileText,
  Gauge,
  Link2,
  Lock,
  Network,
  Search,
  Settings,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { HeroCanvas } from "@/components/three/scenes";

const FEATURES = [
  {
    icon: Gauge,
    title: "Website Audit",
    description:
      "Crawl any page for meta tags, headings, broken links, and page-speed basics with a clear SEO score.",
  },
  {
    icon: Activity,
    title: "Core Web Vitals",
    description:
      "Real Lighthouse metrics (LCP, CLS, INP) with prioritized, one-click fixes for WordPress.",
  },
  {
    icon: Search,
    title: "Keyword Research",
    description:
      "Related terms, long-tail variations, and People-Also-Ask questions, clustered by topic.",
  },
  {
    icon: FileText,
    title: "AI Content Studio",
    description:
      "Generate SEO-optimized, on-brand content from a topic and target keyword in seconds.",
  },
  {
    icon: Network,
    title: "Internal Links",
    description:
      "Visualize your link graph, surface orphan pages, and get semantic linking suggestions.",
  },
  {
    icon: BarChart3,
    title: "Competitor Intel",
    description:
      "Compare topic focus, keyword gaps, and content gaps against any competitor.",
  },
];

const STANDARD_FEATURES = [
  "Website Audit & Core Web Vitals",
  "On-Page Optimizer",
  "Keyword Research & clustering",
  "Competitor Intel & Content Gaps",
  "Internal Link Optimizer",
  "AI Content Studio",
  "Branded PDF & HTML reports",
];

const PREMIUM_ONLY = [
  "Backlink Center",
  "Automation (scheduled audits & alerts)",
  "Agency Mode (team roles & client links)",
  "White-label reports",
];

export default function HomePage() {
  return (
    <main className="flex flex-col">
      {/* ---------------- Hero ---------------- */}
      <section className="relative isolate flex min-h-[640px] flex-col overflow-hidden bg-gradient-to-b from-slate-950 via-indigo-950 to-slate-900 lg:min-h-[720px]">
        {/* 3D scene, contained to the hero. Falls back to the gradient above. */}
        <HeroCanvas />
        {/* Legibility veil over the canvas. */}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-slate-950/40" />

        {/* Nav */}
        <header className="relative z-10 mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
          <div className="flex items-center gap-2 text-lg font-bold text-white">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Sparkles className="h-4 w-4 text-primary-foreground" />
            </span>
            RankPilot <span className="text-indigo-300">AI</span>
          </div>
          <Button asChild variant="ghost" className="text-white hover:bg-white/10 hover:text-white">
            <Link href="/login">Sign in</Link>
          </Button>
        </header>

        {/* Hero content */}
        <div className="relative z-10 mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-6 py-16 text-center">
          <span className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-medium text-indigo-200 backdrop-blur">
            <Sparkles className="h-3.5 w-3.5" />
            AI-powered SEO, end to end
          </span>
          <h1 className="text-4xl font-bold tracking-tight text-white sm:text-6xl">
            Rank higher with an
            <span className="bg-gradient-to-r from-indigo-300 to-violet-300 bg-clip-text text-transparent">
              {" "}
              AI copilot
            </span>{" "}
            for SEO
          </h1>
          <p className="mt-6 max-w-xl text-lg text-slate-300">
            Audits, Core Web Vitals fixes, keyword research, competitor
            intelligence, and an AI content studio — all in one dashboard.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Button asChild size="lg">
              <Link href="/contact">
                Contact us for access
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
            <Button
              asChild
              size="lg"
              variant="outline"
              className="border-white/20 bg-white/5 text-white hover:bg-white/10 hover:text-white"
            >
              <Link href="/login">Sign in</Link>
            </Button>
          </div>
          <p className="mt-5 text-sm text-slate-400">
            RankPilot AI is invite-only.
          </p>
        </div>
      </section>

      {/* ---------------- Features ---------------- */}
      <section className="mx-auto w-full max-w-6xl px-6 py-20 sm:py-24">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Everything you need to grow organic traffic
          </h2>
          <p className="mt-4 text-muted-foreground">
            A complete toolkit that turns SEO insight into action.
          </p>
        </div>
        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <div
              key={title}
              className="rounded-xl border bg-card p-6 shadow-soft transition-shadow hover:shadow-card"
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                <Icon className="h-5 w-5" />
              </span>
              <h3 className="mt-4 font-semibold">{title}</h3>
              <p className="mt-1.5 text-sm text-muted-foreground">
                {description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------------- Pricing ---------------- */}
      <section className="border-t bg-muted/30 py-20 sm:py-24">
        <div className="mx-auto w-full max-w-5xl px-6">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Two simple plans
            </h2>
            <p className="mt-4 text-muted-foreground">
              Plans are assigned by our team when your account is created.
            </p>
          </div>

          <div className="mx-auto mt-14 grid max-w-3xl gap-6 md:grid-cols-2">
            {/* Standard */}
            <div className="flex flex-col rounded-2xl border bg-card p-8 shadow-soft">
              <h3 className="text-lg font-semibold">Standard</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                The full core toolkit for growing sites.
              </p>
              <ul className="mt-6 space-y-3 text-sm">
                {STANDARD_FEATURES.map((f) => (
                  <li key={f} className="flex items-start gap-2.5">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    <span>{f}</span>
                  </li>
                ))}
                {PREMIUM_ONLY.map((f) => (
                  <li
                    key={f}
                    className="flex items-start gap-2.5 text-muted-foreground/70"
                  >
                    <Lock className="mt-0.5 h-4 w-4 shrink-0" />
                    <span className="line-through decoration-muted-foreground/40">
                      {f}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Premium */}
            <div className="relative flex flex-col rounded-2xl border-2 border-primary bg-card p-8 shadow-card">
              <span className="absolute -top-3 left-8 inline-flex items-center gap-1 rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground">
                <Sparkles className="h-3 w-3" />
                Everything unlocked
              </span>
              <h3 className="text-lg font-semibold">Premium</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Everything in Standard, plus power tools for agencies.
              </p>
              <ul className="mt-6 space-y-3 text-sm">
                <li className="flex items-start gap-2.5">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <span className="font-medium">Everything in Standard</span>
                </li>
                {PREMIUM_ONLY.map((f) => {
                  const Icon =
                    f.startsWith("Backlink") ? Link2 : f.startsWith("Automation") ? Settings : Sparkles;
                  return (
                    <li key={f} className="flex items-start gap-2.5">
                      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>{f}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- CTA ---------------- */}
      <section className="mx-auto w-full max-w-4xl px-6 py-20 text-center sm:py-24">
        <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
          Ready to climb the rankings?
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
          RankPilot AI is invite-only. Tell us about your site and our team will
          set you up with the right plan.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Button asChild size="lg">
            <Link href="/contact">
              Contact us for access
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/login">Sign in</Link>
          </Button>
        </div>
      </section>

      {/* ---------------- Footer ---------------- */}
      <footer className="border-t py-8">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-3 px-6 text-sm text-muted-foreground sm:flex-row">
          <span className="font-semibold text-foreground">
            RankPilot <span className="text-primary">AI</span>
          </span>
          <span>© {new Date().getFullYear()} RankPilot AI. All rights reserved.</span>
        </div>
      </footer>
    </main>
  );
}

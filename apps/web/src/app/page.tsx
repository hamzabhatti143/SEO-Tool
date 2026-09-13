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
  Plug,
  Search,
  Settings,
  Sparkles,
  TrendingUp,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { HeroCanvas } from "@/components/three/scenes";
import { FadeIn, HoverLift, Reveal } from "@/components/motion";

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

const STEPS = [
  {
    icon: Plug,
    title: "Connect your site",
    description:
      "Link WordPress or Shopify with the RankPilot plugin, or just point us at any URL to start analyzing.",
  },
  {
    icon: Sparkles,
    title: "Analyze & optimize",
    description:
      "Run audits and Core Web Vitals fixes, research keywords, and generate optimized content with AI — all in one place.",
  },
  {
    icon: TrendingUp,
    title: "Track & grow",
    description:
      "Automate weekly audits, monitor competitors and backlinks, and get branded reports as your rankings climb.",
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

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-primary">
      {children}
    </span>
  );
}

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
          <Button
            asChild
            variant="ghost"
            className="text-white hover:bg-white/10 hover:text-white"
          >
            <Link href="/login">Sign in</Link>
          </Button>
        </header>

        {/* Hero content (staggered entrance on load) */}
        <div className="relative z-10 mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-6 py-16 text-center">
          <FadeIn delay={0.05}>
            <span className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-medium text-indigo-200 backdrop-blur">
              <Sparkles className="h-3.5 w-3.5 animate-pulse" />
              AI-powered SEO, end to end
            </span>
          </FadeIn>
          <FadeIn delay={0.15}>
            <h1 className="text-4xl font-bold tracking-tight text-white sm:text-6xl">
              Rank higher with an
              <span className="animate-gradient-x bg-gradient-to-r from-indigo-300 via-violet-300 to-indigo-300 bg-[length:200%_auto] bg-clip-text text-transparent">
                {" "}
                AI copilot
              </span>{" "}
              for SEO
            </h1>
          </FadeIn>
          <FadeIn delay={0.25}>
            <p className="mt-6 max-w-xl text-lg text-slate-300">
              Audits, Core Web Vitals fixes, keyword research, competitor
              intelligence, and an AI content studio — all in one dashboard.
            </p>
          </FadeIn>
          <FadeIn
            delay={0.35}
            className="mt-9 flex flex-wrap items-center justify-center gap-3"
          >
            <Button asChild size="lg" className="group">
              <Link href="/contact">
                Contact us for access
                <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
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
          </FadeIn>
          <FadeIn delay={0.45}>
            <p className="mt-5 text-sm text-slate-400">
              RankPilot AI is invite-only.
            </p>
          </FadeIn>
        </div>
      </section>

      {/* ---------------- Features ---------------- */}
      <section className="relative mx-auto w-full max-w-6xl px-6 py-24 sm:py-28">
        <Reveal className="mx-auto max-w-2xl text-center">
          <Eyebrow>Features</Eyebrow>
          <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
            Everything you need to grow organic traffic
          </h2>
          <p className="mt-4 text-muted-foreground">
            A complete toolkit that turns SEO insight into action — no
            duct-taped stack of single-purpose tools.
          </p>
        </Reveal>

        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, description }, i) => (
            <Reveal key={title} delay={i * 0.06} className="h-full">
              <HoverLift className="group relative flex h-full flex-col overflow-hidden rounded-2xl border bg-card p-6 shadow-soft transition-colors hover:border-primary/40 hover:shadow-card">
                {/* top accent line on hover */}
                <span className="absolute inset-x-0 top-0 h-0.5 origin-left scale-x-0 bg-gradient-to-r from-indigo-500 to-violet-500 transition-transform duration-300 group-hover:scale-x-100" />
                <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow-lg shadow-indigo-500/25 transition-transform duration-300 group-hover:scale-110">
                  <Icon className="h-6 w-6" />
                </span>
                <h3 className="mt-5 text-base font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {description}
                </p>
              </HoverLift>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ---------------- How it works ---------------- */}
      <section className="border-y bg-muted/30 py-24 sm:py-28">
        <div className="mx-auto w-full max-w-6xl px-6">
          <Reveal className="mx-auto max-w-2xl text-center">
            <Eyebrow>How it works</Eyebrow>
            <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
              From audit to action in three steps
            </h2>
            <p className="mt-4 text-muted-foreground">
              Go from &ldquo;where do I even start?&rdquo; to a prioritized plan
              — fast.
            </p>
          </Reveal>

          <div className="relative mt-16">
            {/* connecting line (desktop) */}
            <div className="absolute inset-x-0 top-8 hidden h-px bg-gradient-to-r from-transparent via-border to-transparent md:block" />
            <div className="grid gap-10 md:grid-cols-3">
              {STEPS.map(({ icon: Icon, title, description }, i) => (
                <Reveal
                  key={title}
                  delay={i * 0.1}
                  className="relative text-center md:text-left"
                >
                  <div className="relative z-10 mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-lg shadow-indigo-500/30 md:mx-0">
                    <Icon className="h-7 w-7" />
                    <span className="absolute -right-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full bg-background text-xs font-bold text-primary ring-1 ring-border">
                      {i + 1}
                    </span>
                  </div>
                  <h3 className="mt-5 text-lg font-semibold">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {description}
                  </p>
                </Reveal>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- Pricing ---------------- */}
      <section className="mx-auto w-full max-w-5xl px-6 py-24 sm:py-28">
        <Reveal className="mx-auto max-w-2xl text-center">
          <Eyebrow>Pricing</Eyebrow>
          <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
            Two simple plans
          </h2>
          <p className="mt-4 text-muted-foreground">
            No confusing tiers. Your plan is assigned by our team when your
            account is created.
          </p>
        </Reveal>

        <div className="mx-auto mt-16 grid max-w-3xl items-stretch gap-6 md:grid-cols-2">
          {/* Standard */}
          <Reveal className="h-full">
            <div className="flex h-full flex-col rounded-3xl border bg-card p-8 shadow-soft">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Standard
              </p>
              <p className="mt-2 text-2xl font-bold tracking-tight">
                The core toolkit
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Everything you need to audit, research, and optimize.
              </p>
              <ul className="mt-7 space-y-3.5 text-sm">
                {STANDARD_FEATURES.map((f) => (
                  <li key={f} className="flex items-start gap-3">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10">
                      <Check className="h-3 w-3 text-primary" />
                    </span>
                    <span>{f}</span>
                  </li>
                ))}
                {PREMIUM_ONLY.map((f) => (
                  <li
                    key={f}
                    className="flex items-start gap-3 text-muted-foreground/60"
                  >
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted">
                      <Lock className="h-3 w-3" />
                    </span>
                    <span className="line-through decoration-muted-foreground/30">
                      {f}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>

          {/* Premium */}
          <Reveal delay={0.08} className="relative h-full">
            {/* glow (slowly pulsing) */}
            <div
              aria-hidden
              className="absolute -inset-1 animate-glow rounded-[1.9rem] bg-gradient-to-br from-indigo-500/30 to-violet-500/30 blur-2xl"
            />
            <div className="relative h-full rounded-3xl bg-gradient-to-br from-indigo-500 to-violet-600 p-[1.5px] shadow-card">
              <div className="relative flex h-full flex-col rounded-[calc(1.5rem-1.5px)] bg-card p-8">
                <span className="absolute -top-3.5 left-8 inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-indigo-500 to-violet-600 px-3 py-1 text-xs font-semibold text-white shadow">
                  <Sparkles className="h-3 w-3" />
                  Everything unlocked
                </span>
                <p className="text-xs font-semibold uppercase tracking-wider text-primary">
                  Premium
                </p>
                <p className="mt-2 text-2xl font-bold tracking-tight">
                  The full platform
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Standard, plus growth &amp; agency power tools.
                </p>
                <ul className="mt-7 space-y-3.5 text-sm">
                  <li className="flex items-start gap-3">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10">
                      <Check className="h-3 w-3 text-primary" />
                    </span>
                    <span className="font-medium">Everything in Standard</span>
                  </li>
                  {PREMIUM_ONLY.map((f) => {
                    const Icon = f.startsWith("Backlink")
                      ? Link2
                      : f.startsWith("Automation")
                        ? Settings
                        : Sparkles;
                    return (
                      <li key={f} className="flex items-start gap-3">
                        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-500">
                          <Icon className="h-3 w-3 text-white" />
                        </span>
                        <span>{f}</span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ---------------- CTA ---------------- */}
      <section className="mx-auto w-full max-w-6xl px-6 pb-24 sm:pb-28">
        <Reveal>
          <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-600 via-indigo-600 to-violet-600 px-8 py-16 text-center shadow-card sm:px-12">
            <div
              aria-hidden
              className="pointer-events-none absolute -left-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-3xl"
            />
            <div
              aria-hidden
              className="pointer-events-none absolute -bottom-20 -right-10 h-64 w-64 rounded-full bg-violet-300/20 blur-3xl"
            />
            <div className="relative">
              <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
                Ready to climb the rankings?
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-indigo-100">
                RankPilot AI is invite-only. Tell us about your site and our
                team will set you up with the right plan.
              </p>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                <Button
                  asChild
                  size="lg"
                  className="group bg-white text-indigo-700 hover:bg-white/90"
                >
                  <Link href="/contact">
                    Contact us for access
                    <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
                  </Link>
                </Button>
                <Button
                  asChild
                  size="lg"
                  variant="outline"
                  className="border-white/40 bg-transparent text-white hover:bg-white/10 hover:text-white"
                >
                  <Link href="/login">Sign in</Link>
                </Button>
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      {/* ---------------- Footer ---------------- */}
      <footer className="border-t bg-muted/20">
        <div className="mx-auto grid w-full max-w-6xl gap-8 px-6 py-12 sm:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-2 text-lg font-bold">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
                <Sparkles className="h-4 w-4 text-primary-foreground" />
              </span>
              RankPilot <span className="text-primary">AI</span>
            </div>
            <p className="mt-3 max-w-xs text-sm text-muted-foreground">
              An AI copilot for SEO — audits, Core Web Vitals fixes, keyword
              research, and content, all in one dashboard.
            </p>
          </div>
          <div>
            <p className="text-sm font-semibold">Product</p>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li>
                <Link href="/login" className="hover:text-foreground">
                  Sign in
                </Link>
              </li>
              <li>
                <Link href="/contact" className="hover:text-foreground">
                  Request access
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <p className="text-sm font-semibold">Company</p>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li>
                <Link href="/contact" className="hover:text-foreground">
                  Contact us
                </Link>
              </li>
              <li>
                <Link
                  href="/privacy-policy"
                  className="hover:text-foreground"
                >
                  Privacy Policy
                </Link>
              </li>
            </ul>
          </div>
        </div>
        <div className="border-t">
          <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-2 px-6 py-6 text-xs text-muted-foreground sm:flex-row">
            <span>
              © {new Date().getFullYear()} RankPilot AI. All rights reserved.
            </span>
            <span>Invite-only · AI-powered SEO</span>
          </div>
        </div>
      </footer>
    </main>
  );
}

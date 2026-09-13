import Link from "next/link";
import { Sparkles } from "lucide-react";

export const metadata = {
  title: "Privacy Policy · RankPilot AI",
  description:
    "How RankPilot AI collects, uses, and protects your data, including Google user data accessed via the Gmail API.",
};

// Last updated — bump this whenever the policy content changes.
const LAST_UPDATED = "September 13, 2026";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-xl font-semibold text-foreground">{title}</h2>
      <div className="space-y-3 text-sm leading-relaxed text-muted-foreground">
        {children}
      </div>
    </section>
  );
}

export default function PrivacyPolicyPage() {
  return (
    <main className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-muted/20">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2 text-lg font-bold">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Sparkles className="h-4 w-4 text-primary-foreground" />
            </span>
            RankPilot <span className="text-primary">AI</span>
          </Link>
          <Link
            href="/"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Back to home
          </Link>
        </div>
      </header>

      <div className="mx-auto w-full max-w-3xl space-y-10 px-6 py-12">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">Privacy Policy</h1>
          <p className="text-sm text-muted-foreground">
            Last updated: {LAST_UPDATED}
          </p>
        </div>

        <p className="text-sm leading-relaxed text-muted-foreground">
          RankPilot AI (&ldquo;RankPilot,&rdquo; &ldquo;we,&rdquo;
          &ldquo;us,&rdquo; or &ldquo;our&rdquo;) provides an AI-powered SEO
          platform for site audits, Core Web Vitals fixes, keyword research,
          rank tracking, and content optimization. This Privacy Policy explains
          what information we collect, how we use it, and the choices you have.
          By using RankPilot AI you agree to the practices described here.
        </p>

        <Section title="Information we collect">
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong className="text-foreground">Account information.</strong>{" "}
              Your name, email address, and password (stored only as a salted
              hash). RankPilot AI is invite-only, so accounts are created for
              you by an administrator.
            </li>
            <li>
              <strong className="text-foreground">Project data.</strong> The
              websites, URLs, keywords, and connected platforms (e.g. WordPress
              or Shopify stores) you add so we can run audits and apply fixes.
            </li>
            <li>
              <strong className="text-foreground">
                Connected-platform credentials.
              </strong>{" "}
              Access tokens for platforms you connect, stored encrypted at rest
              and used solely to read and apply the SEO changes you request.
            </li>
            <li>
              <strong className="text-foreground">Usage data.</strong> Basic
              logs (timestamps, request paths, error information) used to
              operate and secure the service.
            </li>
          </ul>
        </Section>

        <Section title="Google user data (Gmail API)">
          <p>
            RankPilot AI uses the Gmail API strictly to{" "}
            <strong className="text-foreground">send</strong> transactional and
            notification emails from a designated sender account — for example,
            new-account welcome messages and automation reports. We request only
            the{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
              https://www.googleapis.com/auth/gmail.send
            </code>{" "}
            scope.
          </p>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              We use the granted access <strong className="text-foreground">only
              to send email</strong> on behalf of the connected account. We do
              not read, delete, or modify messages in the mailbox.
            </li>
            <li>
              We do not sell, rent, or share Google user data with third
              parties, and we do not use it for advertising.
            </li>
            <li>
              We do not use Google user data to develop, improve, or train
              generalized artificial-intelligence or machine-learning models.
            </li>
            <li>
              The stored OAuth refresh token is used only to obtain short-lived
              access tokens for sending, and can be revoked by you at any time
              from your{" "}
              <a
                href="https://myaccount.google.com/permissions"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                Google Account permissions
              </a>
              .
            </li>
          </ul>
          <p>
            RankPilot AI&apos;s use of information received from Google APIs
            adheres to the{" "}
            <a
              href="https://developers.google.com/terms/api-services-user-data-policy"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Google API Services User Data Policy
            </a>
            , including the Limited Use requirements.
          </p>
        </Section>

        <Section title="How we use information">
          <ul className="list-disc space-y-2 pl-5">
            <li>To provide, maintain, and secure the RankPilot AI service.</li>
            <li>
              To run SEO audits and analyses, and to apply the fixes you
              explicitly request on your connected platforms.
            </li>
            <li>
              To send account, security, and automation-report emails you have
              opted into.
            </li>
            <li>
              To diagnose problems, prevent abuse, and comply with legal
              obligations.
            </li>
          </ul>
        </Section>

        <Section title="Third-party services">
          <p>
            We rely on trusted providers to operate the service, and share only
            the data needed for each to function:
          </p>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong className="text-foreground">Google (Gmail API)</strong> —
              sending outbound email.
            </li>
            <li>
              <strong className="text-foreground">OpenAI</strong> — generating
              SEO recommendations and content. Project text may be sent to the
              model to produce results.
            </li>
            <li>
              <strong className="text-foreground">
                SEO data providers (e.g. PageSpeed Insights, SerpApi)
              </strong>{" "}
              — retrieving performance metrics and search-ranking data for the
              URLs and keywords you add.
            </li>
            <li>
              <strong className="text-foreground">
                Hosting &amp; infrastructure (Vercel, Hugging Face, Neon)
              </strong>{" "}
              — running the application and storing your data.
            </li>
          </ul>
        </Section>

        <Section title="Data retention & security">
          <p>
            We retain your data for as long as your account is active or as
            needed to provide the service. Credentials and access tokens are
            encrypted at rest, passwords are stored only as salted hashes, and
            all traffic is served over HTTPS. You can request deletion of your
            account and associated data at any time.
          </p>
        </Section>

        <Section title="Your choices">
          <ul className="list-disc space-y-2 pl-5">
            <li>
              Disconnect a connected platform or revoke Gmail access at any time
              to stop further processing.
            </li>
            <li>
              Request access to, correction of, or deletion of your personal
              data by contacting us.
            </li>
            <li>Adjust or disable automation emails from your dashboard.</li>
          </ul>
        </Section>

        <Section title="Changes to this policy">
          <p>
            We may update this Privacy Policy from time to time. Material
            changes will be reflected by updating the &ldquo;Last updated&rdquo;
            date above, and where appropriate we will notify you.
          </p>
        </Section>

        <Section title="Contact us">
          <p>
            If you have questions about this Privacy Policy or your data, reach
            us through our{" "}
            <Link href="/contact" className="text-primary hover:underline">
              contact page
            </Link>
            .
          </p>
        </Section>

        <div className="border-t pt-6 text-xs text-muted-foreground">
          © {new Date().getFullYear()} RankPilot AI. All rights reserved.
        </div>
      </div>
    </main>
  );
}

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "RankPilot Admin",
  // Never index the admin area.
  robots: { index: false, follow: false },
};

// Distinct shell for the isolated admin area — no shared user dashboard nav.
// `theme-admin` re-skins the shared design system to a VIOLET accent so admin
// mode is instantly distinguishable from the (indigo) user dashboard.
export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="theme-admin min-h-screen bg-muted/30">{children}</div>;
}

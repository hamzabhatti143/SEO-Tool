"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from "@/lib/api";

export default function AcceptInvitePage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const router = useRouter();
  const { status } = useSession();

  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [done, setDone] = React.useState(false);

  async function accept() {
    setBusy(true);
    setError(null);
    try {
      await api.acceptInvite(token);
      setDone(true);
      setTimeout(() => router.push("/dashboard"), 1200);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not accept invite");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Team invitation</CardTitle>
          <CardDescription>
            You&apos;ve been invited to collaborate on a RankPilot AI project.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {status === "loading" && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}

          {status === "unauthenticated" && (
            <>
              <p className="text-sm text-muted-foreground">
                Sign in or create an account to accept this invitation.
              </p>
              <Button asChild className="w-full">
                <Link href={`/login?callbackUrl=/invite/${token}`}>
                  Sign in to accept
                </Link>
              </Button>
            </>
          )}

          {status === "authenticated" && !done && (
            <>
              <Button onClick={accept} disabled={busy} className="w-full">
                {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Accept invitation
              </Button>
              {error && <p className="text-sm text-destructive">{error}</p>}
            </>
          )}

          {done && (
            <p className="text-sm text-emerald-600">
              Invitation accepted! Redirecting to your dashboard…
            </p>
          )}
        </CardContent>
      </Card>
    </main>
  );
}

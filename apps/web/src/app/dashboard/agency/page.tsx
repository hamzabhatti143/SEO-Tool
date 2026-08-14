"use client";

import * as React from "react";
import { useSession } from "next-auth/react";
import { Copy, Loader2, Plus, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useProject } from "@/components/project-provider";
import {
  api,
  type AgencyRole,
  type Invite,
  type Member,
  type ShareLink,
} from "@/lib/api";

const ROLES: AgencyRole[] = ["admin", "editor", "viewer"];

export default function AgencyPage() {
  const { currentProject } = useProject();
  const { data: session } = useSession();
  const isAgency = session?.user?.tier === "agency";

  if (!isAgency) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <CardHeader>
            <CardTitle>Agency Mode</CardTitle>
            <CardDescription>
              Team members, client share links, and white-label branding are
              available on the <strong>Agency</strong> plan.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Upgrade to Agency to invite teammates with roles, share read-only
              report links with clients, and apply your own branding.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Agency Mode</h1>
        <p className="text-muted-foreground">
          Manage your team and client access for {currentProject?.name}.
        </p>
      </header>
      {currentProject && (
        <>
          <TeamCard projectId={currentProject.id} />
          <ShareLinksCard projectId={currentProject.id} />
        </>
      )}
    </div>
  );
}

function TeamCard({ projectId }: { projectId: string }) {
  const [members, setMembers] = React.useState<Member[]>([]);
  const [invites, setInvites] = React.useState<Invite[]>([]);
  const [email, setEmail] = React.useState("");
  const [role, setRole] = React.useState<AgencyRole>("viewer");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setError(null);
    try {
      const [m, i] = await Promise.all([
        api.listMembers(projectId),
        api.listInvites(projectId),
      ]);
      setMembers(m);
      setInvites(i);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load team");
    }
  }, [projectId]);

  React.useEffect(() => {
    load();
  }, [load]);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    setBusy(true);
    setError(null);
    try {
      await api.createInvite(projectId, { email, role });
      setEmail("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invite failed");
    } finally {
      setBusy(false);
    }
  }

  async function changeRole(memberId: string, r: AgencyRole) {
    await api.updateMemberRole(projectId, memberId, r);
    await load();
  }
  async function remove(memberId: string) {
    await api.removeMember(projectId, memberId);
    await load();
  }

  function copyInvite(token: string) {
    navigator.clipboard.writeText(
      `${window.location.origin}/invite/${token}`
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Team members</CardTitle>
        <CardDescription>Invite teammates with a role.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={invite} className="flex flex-wrap items-end gap-3">
          <div className="flex-1 space-y-1">
            <Label htmlFor="email" className="text-xs">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              placeholder="teammate@agency.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Role</Label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as AgencyRole)}
              className="h-10 rounded-md border border-input bg-background px-2 text-sm"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <Button type="submit" disabled={busy}>
            {busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Plus className="mr-2 h-4 w-4" />
            )}
            Invite
          </Button>
        </form>
        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="space-y-2">
          {members.map((m) => (
            <div
              key={m.id}
              className="flex items-center justify-between rounded-md border p-2 text-sm"
            >
              <span>{m.email}</span>
              <div className="flex items-center gap-2">
                <select
                  value={m.role}
                  onChange={(e) =>
                    changeRole(m.id, e.target.value as AgencyRole)
                  }
                  className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => remove(m.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
          {members.length === 0 && (
            <p className="text-sm text-muted-foreground">No members yet.</p>
          )}
        </div>

        {invites.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase text-muted-foreground">
              Pending invites
            </p>
            {invites.map((i) => (
              <div
                key={i.id}
                className="flex items-center justify-between rounded-md border border-dashed p-2 text-sm"
              >
                <span>
                  {i.email} <Badge variant="secondary">{i.role}</Badge>
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyInvite(i.token)}
                >
                  <Copy className="mr-1 h-3 w-3" />
                  Copy invite link
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ShareLinksCard({ projectId }: { projectId: string }) {
  const [links, setLinks] = React.useState<ShareLink[]>([]);
  const [label, setLabel] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    setLinks(await api.listShareLinks(projectId));
  }, [projectId]);

  React.useEffect(() => {
    load();
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.createShareLink(projectId, label || undefined);
      setLabel("");
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    await api.revokeShareLink(projectId, id);
    await load();
  }

  function copy(token: string) {
    navigator.clipboard.writeText(`${window.location.origin}/share/${token}`);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Client access (share links)</CardTitle>
        <CardDescription>
          Read-only report links clients can open without logging in.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={create} className="flex items-end gap-3">
          <div className="flex-1 space-y-1">
            <Label htmlFor="label" className="text-xs">
              Label (optional)
            </Label>
            <Input
              id="label"
              placeholder="Acme Corp"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={busy}>
            {busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Plus className="mr-2 h-4 w-4" />
            )}
            Create link
          </Button>
        </form>

        <div className="space-y-2">
          {links.map((l) => (
            <div
              key={l.id}
              className="flex items-center justify-between rounded-md border p-2 text-sm"
            >
              <span className={l.revoked ? "text-muted-foreground line-through" : ""}>
                {l.label || "Client link"}
              </span>
              <div className="flex items-center gap-2">
                {l.revoked ? (
                  <Badge variant="destructive">revoked</Badge>
                ) : (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => copy(l.token)}
                    >
                      <Copy className="mr-1 h-3 w-3" />
                      Copy link
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => revoke(l.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </>
                )}
              </div>
            </div>
          ))}
          {links.length === 0 && (
            <p className="text-sm text-muted-foreground">No share links yet.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

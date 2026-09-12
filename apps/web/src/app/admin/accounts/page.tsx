"use client";

import * as React from "react";
import { Loader2, Plus, Search, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DataTable, type Column } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Stagger, StaggerItem } from "@/components/motion";
import { AdminShell } from "@/components/admin/admin-shell";
import { Modal } from "@/components/admin/modal";
import {
  AdminAuthError,
  adminApi,
  type Account,
  type AccountCreateResponse,
  type AdminStats,
  type Tier,
} from "@/lib/admin-api";
import { useRouter } from "next/navigation";

export default function AdminAccountsPage() {
  return (
    <AdminShell>
      <AccountsDashboard />
    </AdminShell>
  );
}

function AccountsDashboard() {
  const router = useRouter();
  const [accounts, setAccounts] = React.useState<Account[]>([]);
  const [stats, setStats] = React.useState<AdminStats | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [busyId, setBusyId] = React.useState<string | null>(null);

  const [search, setSearch] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [tierFilter, setTierFilter] = React.useState("all");

  const [createOpen, setCreateOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Account | null>(null);

  const handleError = React.useCallback(
    (e: unknown) => {
      if (e instanceof AdminAuthError) {
        router.replace("/admin/login");
        return;
      }
      setError(e instanceof Error ? e.message : "Something went wrong.");
    },
    [router]
  );

  const load = React.useCallback(async () => {
    setError(null);
    try {
      const [accts, s] = await Promise.all([
        adminApi.listAccounts(),
        adminApi.stats(),
      ]);
      setAccounts(accts);
      setStats(s);
    } catch (e) {
      handleError(e);
    } finally {
      setLoading(false);
    }
  }, [handleError]);

  React.useEffect(() => {
    load();
  }, [load]);

  async function toggleStatus(a: Account) {
    setBusyId(a.id);
    try {
      await adminApi.setStatus(
        a.id,
        a.status === "active" ? "suspended" : "active"
      );
      await load();
    } catch (e) {
      handleError(e);
    } finally {
      setBusyId(null);
    }
  }

  async function changePlan(a: Account) {
    const next: Tier = a.plan === "premium" ? "standard" : "premium";
    setBusyId(a.id);
    try {
      await adminApi.updateAccount(a.id, { plan: next });
      await load();
    } catch (e) {
      handleError(e);
    } finally {
      setBusyId(null);
    }
  }

  async function remove(a: Account) {
    if (
      !window.confirm(
        `Delete ${a.email}? This permanently removes the account and all of their projects and data.`
      )
    ) {
      return;
    }
    setBusyId(a.id);
    try {
      await adminApi.deleteAccount(a.id);
      await load();
    } catch (e) {
      handleError(e);
    } finally {
      setBusyId(null);
    }
  }

  const filtered = accounts.filter((a) => {
    const q = search.trim().toLowerCase();
    const matchesSearch =
      !q ||
      a.email.toLowerCase().includes(q) ||
      (a.full_name ?? "").toLowerCase().includes(q);
    const matchesStatus =
      statusFilter === "all" || a.status === statusFilter;
    const matchesTier = tierFilter === "all" || a.plan === tierFilter;
    return matchesSearch && matchesStatus && matchesTier;
  });

  const columns: Column<Account>[] = [
    {
      key: "email",
      header: "Email",
      cell: (a) => <span className="font-medium">{a.email}</span>,
      sortValue: (a) => a.email.toLowerCase(),
    },
    {
      key: "name",
      header: "Name",
      cell: (a) => (
        <span className="text-muted-foreground">{a.full_name ?? "—"}</span>
      ),
      sortValue: (a) => (a.full_name ?? "").toLowerCase(),
    },
    {
      key: "plan",
      header: "Tier",
      cell: (a) => (
        <Badge variant={a.plan === "premium" ? "default" : "secondary"}>
          {a.plan}
        </Badge>
      ),
      sortValue: (a) => a.plan,
    },
    {
      key: "status",
      header: "Status",
      cell: (a) => (
        <Badge variant={a.status === "active" ? "success" : "destructive"}>
          {a.status}
        </Badge>
      ),
      sortValue: (a) => a.status,
    },
    {
      key: "project_count",
      header: "Projects",
      cell: (a) => a.project_count,
      sortValue: (a) => a.project_count,
      align: "right",
    },
    {
      key: "created_at",
      header: "Created",
      cell: (a) => (
        <span className="text-muted-foreground">
          {new Date(a.created_at).toLocaleDateString()}
        </span>
      ),
      sortValue: (a) => a.created_at,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      cell: (a) => (
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={busyId === a.id}
            onClick={() => setEditing(a)}
          >
            Edit
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={busyId === a.id}
            onClick={() => changePlan(a)}
          >
            {a.plan === "premium" ? "Downgrade" : "Upgrade"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={busyId === a.id}
            onClick={() => toggleStatus(a)}
          >
            {a.status === "active" ? "Suspend" : "Reactivate"}
          </Button>
          <Button
            variant="destructive"
            size="sm"
            disabled={busyId === a.id}
            onClick={() => remove(a)}
          >
            Delete
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Accounts"
        description="Manage user accounts, subscription tiers, and access."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create Account
          </Button>
        }
      />

      {/* Stats */}
      <Stagger className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StaggerItem>
          <StatCard label="Total accounts" value={stats?.total ?? "—"} />
        </StaggerItem>
        <StaggerItem>
          <StatCard
            label="Standard / Premium"
            value={stats ? `${stats.standard} / ${stats.premium}` : "—"}
          />
        </StaggerItem>
        <StaggerItem>
          <StatCard label="Active" value={stats?.active ?? "—"} />
        </StaggerItem>
        <StaggerItem>
          <StatCard label="Suspended" value={stats?.suspended ?? "—"} />
        </StaggerItem>
      </Stagger>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search by email or name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <FilterSelect
          value={statusFilter}
          onChange={setStatusFilter}
          options={[
            ["all", "All statuses"],
            ["active", "Active"],
            ["suspended", "Suspended"],
          ]}
        />
        <FilterSelect
          value={tierFilter}
          onChange={setTierFilter}
          options={[
            ["all", "All tiers"],
            ["standard", "Standard"],
            ["premium", "Premium"],
          ]}
        />
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <Card>
          <CardContent className="flex items-center justify-center py-16 text-muted-foreground">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading…
          </CardContent>
        </Card>
      ) : (
        <DataTable
          columns={columns}
          rows={filtered}
          getRowKey={(a) => a.id}
          pageSize={10}
          initialSort={{ key: "created_at", dir: "desc" }}
          emptyState={
            <EmptyState
              icon={Users}
              title={
                accounts.length === 0
                  ? "No accounts yet"
                  : "No accounts match your filters"
              }
              description={
                accounts.length === 0
                  ? "Create the first account to get started."
                  : "Try adjusting your search or filters."
              }
              action={
                accounts.length === 0 ? (
                  <Button onClick={() => setCreateOpen(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Create Account
                  </Button>
                ) : undefined
              }
            />
          }
        />
      )}

      <CreateAccountModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={load}
        onError={handleError}
      />
      <EditAccountModal
        account={editing}
        onClose={() => setEditing(null)}
        onSaved={load}
        onError={handleError}
      />
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs uppercase text-muted-foreground">{label}</p>
        <p className="mt-1 text-2xl font-bold">{value}</p>
      </CardContent>
    </Card>
  );
}

function FilterSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-10 rounded-md border border-input bg-background px-3 text-sm"
    >
      {options.map(([v, label]) => (
        <option key={v} value={v}>
          {label}
        </option>
      ))}
    </select>
  );
}

function TierSelect({
  value,
  onChange,
  id,
}: {
  value: Tier;
  onChange: (v: Tier) => void;
  id?: string;
}) {
  return (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value as Tier)}
      className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
    >
      <option value="standard">Standard</option>
      <option value="premium">Premium</option>
    </select>
  );
}

function CreateAccountModal({
  open,
  onClose,
  onCreated,
  onError,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => Promise<void> | void;
  onError: (e: unknown) => void;
}) {
  const [email, setEmail] = React.useState("");
  const [fullName, setFullName] = React.useState("");
  const [plan, setPlan] = React.useState<Tier>("standard");
  const [password, setPassword] = React.useState("");
  const [sendEmail, setSendEmail] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [result, setResult] = React.useState<AccountCreateResponse | null>(
    null
  );

  function reset() {
    setEmail("");
    setFullName("");
    setPlan("standard");
    setPassword("");
    setSendEmail(true);
    setResult(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await adminApi.createAccount({
        email,
        full_name: fullName || null,
        plan,
        password: password.trim() || undefined,
        send_email: sendEmail,
      });
      setResult(res);
      await onCreated();
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title="Create account"
      description="Set a password, or leave it blank to auto-generate a temporary one the user must change on first login."
    >
      {result ? (
        <div className="space-y-4">
          <p className="text-sm">
            Account created for <strong>{result.account.email}</strong>.
          </p>
          <div className="rounded-md border bg-muted/40 p-3">
            <p className="text-xs uppercase text-muted-foreground">Password</p>
            <code className="text-lg tracking-wide">
              {result.temporary_password}
            </code>
          </div>
          <p className="text-xs text-muted-foreground">
            {result.emailed
              ? "The credentials were emailed to the user. Share the password securely as a backup."
              : "Email was not sent — share this password with the user securely."}
          </p>
          <Button
            className="w-full"
            onClick={() => {
              reset();
              onClose();
            }}
          >
            Done
          </Button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="c-email">Email</Label>
            <Input
              id="c-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="c-name">Full name</Label>
            <Input
              id="c-name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Jane Doe"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="c-plan">Subscription tier</Label>
            <TierSelect id="c-plan" value={plan} onChange={setPlan} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="c-password">Password</Label>
            <Input
              id="c-password"
              type="text"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Leave blank to auto-generate"
              minLength={8}
              autoComplete="new-password"
            />
            <p className="text-xs text-muted-foreground">
              Optional. If blank, a temporary password is generated and the
              user must change it on first login.
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={sendEmail}
              onChange={(e) => setSendEmail(e.target.checked)}
            />
            Email the password to the user
          </label>
          <Button type="submit" className="w-full" disabled={busy}>
            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create account
          </Button>
        </form>
      )}
    </Modal>
  );
}

function EditAccountModal({
  account,
  onClose,
  onSaved,
  onError,
}: {
  account: Account | null;
  onClose: () => void;
  onSaved: () => Promise<void> | void;
  onError: (e: unknown) => void;
}) {
  const [fullName, setFullName] = React.useState("");
  const [plan, setPlan] = React.useState<Tier>("standard");
  const [password, setPassword] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (account) {
      setFullName(account.full_name ?? "");
      setPlan(account.plan);
      setPassword("");
    }
  }, [account]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!account) return;
    setBusy(true);
    try {
      await adminApi.updateAccount(account.id, {
        full_name: fullName || null,
        plan,
        password: password.trim() || undefined,
      });
      await onSaved();
      onClose();
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={account !== null}
      onClose={onClose}
      title="Edit account"
      description={account?.email}
    >
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="e-name">Full name</Label>
          <Input
            id="e-name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="e-plan">Subscription tier</Label>
          <TierSelect id="e-plan" value={plan} onChange={setPlan} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="e-password">New password</Label>
          <Input
            id="e-password"
            type="text"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Leave blank to keep current"
            minLength={8}
            autoComplete="new-password"
          />
          <p className="text-xs text-muted-foreground">
            Optional. Sets a new password for this user immediately.
          </p>
        </div>
        <Button type="submit" className="w-full" disabled={busy}>
          {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save changes
        </Button>
      </form>
    </Modal>
  );
}

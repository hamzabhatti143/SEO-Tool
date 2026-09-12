"use client";

import * as React from "react";
import { Check, ChevronsUpDown, FolderPlus, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dropdown, DropdownItem } from "@/components/ui/dropdown";
import { Modal } from "@/components/admin/modal";
import { useProject } from "@/components/project-provider";

/** Top-bar control to switch the active project or create a new one. */
export function ProjectSelector() {
  const { projects, currentProject, selectProject, createProject } =
    useProject();
  const [createOpen, setCreateOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const [domain, setDomain] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name || !domain) return;
    setBusy(true);
    setError(null);
    try {
      await createProject(name, domain);
      setName("");
      setDomain("");
      setCreateOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create project");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Dropdown
        align="start"
        trigger={({ toggle, open }) => (
          <button
            type="button"
            onClick={toggle}
            className="flex h-9 max-w-[15rem] items-center gap-2 rounded-lg border bg-background px-3 text-sm font-medium transition-colors hover:bg-accent"
          >
            <span className="truncate">
              {currentProject?.name ?? "Select project"}
            </span>
            <ChevronsUpDown
              className={cn(
                "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                open && "rotate-180"
              )}
            />
          </button>
        )}
      >
        {({ close }) => (
          <div className="min-w-[16rem]">
            <p className="px-2.5 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Projects
            </p>
            <div className="max-h-64 overflow-y-auto">
              {projects.length === 0 && (
                <p className="px-2.5 py-2 text-sm text-muted-foreground">
                  No projects yet.
                </p>
              )}
              {projects.map((p) => (
                <DropdownItem
                  key={p.id}
                  onClick={() => {
                    selectProject(p.id);
                    close();
                  }}
                >
                  <Check
                    className={cn(
                      "h-4 w-4",
                      p.id === currentProject?.id
                        ? "opacity-100 text-primary"
                        : "opacity-0"
                    )}
                  />
                  <span className="flex-1 truncate">{p.name}</span>
                  <span className="truncate text-xs text-muted-foreground">
                    {p.domain}
                  </span>
                </DropdownItem>
              ))}
            </div>
            <div className="my-1 border-t" />
            <DropdownItem
              onClick={() => {
                close();
                setCreateOpen(true);
              }}
            >
              <FolderPlus className="h-4 w-4" />
              New project
            </DropdownItem>
          </div>
        )}
      </Dropdown>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create project"
        description="Add a website you want to optimize."
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="p-name">Project name</Label>
            <Input
              id="p-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Acme Marketing"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="p-domain">Domain</Label>
            <Input
              id="p-domain"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="example.com"
              required
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={busy}>
            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create project
          </Button>
        </form>
      </Modal>
    </>
  );
}

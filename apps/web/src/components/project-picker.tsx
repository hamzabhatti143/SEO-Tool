"use client";

import * as React from "react";
import { FolderPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useProject } from "@/components/project-provider";

/** Sidebar control to switch between projects or create a new one. */
export function ProjectPicker() {
  const { projects, currentProject, selectProject, createProject } =
    useProject();
  const [creating, setCreating] = React.useState(false);
  const [name, setName] = React.useState("");
  const [domain, setDomain] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name || !domain) return;
    setBusy(true);
    try {
      await createProject(name, domain);
      setName("");
      setDomain("");
      setCreating(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <label className="px-2 text-xs font-medium uppercase text-muted-foreground">
        Project
      </label>
      {projects.length > 0 && (
        <select
          value={currentProject?.id ?? ""}
          onChange={(e) => selectProject(e.target.value)}
          className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      )}

      {creating ? (
        <form onSubmit={handleCreate} className="space-y-2">
          <Input
            placeholder="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input
            placeholder="example.com"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
          />
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={busy} className="flex-1">
              {busy ? "Creating…" : "Create"}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setCreating(false)}
            >
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <Button
          variant="outline"
          size="sm"
          className="w-full justify-start"
          onClick={() => setCreating(true)}
        >
          <FolderPlus className="mr-2 h-4 w-4" />
          New project
        </Button>
      )}
    </div>
  );
}

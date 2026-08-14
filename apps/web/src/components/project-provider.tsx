"use client";

import * as React from "react";
import { useSession } from "next-auth/react";

import { api, type Project } from "@/lib/api";

interface ProjectContextValue {
  projects: Project[];
  currentProject: Project | null;
  loading: boolean;
  error: string | null;
  selectProject: (id: string) => void;
  createProject: (name: string, domain: string) => Promise<void>;
}

const ProjectContext = React.createContext<ProjectContextValue | null>(null);

const STORAGE_KEY = "rankpilot.currentProjectId";

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const { status } = useSession();
  const [projects, setProjects] = React.useState<Project[]>([]);
  const [currentId, setCurrentId] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (status !== "authenticated") return;
    (async () => {
      try {
        const list = await api.listProjects();
        setProjects(list);
        const stored =
          typeof window !== "undefined"
            ? window.localStorage.getItem(STORAGE_KEY)
            : null;
        const initial =
          list.find((p) => p.id === stored)?.id ?? list[0]?.id ?? null;
        setCurrentId(initial);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load workspace");
      } finally {
        setLoading(false);
      }
    })();
  }, [status]);

  const selectProject = React.useCallback((id: string) => {
    setCurrentId(id);
    window.localStorage.setItem(STORAGE_KEY, id);
  }, []);

  const createProject = React.useCallback(
    async (name: string, domain: string) => {
      const project = await api.createProject({ name, domain });
      setProjects((prev) => [project, ...prev]);
      selectProject(project.id);
    },
    [selectProject]
  );

  const currentProject =
    projects.find((p) => p.id === currentId) ?? null;

  const value: ProjectContextValue = {
    projects,
    currentProject,
    loading,
    error,
    selectProject,
    createProject,
  };

  return (
    <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
  );
}

export function useProject() {
  const ctx = React.useContext(ProjectContext);
  if (!ctx) {
    throw new Error("useProject must be used within a ProjectProvider");
  }
  return ctx;
}

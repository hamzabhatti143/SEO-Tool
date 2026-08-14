import { AssistantWidget } from "@/components/assistant-widget";
import { ProjectProvider } from "@/components/project-provider";
import { Sidebar } from "@/components/sidebar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProjectProvider>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-8">{children}</main>
      </div>
      <AssistantWidget />
    </ProjectProvider>
  );
}

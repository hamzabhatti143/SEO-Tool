import { AssistantWidget } from "@/components/assistant-widget";
import { DashboardChrome } from "@/components/dashboard-chrome";
import { ProjectProvider } from "@/components/project-provider";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProjectProvider>
      <DashboardChrome>{children}</DashboardChrome>
      <AssistantWidget />
    </ProjectProvider>
  );
}

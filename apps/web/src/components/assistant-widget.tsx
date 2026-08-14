"use client";

import * as React from "react";
import {
  Bot,
  Loader2,
  MessageCircle,
  Send,
  Sparkles,
  Wrench,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useProject } from "@/components/project-provider";
import { api, type AssistantMessage } from "@/lib/api";

const SUGGESTIONS = [
  "Why is my page not ranking?",
  "Summarize my latest audit",
  "What should I work on next?",
];

export function AssistantWidget() {
  const { currentProject } = useProject();
  const [open, setOpen] = React.useState(false);
  const [messages, setMessages] = React.useState<AssistantMessage[]>([]);
  const [input, setInput] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [tool, setTool] = React.useState<string | null>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, tool]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || busy || !currentProject) return;

    const userMsg: AssistantMessage = { role: "user", content: question };
    const apiMessages = [...messages, userMsg];
    setMessages([...apiMessages, { role: "assistant", content: "" }]);
    setInput("");
    setBusy(true);
    setTool(null);

    const appendToLast = (text: string) =>
      setMessages((prev) => {
        const copy = [...prev];
        const last = copy[copy.length - 1];
        copy[copy.length - 1] = { ...last, content: last.content + text };
        return copy;
      });

    await api.streamAssistantChat(
      { project_id: currentProject.id, messages: apiMessages },
      {
        onTool: (_name, label) => setTool(label),
        onToken: (t) => {
          setTool(null);
          appendToLast(t);
        },
        onDone: () => {
          setBusy(false);
          setTool(null);
        },
        onError: (detail) => {
          appendToLast(`\n\n⚠ ${detail}`);
          setBusy(false);
          setTool(null);
        },
      }
    );
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform hover:scale-105"
        aria-label="Open SEO Assistant"
      >
        <MessageCircle className="h-6 w-6" />
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex h-[560px] w-[380px] max-w-[calc(100vw-2rem)] flex-col rounded-xl border bg-card shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b p-3">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-primary" />
          <span className="font-semibold">SEO Assistant</span>
        </div>
        <button
          onClick={() => setOpen(false)}
          className="text-muted-foreground hover:text-foreground"
          aria-label="Close"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3">
        {messages.length === 0 && (
          <div className="space-y-3 text-sm text-muted-foreground">
            <p>
              Ask about {currentProject?.name ?? "your project"} — I&apos;ll pull
              your real audit, ranking, keyword, and content data to answer.
            </p>
            <div className="flex flex-col gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  disabled={!currentProject}
                  className="flex items-center gap-2 rounded-md border p-2 text-left text-foreground hover:bg-accent"
                >
                  <Sparkles className="h-4 w-4 text-primary" />
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={cn(
              "flex",
              m.role === "user" ? "justify-end" : "justify-start"
            )}
          >
            <div
              className={cn(
                "max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm",
                m.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted"
              )}
            >
              {m.content || (
                <span className="text-muted-foreground">…</span>
              )}
            </div>
          </div>
        ))}

        {tool && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Wrench className="h-3 w-3 animate-pulse" />
            {tool}…
          </div>
        )}
      </div>

      {/* Input */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex items-center gap-2 border-t p-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            currentProject ? "Ask about your SEO…" : "Select a project first"
          }
          disabled={busy || !currentProject}
          className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <Button type="submit" size="icon" disabled={busy || !currentProject}>
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </form>
    </div>
  );
}

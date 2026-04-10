"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Image from "next/image";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { X, Send, Loader2, Database, BarChart3, Search, GitCompare, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

// --- Types ---

interface ToolEvent {
  name: string;
  input: Record<string, unknown>;
  result?: Record<string, unknown>;
  done: boolean;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  tools?: ToolEvent[];
}

// --- Tool info ---

function toolLabel(name: string) {
  if (name === "query_database") return "Querying database";
  if (name === "analyze_anomaly") return "Analyzing anomaly";
  if (name === "compare_periods") return "Comparing periods";
  if (name === "web_search") return "Searching the web";
  return name;
}

function toolIcon(name: string) {
  if (name === "query_database") return <Database className="size-3.5" />;
  if (name === "analyze_anomaly") return <BarChart3 className="size-3.5" />;
  if (name === "compare_periods") return <GitCompare className="size-3.5" />;
  if (name === "web_search") return <Search className="size-3.5" />;
  return <Database className="size-3.5" />;
}

// --- Rappi avatar ---

function RappiAvatar() {
  return (
    <div className="shrink-0 rounded-full bg-white border shadow-sm flex items-center justify-center overflow-hidden size-7">
      <Image src="/rappi-avatar.png" alt="Rappi" width={28} height={28} className="object-contain p-0.5" />
    </div>
  );
}

// --- Trigger button for header ---

export function ChatTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-[#FC4C02] bg-transparent text-[#FC4C02] hover:bg-[#FC4C02]/10 transition-colors"
      title="Ask AI about the data"
    >
      <span className="text-sm font-bold">?</span>
    </button>
  );
}

// --- Suggested questions ---

const SUGGESTIONS = [
  "What hour has the highest store availability?",
  "Why do anomalies spike in the afternoon?",
  "Compare weekdays vs weekends",
  "What happens to stores overnight?",
];

// --- Main chat panel ---

export function ChatPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamPhase, setStreamPhase] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streaming, streamPhase]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 150);
  }, [open]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || streaming) return;

    const userMsg: Message = { role: "user", content: text.trim() };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setStreaming(true);
    setStreamPhase("thinking");

    const idx = newMessages.length;
    setMessages((prev) => [...prev, { role: "assistant", content: "", thinking: "", tools: [] }]);

    const update = (fn: (msg: Message) => Message) => {
      setMessages((prev) => {
        const updated = [...prev];
        updated[idx] = fn({ ...updated[idx] });
        return updated;
      });
    };

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: newMessages.map((m) => ({ role: m.role, content: m.content })),
        }),
      });

      if (!res.ok || !res.body) throw new Error("Chat request failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          let data;
          try { data = JSON.parse(line.slice(6)); } catch { continue; }

          if (data.type === "thinking_start") {
            setStreamPhase("thinking");
          } else if (data.type === "thinking") {
            update((m) => ({ ...m, thinking: (m.thinking ?? "") + data.content }));
          } else if (data.type === "thinking_end") {
            setStreamPhase("");
          } else if (data.type === "tool_start") {
            setStreamPhase(toolLabel(data.name));
            update((m) => ({
              ...m,
              tools: [...(m.tools ?? []), { name: data.name, input: data.input, done: false }],
            }));
          } else if (data.type === "tool_result") {
            setStreamPhase("");
            update((m) => {
              const tools = [...(m.tools ?? [])];
              const last = tools[tools.length - 1];
              if (last) tools[tools.length - 1] = { ...last, result: data.result, done: true };
              return { ...m, tools };
            });
          } else if (data.type === "text") {
            setStreamPhase("responding");
            update((m) => ({ ...m, content: m.content + data.content }));
          } else if (data.type === "error") {
            update((m) => ({ ...m, content: `Error: ${data.content}` }));
          }
        }
      }
    } catch (err) {
      update((m) => ({ ...m, content: "Connection error. Please try again." }));
      console.error(err);
    } finally {
      setStreaming(false);
      setStreamPhase("");
    }
  }, [messages, streaming]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  if (!open) return null;

  return (
    <div className="w-[460px] max-w-[40vw] shrink-0 border-l flex flex-col bg-background">
      {/* Header */}
      <div className="flex items-center gap-3 border-b px-4 py-3 shrink-0">
        <RappiAvatar />
        <div className="flex-1">
          <p className="text-sm font-semibold">Rappi AI</p>
          <p className="text-[11px] text-muted-foreground">Ask about store availability data</p>
        </div>
        {messages.length > 0 && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setMessages([])}
            title="New conversation"
          >
            <RotateCcw className="size-3.5" />
          </Button>
        )}
        <Button variant="ghost" size="icon-sm" onClick={onClose}>
          <X className="size-4" />
        </Button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {/* Welcome */}
        {messages.length === 0 && (
          <div className="space-y-4 pt-2">
            <div className="flex gap-3">
              <RappiAvatar />
              <div className="flex-1 space-y-3">
                <div className="text-sm">
                  <p className="font-medium mb-1">
                    Hey! I&apos;m your dashboard assistant.
                  </p>
                  <p className="text-muted-foreground">
                    I can query the database, analyze anomalies, and help you understand
                    store availability patterns. What would you like to explore?
                  </p>
                </div>
                <div className="space-y-1.5">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => sendMessage(s)}
                      className="w-full text-left rounded-lg border px-3 py-2 text-xs text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            {msg.role === "user" ? (
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-[#FC4C02] px-3.5 py-2 text-sm text-white">
                  {msg.content}
                </div>
              </div>
            ) : (
              <div className="flex gap-3">
                <RappiAvatar />
                <div className="flex-1 min-w-0 text-sm space-y-3">
                  {/* Thinking — streamed inline */}
                  {msg.thinking && (
                    <div className="text-xs text-muted-foreground whitespace-pre-wrap leading-relaxed">
                      {msg.thinking}
                    </div>
                  )}

                  {/* Tools */}
                  {msg.tools?.map((tool, ti) => (
                    <div
                      key={ti}
                      className="rounded-lg border border-[#FC4C02]/20 bg-[#FC4C02]/[0.03] overflow-hidden animate-in fade-in duration-300"
                    >
                      {/* Tool header */}
                      <div className="flex items-center gap-2 px-3 py-2 text-xs">
                        <span className="text-[#FC4C02]">
                          {!tool.done ? <Loader2 className="size-3.5 animate-spin" /> : toolIcon(tool.name)}
                        </span>
                        <span className="font-medium text-[#FC4C02]/80">
                          {toolLabel(tool.name)}{!tool.done && "..."}
                        </span>
                      </div>
                      {/* Tool body — slides in when done */}
                      {tool.done && (
                        <div className="border-t border-[#FC4C02]/10 px-3 py-2 space-y-2 animate-in slide-in-from-top-1 fade-in duration-200">
                          {tool.input.sql != null && (
                            <pre className="bg-white dark:bg-black/20 rounded-md p-2.5 text-[11px] leading-relaxed overflow-x-auto whitespace-pre-wrap border border-border/50">
                              {String(tool.input.sql).trim()}
                            </pre>
                          )}
                          {tool.input.reasoning != null && (
                            <p className="text-[11px] text-muted-foreground">{String(tool.input.reasoning)}</p>
                          )}
                          {tool.result && (
                            <details className="group" open>
                              <summary className="text-[11px] text-muted-foreground cursor-pointer hover:text-foreground transition-colors">
                                View result ({String((tool.result as Record<string, unknown>).row_count ?? "data")})
                              </summary>
                              <pre className="mt-1 bg-white dark:bg-black/20 rounded-md p-2.5 text-[10px] leading-relaxed overflow-x-auto max-h-[150px] overflow-y-auto whitespace-pre-wrap border border-border/50">
                                {JSON.stringify(tool.result, null, 2)}
                              </pre>
                            </details>
                          )}
                        </div>
                      )}
                    </div>
                  ))}

                  {/* Stream phase indicator — always visible while generating */}
                  {streaming && i === messages.length - 1 && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="flex gap-1">
                        <span className="size-1.5 rounded-full bg-[#FC4C02] animate-bounce" style={{ animationDelay: "0ms" }} />
                        <span className="size-1.5 rounded-full bg-[#FC4C02] animate-bounce" style={{ animationDelay: "150ms" }} />
                        <span className="size-1.5 rounded-full bg-[#FC4C02] animate-bounce" style={{ animationDelay: "300ms" }} />
                      </span>
                      <span>
                        {streamPhase === "thinking" ? "Thinking..." : streamPhase === "responding" ? "Responding..." : streamPhase ? streamPhase + "..." : "Processing..."}
                      </span>
                    </div>
                  )}

                  {/* Response text */}
                  {msg.content && (
                    <div className={[
                      "prose prose-sm max-w-none text-sm leading-relaxed",
                      "[&_p]:my-2",
                      "[&_h1]:text-base [&_h1]:font-bold [&_h1]:mt-4 [&_h1]:mb-2",
                      "[&_h2]:text-sm [&_h2]:font-bold [&_h2]:mt-4 [&_h2]:mb-2",
                      "[&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mt-3 [&_h3]:mb-1.5",
                      "[&_ul]:my-2 [&_ul]:pl-4 [&_ol]:my-2 [&_ol]:pl-4",
                      "[&_li]:my-1 [&_li]:leading-relaxed",
                      "[&_strong]:font-semibold",
                      "[&_pre]:bg-muted [&_pre]:text-xs [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:my-2",
                      "[&_code]:text-xs [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded",
                      "[&_table]:w-full [&_table]:text-xs [&_table]:my-3 [&_table]:border [&_table]:border-border [&_table]:rounded-lg [&_table]:overflow-hidden",
                      "[&_thead]:bg-muted/50",
                      "[&_th]:text-left [&_th]:py-2 [&_th]:px-3 [&_th]:font-semibold [&_th]:border-b [&_th]:border-border",
                      "[&_td]:py-2 [&_td]:px-3 [&_td]:border-b [&_td]:border-border/50",
                      "[&_tr:last-child_td]:border-b-0",
                      "[&_blockquote]:border-l-2 [&_blockquote]:border-[#FC4C02]/30 [&_blockquote]:pl-3 [&_blockquote]:my-2 [&_blockquote]:text-muted-foreground",
                      "[&_hr]:my-3 [&_hr]:border-border",
                    ].join(" ")}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t px-3 py-2.5 shrink-0">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the data..."
            disabled={streaming}
            rows={1}
            className="flex-1 resize-none rounded-lg border bg-muted/30 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
          />
          <Button
            type="submit"
            size="icon"
            disabled={streaming || !input.trim()}
            className="bg-[#FC4C02] hover:bg-[#e04400] shrink-0"
          >
            {streaming ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
          </Button>
        </div>
      </form>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { MessageSquare, X } from "lucide-react";
import * as api from "@/lib/api";

interface SessionListProps {
  agentId: string;
  userId: string;
  currentSessionId: string | null;
}

interface SessionInfo {
  session_id: string;
  title: string;
  updated_at: number;
  message_count: number;
}

export function SessionList({ agentId, userId, currentSessionId }: SessionListProps) {
  const [open, setOpen] = useState(false);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const loadSessions = async () => {
    setLoading(true);
    try {
      const data = await api.fetchSessions(agentId, userId);
      setSessions(data);
    } catch (e) {
      console.error("Failed to load sessions", e);
    } finally {
      setLoading(false);
    }
  };

  const handleOpen = () => {
    setOpen(true);
    loadSessions();
  };

  const handleSelectSession = (sessionId: string) => {
    setOpen(false);
    router.push(`/?user_id=${userId}&agent_id=${agentId}&session_id=${sessionId}`);
  };

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString("zh-CN");
  };

  return (
    <>
      <button
        onClick={handleOpen}
        className="btn-ghost p-1.5 rounded-md"
        title="会话列表"
      >
        <MessageSquare className="w-4 h-4" />
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div
            className="rounded-xl shadow-xl max-w-md w-full mx-4 max-h-[70vh] flex flex-col"
            style={{ background: "var(--bg)", border: "1px solid var(--border)" }}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "var(--border)" }}>
              <h2 className="font-medium" style={{ color: "var(--text)" }}>
                会话列表 ({userId})
              </h2>
              <button onClick={() => setOpen(false)} className="btn-ghost p-1 rounded">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-2">
              {loading ? (
                <div className="text-center py-8" style={{ color: "var(--text-muted)" }}>
                  加载中...
                </div>
              ) : sessions.length === 0 ? (
                <div className="text-center py-8" style={{ color: "var(--text-muted)" }}>
                  暂无会话
                </div>
              ) : (
                <div className="space-y-1">
                  {sessions.map((session) => (
                    <button
                      key={session.session_id}
                      onClick={() => handleSelectSession(session.session_id)}
                      className="w-full text-left px-3 py-2 rounded-lg transition-colors hover:bg-[var(--glass)]"
                      style={{
                        background: session.session_id === currentSessionId ? "var(--glass)" : undefined,
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium truncate" style={{ color: "var(--text)" }}>
                          {session.title || "未命名会话"}
                        </span>
                        {session.session_id === currentSessionId && (
                          <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "var(--primary)", color: "white" }}>
                            当前
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                        <span>{formatDate(session.updated_at)}</span>
                        <span>·</span>
                        <span>{session.message_count} 条消息</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
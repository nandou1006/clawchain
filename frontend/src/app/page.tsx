"use client";

import { useEffect, useRef, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { PanelRightOpen } from "lucide-react";
import * as api from "@/lib/api";
import { useApp } from "@/lib/store";
import Navbar from "@/components/layout/Navbar";
import ChatPanel from "@/components/chat/ChatPanel";
import InspectorPanel from "@/components/editor/InspectorPanel";
import ConfigModal from "@/components/layout/ConfigModal";
import ApprovalModal from "@/components/layout/ApprovalModal";
import ResizeHandle from "@/components/layout/ResizeHandle";

function HomeContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const userId = searchParams.get("user_id");
  const agentId = searchParams.get("agent_id");
  const sessionId = searchParams.get("session_id");

  const {
    loadAgents,
    loadSession,
    setUserId,
    setCurrentAgentId,
    setCurrentSessionId,
    userRole,
    inspectorWidth,
    setInspectorWidth,
    inspectorPanelMode,
    setInspectorPanelMode,
    uiNotice,
    clearNotice,
    sessionError,
    setShowConfigModal,
    showNotice,
  } = useApp();
  const initCheckedRef = useRef(false);

  // 所有 useEffect 必须在条件语句之前
  useEffect(() => {
    if (!userId) {
      router.push("/unauthorized");
      return;
    }
    setUserId(userId);
    // URL 参数优先于 localStorage
    if (agentId) {
      setCurrentAgentId(agentId);
      try { window.localStorage.setItem("netclaw.agent", agentId); } catch {}
    }
    if (sessionId) {
      setCurrentSessionId(sessionId);
    }
  }, [userId, agentId, sessionId, router, setUserId, setCurrentAgentId, setCurrentSessionId]);

  useEffect(() => {
    if (!userId) return;
    loadAgents();
  }, [userId, loadAgents]);

  // 当 sessionId 变化时加载会话消息
  useEffect(() => {
    if (!userId || !sessionId) return;
    loadSession();
  }, [userId, sessionId, loadSession]);

  useEffect(() => {
    if (initCheckedRef.current) return;
    initCheckedRef.current = true;

    api.fetchInitStatus().then((status) => {
      if (!status.config_ready) {
        setShowConfigModal(true);
        showNotice({
          kind: "info",
          text: "检测到尚未完成初始化，请先在配置中心添加 Provider 并设置默认模型。",
        });
      }
    }).catch(() => {});
  }, [setShowConfigModal, showNotice]);

  useEffect(() => {
    if (!uiNotice) return;
    const timer = setTimeout(() => clearNotice(), 3500);
    return () => clearTimeout(timer);
  }, [uiNotice, clearNotice]);

  // 无 user_id 时返回 null（useEffect 会处理跳转）
  if (!userId) {
    return null;
  }

  // 正在获取用户角色时显示加载状态
  if (userRole === null) {
    return (
      <div className="h-screen flex items-center justify-center" style={{ background: "var(--bg)" }}>
        <div className="text-sm" style={{ color: "var(--text-muted)" }}>Loading...</div>
      </div>
    );
  }

  // 用户不在配置中，显示无权限
  if (userRole === undefined) {
    return (
      <div className="h-screen flex items-center justify-center" style={{ background: "var(--bg)" }}>
        <div className="text-center">
          <div className="text-lg font-medium mb-2" style={{ color: "var(--error)" }}>没有权限访问</div>
          <div className="text-sm" style={{ color: "var(--text-muted)" }}>用户 "{userId}" 未在系统中注册</div>
        </div>
      </div>
    );
  }

  // 是否为管理员
  const isAdmin = userRole === "admin";

  // 普通用户：只显示 ChatPanel
  if (!isAdmin) {
    return (
      <div className="h-screen flex flex-col overflow-hidden" style={{ background: "var(--bg)" }}>
        <ApprovalModal />
        {uiNotice && (
          <div className={`toast toast--${uiNotice.kind} animate-slide-in-left`}>
            {uiNotice.text}
          </div>
        )}
        {sessionError && (
          <div className="px-4 py-2 text-xs font-medium"
            style={{ background: "var(--error-bg)", color: "var(--error)", borderBottom: "1px solid var(--border)" }}>
            {sessionError}
          </div>
        )}
        <div className="flex-1 overflow-hidden">
          <ChatPanel />
        </div>
      </div>
    );
  }

  // 管理员：显示完整界面（Navbar + ChatPanel + InspectorPanel + ConfigModal）
  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: "var(--bg)" }}>
      <Navbar />
      <ConfigModal />
      <ApprovalModal />

      {/* Toast：左侧弹出，与聊天框保持间距 */}
      {uiNotice && (
        <div className={`toast toast--${uiNotice.kind} animate-slide-in-left`}>
          {uiNotice.text}
        </div>
      )}

      {/* Session error */}
      {sessionError && (
        <div className="px-4 py-2 text-xs font-medium"
          style={{ background: "var(--error-bg)", color: "var(--error)", borderBottom: "1px solid var(--border)" }}>
          {sessionError}
        </div>
      )}

      {/* Main workspace with glass inset */}
      <div className="relative flex flex-1 overflow-hidden m-1.5 mt-0 gap-0 rounded-xl"
        style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
        <div className="flex-1 min-w-0 rounded-l-xl overflow-hidden">
          <ChatPanel />
        </div>
        {inspectorPanelMode === "docked" && (
          <>
            <div
              className="w-[1px] h-full flex-shrink-0"
              style={{ background: "linear-gradient(to bottom, transparent, var(--border), transparent)" }}
            />
            <ResizeHandle onResize={(delta) => setInspectorWidth(Math.max(280, inspectorWidth - delta))} />
            <div
              style={{ width: inspectorWidth, minWidth: 280, borderLeft: "1px solid var(--border)" }}
              className="flex-shrink-0 overflow-hidden flex flex-col rounded-r-xl bg-[var(--bg)]"
            >
              <InspectorPanel />
            </div>
          </>
        )}
        <div
          className={`absolute inset-y-0 right-0 z-20 overflow-hidden flex flex-col rounded-r-xl transition-all duration-300 ease-out ${
            inspectorPanelMode === "overlay"
              ? "translate-x-0 opacity-100 pointer-events-auto"
              : "translate-x-full opacity-0 pointer-events-none"
          }`}
          style={{
            width: inspectorWidth,
            minWidth: 280,
            background: "var(--bg)",
            borderLeft: "1px solid var(--border)",
            boxShadow: "0 14px 36px rgba(0, 0, 0, 0.12)",
          }}
        >
          <InspectorPanel />
        </div>
        {inspectorPanelMode === "hidden" && (
          <button
            className="absolute right-2 top-1/2 -translate-y-1/2 z-30 btn-ghost p-1.5 rounded-full"
            style={{ background: "var(--glass)", border: "1px solid var(--border)" }}
            title="展开侧栏（停靠）"
            onClick={() => setInspectorPanelMode("docked")}
          >
            <PanelRightOpen className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<div className="h-screen" style={{ background: "var(--bg)" }} />}>
      <HomeContent />
    </Suspense>
  );
}
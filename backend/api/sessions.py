"""会话管理 API — 多会话模式 + 用户隔离

每个 Agent 可以有多个会话，通过 UUID v4 生成 session_id。
支持 user_id 参数实现多用户隔离。
"""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import list_agents, resolve_agent_sessions_dir
from graph.session_manager import session_manager
from graph.prompt_builder import prompt_builder

router = APIRouter()


def _get_user_id(request: Request) -> str:
    """从请求中获取user_id"""
    user_id = request.query_params.get("user_id")
    if not user_id:
        user_id = request.headers.get("X-User-ID")
    return user_id or "default"


@router.post("/agents/{agent_id}/session")
async def create_session(agent_id: str, request: Request):
    """创建新的空白会话，返回 session_id"""
    user_id = _get_user_id(request)
    session_id = session_manager.create_session(agent_id, title="新会话", user_id=user_id)
    return {"session_id": session_id, "agent_id": agent_id, "user_id": user_id}


@router.get("/agents/{agent_id}/session/{session_id}")
async def get_session(agent_id: str, session_id: str, request: Request):
    """获取指定会话信息"""
    user_id = _get_user_id(request)
    data = session_manager.load_session(session_id, agent_id, user_id)

    if data is None:
        raise HTTPException(404, "会话不存在")

    from graph.token_counter import count_messages_tokens, count_tokens
    messages = data.get("messages", [])
    compressed = data.get("compressed_context", "")

    return {
        "session_id": session_id,
        "agent_id": agent_id,
        "user_id": user_id,
        "message_count": len(messages),
        "token_count": count_messages_tokens(messages) + (count_tokens(compressed) if compressed else 0),
        "has_compressed": bool(compressed),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }


@router.get("/agents/{agent_id}/session/{session_id}/messages")
async def get_session_messages(agent_id: str, session_id: str, request: Request):
    """获取指定会话的完整消息"""
    user_id = _get_user_id(request)
    data = session_manager.load_session(session_id, agent_id, user_id)
    if data is None:
        raise HTTPException(404, "会话不存在")

    system_prompt = prompt_builder.build_system_prompt(agent_id)
    return {
        "session_id": session_id,
        "system_prompt": system_prompt,
        "messages": data.get("messages", []),
        "compressed_context": data.get("compressed_context"),
    }


@router.post("/agents/{agent_id}/session/{session_id}/reset")
async def reset_session(agent_id: str, session_id: str, request: Request):
    """重置指定会话"""
    from graph.agent import agent_manager

    user_id = _get_user_id(request)
    data = session_manager.load_session(session_id, agent_id, user_id)
    if data is None:
        raise HTTPException(404, "会话不存在")

    result: dict = {"session_id": session_id, "memory_saved": None, "archived": False}

    messages = data.get("messages", [])
    if len(messages) >= 2:
        try:
            mem_result = await agent_manager.save_session_memory(session_id, agent_id, user_id)
            result["memory_saved"] = mem_result
        except Exception as e:
            result["memory_saved"] = {"saved": False, "reason": str(e)}

    reset_result = session_manager.reset_session(session_id, agent_id, user_id)
    result["archived"] = reset_result.get("archived", False)
    result["archive_file"] = reset_result.get("archive_file")

    return result


# ---------------------------------------------------------------------------
# 向后兼容 — 保留旧的端点命名
# ---------------------------------------------------------------------------

@router.get("/agents/{agent_id}/session")
async def get_latest_session(agent_id: str, request: Request):
    """获取 Agent 最近活跃的会话信息（兼容旧 API）"""
    user_id = _get_user_id(request)
    sessions = session_manager.list_sessions(agent_id, user_id)
    if not sessions:
        # 没有会话时返回空状态
        return {
            "session_id": None,
            "agent_id": agent_id,
            "user_id": user_id,
            "message_count": 0,
            "token_count": 0,
            "has_compressed": False,
            "created_at": None,
            "updated_at": None,
        }
    # 返回最近的会话
    latest = sessions[0]
    return {
        "session_id": latest["session_id"],
        "agent_id": agent_id,
        "user_id": user_id,
        "message_count": latest.get("message_count", 0),
        "token_count": 0,
        "has_compressed": False,
        "created_at": latest.get("created_at"),
        "updated_at": latest.get("updated_at"),
    }


@router.get("/agents/{agent_id}/session/messages")
async def get_latest_session_messages(agent_id: str, request: Request):
    """获取最近会话的完整消息（兼容旧 API）"""
    user_id = _get_user_id(request)
    sessions = session_manager.list_sessions(agent_id, user_id)
    if not sessions:
        return {
            "session_id": None,
            "system_prompt": prompt_builder.build_system_prompt(agent_id),
            "messages": [],
            "compressed_context": None,
        }
    session_id = sessions[0]["session_id"]
    data = session_manager.load_session(session_id, agent_id, user_id)
    if data is None:
        return {
            "session_id": session_id,
            "system_prompt": prompt_builder.build_system_prompt(agent_id),
            "messages": [],
            "compressed_context": None,
        }
    return {
        "session_id": session_id,
        "system_prompt": prompt_builder.build_system_prompt(agent_id),
        "messages": data.get("messages", []),
        "compressed_context": data.get("compressed_context"),
    }


@router.post("/agents/{agent_id}/session/reset")
async def reset_latest_session(agent_id: str, request: Request):
    """重置最近会话（兼容旧 API）"""
    from graph.agent import agent_manager

    user_id = _get_user_id(request)
    sessions = session_manager.list_sessions(agent_id, user_id)
    if not sessions:
        raise HTTPException(404, "没有可重置的会话")

    session_id = sessions[0]["session_id"]
    data = session_manager.load_session(session_id, agent_id, user_id)

    result: dict = {"session_id": session_id, "memory_saved": None, "archived": False}

    if data:
        messages = data.get("messages", [])
        if len(messages) >= 2:
            try:
                mem_result = await agent_manager.save_session_memory(session_id, agent_id, user_id)
                result["memory_saved"] = mem_result
            except Exception as e:
                result["memory_saved"] = {"saved": False, "reason": str(e)}

    reset_result = session_manager.reset_session(session_id, agent_id, user_id)
    result["archived"] = reset_result.get("archived", False)
    result["archive_file"] = reset_result.get("archive_file")

    return result


# ---------------------------------------------------------------------------
# 会话列表与管理
# ---------------------------------------------------------------------------

@router.get("/agents/{agent_id}/sessions")
async def list_sessions(agent_id: str, request: Request):
    """列出会话（支持 user_id 隔离）"""
    user_id = _get_user_id(request)
    sessions = session_manager.list_sessions(agent_id, user_id)
    return sessions


@router.get("/agents/{agent_id}/sessions/{session_id}/messages")
async def get_messages(agent_id: str, session_id: str, request: Request):
    """获取指定会话的完整消息（含 System Prompt）"""
    user_id = _get_user_id(request)
    data = session_manager.load_session(session_id, agent_id, user_id)
    if data is None:
        raise HTTPException(404, "会话不存在")

    system_prompt = prompt_builder.build_system_prompt(agent_id)
    return {
        "session_id": session_id,
        "system_prompt": system_prompt,
        "messages": data.get("messages", []),
        "compressed_context": data.get("compressed_context"),
    }


@router.get("/agents/{agent_id}/sessions/{session_id}/history")
async def get_history(agent_id: str, session_id: str, request: Request):
    """获取对话历史"""
    user_id = _get_user_id(request)
    data = session_manager.load_session(session_id, agent_id, user_id)
    if data is None:
        raise HTTPException(404, "会话不存在")
    return {
        "messages": data.get("messages", []),
        "compressed_context": data.get("compressed_context"),
    }


@router.post("/agents/{agent_id}/sessions/{session_id}/reset")
async def reset_session_by_id(agent_id: str, session_id: str, request: Request):
    """重置指定会话"""
    from graph.agent import agent_manager

    user_id = _get_user_id(request)
    data = session_manager.load_session(session_id, agent_id, user_id)
    if data is None:
        raise HTTPException(404, "会话不存在")

    result: dict = {"session_id": session_id, "memory_saved": None, "archived": False}

    messages = data.get("messages", [])
    if len(messages) >= 2:
        try:
            mem_result = await agent_manager.save_session_memory(session_id, agent_id, user_id)
            result["memory_saved"] = mem_result
        except Exception as e:
            result["memory_saved"] = {"saved": False, "reason": str(e)}

    reset_result = session_manager.reset_session(session_id, agent_id, user_id)
    result["archived"] = reset_result.get("archived", False)
    result["archive_file"] = reset_result.get("archive_file")

    return result


@router.post("/agents/{agent_id}/sessions/cleanup")
async def sessions_cleanup(agent_id: str, request: Request, enforce: bool = False, dry_run: bool = False):
    """sessions cleanup：prune 过期 + cap 超限 + 磁盘预算。enforce=true 时忽略 mode=warn"""
    user_id = _get_user_id(request)
    if not any(a["id"] == agent_id for a in list_agents()):
        raise HTTPException(404, f"Agent '{agent_id}' 不存在")
    store, report = session_manager._run_session_maintenance(
        agent_id, user_id, enforce=enforce, dry_run=dry_run
    )
    result: dict = {"pruned": report["pruned"], "capped": report["capped"]}
    if report.get("diskBudget"):
        result["diskBudget"] = report["diskBudget"]
    if dry_run:
        result["dry_run"] = True
        result["would_prune"] = report["pruned"]
        result["would_cap"] = report["capped"]
    return result

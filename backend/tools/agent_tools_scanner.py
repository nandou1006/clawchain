"""Agent 专属工具扫描器 — 扫描 data/agents/{agent_id}/tools/ 目录，动态加载工具

工具文件规范:
- 文件名: *_tool.py
- 必须导出 get_tools() 函数，返回 List[langchain_core.tools.Tool]
- 可选导出 TOOL_META 字典，提供展示信息

配置机制:
- 配置中仅存储 enabled 开关状态 (agentTools)
- 工具定义从文件自动扫描
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool, Tool

from config import get_config, resolve_agent_dir, resolve_agent_tools_dir

logger = logging.getLogger(__name__)


def scan_agent_tools_dir(agent_id: str) -> List[Dict[str, Any]]:
    """扫描 Agent 的 tools 目录，返回工具元信息列表

    Returns:
        [{"id": tool_name, "name": display_name, "description": ..., "file": ..., "tool_instance": Tool}]
    """
    tools_dir = resolve_agent_tools_dir(agent_id)
    if not tools_dir.exists():
        return []

    tools_info: List[Dict[str, Any]] = []
    seen_ids: set = set()

    for tool_file in sorted(tools_dir.glob("*_tool.py")):
        try:
            # 动态导入模块
            spec = importlib.util.spec_from_file_location(
                f"agent_tools.{agent_id}.{tool_file.stem}",
                tool_file
            )
            if not spec or not spec.loader:
                logger.warning(f"Failed to create spec for {tool_file}")
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 提取工具
            if not hasattr(module, "get_tools"):
                logger.warning(f"{tool_file} does not export get_tools()")
                continue

            tools_list = module.get_tools()
            if not tools_list:
                continue

            # 获取可选的元信息
            meta = getattr(module, "TOOL_META", {}) or {}

            for tool in tools_list:
                if not isinstance(tool, BaseTool):
                    logger.warning(f"Invalid tool type in {tool_file}: {type(tool)}")
                    continue

                tool_id = tool.name
                if tool_id in seen_ids:
                    logger.warning(f"Duplicate tool id '{tool_id}' in {tool_file}, skipping")
                    continue
                seen_ids.add(tool_id)

                tools_info.append({
                    "id": tool_id,
                    "name": meta.get("display_name", tool_id),
                    "description": meta.get("description", tool.description or ""),
                    "category": meta.get("category", "custom"),
                    "file": str(tool_file.name),
                    "tool_instance": tool,
                })

        except Exception as e:
            logger.error(f"Failed to load tool from {tool_file}: {e}")
            continue

    return tools_info


def get_agent_tools_config(agent_id: str) -> Dict[str, bool]:
    """获取 Agent 的 agentTools 配置（enabled 状态）

    Returns:
        {"tool_id": True/False}
    """
    cfg = get_config()
    agents_list = cfg.get("agents", {}).get("list", [])

    for agent in agents_list:
        if agent.get("id") == agent_id:
            raw_tools = agent.get("agentTools") or {}
            return {k: v.get("enabled", True) for k, v in raw_tools.items() if isinstance(v, dict)}

    return {}


def get_agent_custom_tools(agent_id: str) -> List[BaseTool]:
    """获取 Agent 的专属工具列表（已过滤 enabled=True）

    用于 _build_tools() 集成
    """
    all_tools = scan_agent_tools_dir(agent_id)
    if not all_tools:
        return []

    enabled_config = get_agent_tools_config(agent_id)

    result: List[BaseTool] = []
    for tool_info in all_tools:
        tool_id = tool_info["id"]

        # 未配置则默认启用
        is_enabled = enabled_config.get(tool_id, True)

        if is_enabled:
            result.append(tool_info["tool_instance"])

    return result


def scan_agent_tools_with_status(agent_id: str) -> List[Dict[str, Any]]:
    """扫描工具并合并 enabled 状态（用于 API 返回）

    Returns:
        [{"id", "name", "description", "category", "file", "enabled"}]
    """
    all_tools = scan_agent_tools_dir(agent_id)
    if not all_tools:
        return []

    enabled_config = get_agent_tools_config(agent_id)

    result: List[Dict[str, Any]] = []
    for tool_info in all_tools:
        tool_id = tool_info["id"]
        is_enabled = enabled_config.get(tool_id, True)

        result.append({
            "id": tool_id,
            "name": tool_info["name"],
            "description": tool_info["description"],
            "category": tool_info["category"],
            "file": tool_info["file"],
            "enabled": is_enabled,
        })

    return result


def set_agent_tool_enabled(agent_id: str, tool_id: str, enabled: bool) -> bool:
    """设置工具的 enabled 状态

    Returns:
        True if success, False if tool not found
    """
    from config import get_raw_config, save_config

    # 先检查工具是否存在
    all_tools = scan_agent_tools_dir(agent_id)
    tool_ids = {t["id"] for t in all_tools}
    if tool_id not in tool_ids:
        return False

    # 更新配置
    cfg = get_raw_config()
    agents_list = cfg.setdefault("agents", {}).setdefault("list", [])

    agent_entry = None
    for agent in agents_list:
        if agent.get("id") == agent_id:
            agent_entry = agent
            break

    if not agent_entry:
        return False

    agent_tools = agent_entry.setdefault("agentTools", {})
    agent_tools[tool_id] = {"enabled": enabled}

    save_config(cfg)
    return True
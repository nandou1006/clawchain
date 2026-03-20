"""认证模块 — 用户角色查询与API预留"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class UserInfoResponse(BaseModel):
    """用户信息响应"""
    id: str
    role: str
    name: Optional[str] = None


def get_user_id_from_request(request: Request) -> str:
    """从请求中获取user_id（URL参数优先，其次Header）"""
    user_id = request.query_params.get("user_id")
    if not user_id:
        user_id = request.headers.get("X-User-ID")
    return user_id or ""


def get_user_role(user_id: str) -> str:
    """查询用户角色，供前端判断页面路由"""
    from config import get_config
    cfg = get_config()
    users = cfg.get("auth", {}).get("users", {}).get("users", [])
    for user in users:
        if user.get("id") == user_id:
            return user.get("role", "user")
    return "user"


def get_user_info(user_id: str) -> dict:
    """获取用户完整信息"""
    from config import get_config
    cfg = get_config()
    users = cfg.get("auth", {}).get("users", {}).get("users", [])
    for user in users:
        if user.get("id") == user_id:
            return {
                "id": user.get("id"),
                "role": user.get("role", "user"),
                "name": user.get("name"),
            }
    return {"id": user_id, "role": "user", "name": None}


def verify_api_key(request: Request) -> bool:
    """验证API Key（暂留空，后续实现）"""
    from config import get_config
    cfg = get_config()
    api_key_cfg = cfg.get("auth", {}).get("api_key", {})

    if not api_key_cfg.get("enabled", False):
        return True  # 未启用认证，允许通过

    # TODO: 实现API Key验证逻辑
    return True


@router.get("/auth/user/{user_id}", response_model=UserInfoResponse)
async def get_user_info_endpoint(user_id: str):
    """获取用户信息和角色"""
    info = get_user_info(user_id)
    return UserInfoResponse(**info)
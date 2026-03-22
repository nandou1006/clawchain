"""MEMORY.md 向量索引 — 用于 RAG 模式的语义检索"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from config import resolve_agent_memory_dir


class MemoryIndexer:
    """
    为 memory/MEMORY.md 构建简易的关键词索引。
    生产环境中可替换为 LlamaIndex 向量索引。
    支持用户隔离：每个用户的记忆存储在独立的目录中。
    """

    def __init__(self, agent_id: str, agent_dir: str):
        self.agent_id = agent_id
        self.agent_dir = Path(agent_dir)
        self.workspace_dir = self.agent_dir / "workspace"
        # 按用户存储索引缓存
        self._last_md5_by_user: dict[str, str] = {}
        self._chunks_by_user: dict[str, list[dict[str, Any]]] = {}

    def _get_memory_dir(self, user_id: str = "default") -> Path:
        """获取指定用户的 memory 目录"""
        return resolve_agent_memory_dir(self.agent_id, user_id)

    def _compute_md5(self, user_id: str = "default") -> str:
        memory_dir = self._get_memory_dir(user_id)
        memory_file = self.workspace_dir / "MEMORY.md"
        # 计算用户目录下所有 md 文件的 MD5
        hasher = hashlib.md5()
        if memory_file.exists():
            hasher.update(memory_file.read_bytes())
        if memory_dir.exists():
            for f in sorted(memory_dir.rglob("*.md")):
                try:
                    hasher.update(f.read_bytes())
                except Exception:
                    pass
        return hasher.hexdigest()

    def rebuild_index(self, user_id: str = "default") -> None:
        """重建指定用户的索引"""
        chunks: list[dict[str, Any]] = []
        md_files: list[Path] = []

        memory_dir = self._get_memory_dir(user_id)
        memory_file = self.workspace_dir / "MEMORY.md"

        # 共享的 MEMORY.md（在 workspace 根目录）
        if memory_file.exists():
            md_files.append(memory_file)

        # 用户专属的记忆文件
        if memory_dir.exists():
            md_files.extend(sorted(memory_dir.rglob("*.md"), reverse=True))

        for fp in md_files:
            try:
                text = fp.read_text(encoding="utf-8")
            except Exception:
                continue

            rel_path = str(fp.relative_to(self.agent_dir))
            paragraphs = text.split("\n\n")
            line_no = 1
            for para in paragraphs:
                if para.strip():
                    chunks.append({
                        "text": para.strip(),
                        "source": rel_path,
                        "line": line_no,
                    })
                line_no += para.count("\n") + 2

        self._chunks_by_user[user_id] = chunks
        self._last_md5_by_user[user_id] = self._compute_md5(user_id)

    def _maybe_rebuild(self, user_id: str = "default") -> None:
        current_md5 = self._compute_md5(user_id)
        if current_md5 != self._last_md5_by_user.get(user_id):
            self.rebuild_index(user_id)

    def retrieve(self, query: str, top_k: int = 3, user_id: str = "default") -> list[dict[str, Any]]:
        """基于关键词的检索（可替换为向量检索）"""
        self._maybe_rebuild(user_id)

        chunks = self._chunks_by_user.get(user_id, [])
        if not chunks:
            return []

        query_words = set(query.lower().split())
        scored = []
        for chunk in chunks:
            text_lower = chunk["text"].lower()
            score = sum(1 for w in query_words if w in text_lower)
            if score > 0:
                scored.append({
                    "text": chunk["text"],
                    "score": score,
                    "source": chunk["source"],
                    "line": chunk["line"],
                })

        scored.sort(key=lambda x: -x["score"])
        return scored[:top_k]

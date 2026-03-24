"""示例专属工具 - 指标截图

这是一个 Agent 专属工具的示例实现。
"""

from langchain_core.tools import Tool
from typing import List


def capture_metric_screenshot(metric_name: str, time_range: str = "1h") -> str:
    """
    截取指定指标的时间序列图表。

    Args:
        metric_name: 指标名称，如 "cpu_usage", "memory_percent"
        time_range: 时间范围，如 "1h", "24h", "7d"

    Returns:
        截图文件的路径或描述
    """
    # 这里是示例实现，实际可以调用真实的截图服务
    return f"截图已保存: /screenshots/{metric_name}_{time_range}.png"


def get_tools() -> List[Tool]:
    """返回此文件提供的工具列表"""
    return [
        Tool(
            name="metric_screenshot",
            description="截取指定指标的时间序列图表。参数: metric_name (指标名), time_range (时间范围，默认1h)",
            func=capture_metric_screenshot,
        )
    ]


# 可选：工具元信息（用于前端展示）
TOOL_META = {
    "name": "metric_screenshot",
    "display_name": "指标截图",
    "description": "截取指定指标的时间序列图表",
    "category": "monitoring",
}
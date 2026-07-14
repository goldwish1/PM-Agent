"""阶段 1 演示工具：echo / add（证明循环可观察，非业务 PM 工具）。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from pm_agent.tools.registry import ToolRegistry, ToolSpec


class EchoArgs(BaseModel):
    text: str = Field(description="原样回显的文本")


class AddArgs(BaseModel):
    a: float = Field(description="加数 a")
    b: float = Field(description="加数 b")


def _echo(args: EchoArgs) -> str:
    return f"echo: {args.text}"


def _add(args: AddArgs) -> str:
    total = args.a + args.b
    # 整数结果时去掉多余小数，便于阅读
    if total == int(total):
        return f"sum: {int(total)}"
    return f"sum: {total}"


def register_demo_tools(registry: ToolRegistry) -> None:
    """向 Registry 注册 echo、add。"""
    registry.register(
        ToolSpec(
            name="echo",
            description="回显一段文本，用于验证工具调用链路。",
            parameters_model=EchoArgs,
            execute=_echo,
            category="demo",
        )
    )
    registry.register(
        ToolSpec(
            name="add",
            description="计算两个数字之和，用于验证多工具与参数校验。",
            parameters_model=AddArgs,
            execute=_add,
            category="demo",
        )
    )


def build_demo_registry() -> ToolRegistry:
    registry = ToolRegistry()
    register_demo_tools(registry)
    return registry

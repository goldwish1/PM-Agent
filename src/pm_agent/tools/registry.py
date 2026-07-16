"""Tool Registry：注册 / 查找 / 执行、导出 OpenAI 风格 tools schema。"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError


@dataclass
class ToolSpec:
    """单个可注册工具的元数据与执行函数。"""

    name: str
    description: str
    parameters_model: type[BaseModel]
    execute: Callable[[BaseModel], str]
    category: str = "demo"
    pure: bool = True  # 无副作用时可与其他 pure 工具并行


@dataclass
class ToolRegistry:
    """进程内工具表：供 Agent Loop 派发与 schema 导出。"""

    _tools: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> None:
        if not spec.name:
            raise ValueError("工具名不能为空")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def all_pure(self, names: list[str]) -> bool:
        """同批工具是否均可并行：未知工具视为 impure。"""
        if not names:
            return False
        for name in names:
            spec = self.get(name)
            if spec is None or not spec.pure:
                return False
        return True

    def openai_tools_schema(self) -> list[dict[str, Any]]:
        """导出 Chat Completions `tools` 参数（function calling）。"""
        schemas: list[dict[str, Any]] = []
        for spec in self._tools.values():
            json_schema = spec.parameters_model.model_json_schema()
            # 去掉 Pydantic 注入的 title 噪音，保持 schema 简洁
            json_schema.pop("title", None)
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": json_schema,
                    },
                }
            )
        return schemas

    def execute(self, name: str, arguments: dict[str, Any] | str | None) -> str:
        """执行工具；未知工具 / 参数错误返回中文纠正指令（不抛死进程）。"""
        spec = self.get(name)
        if spec is None:
            known = ", ".join(self.names()) or "（无）"
            return (
                f"错误：未知工具「{name}」。"
                f"不要调用未注册的工具；可选工具：{known}。"
            )

        raw = arguments if arguments is not None else {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                return (
                    f"错误：工具「{name}」的 arguments 不是合法 JSON。"
                    "请用对象形式重试，例如 {\"text\": \"hello\"}。"
                )

        if not isinstance(raw, dict):
            return (
                f"错误：工具「{name}」的 arguments 必须是对象。"
                "请修正参数后重试。"
            )

        try:
            params = spec.parameters_model.model_validate(raw)
        except ValidationError as exc:
            return (
                f"错误：工具「{name}」参数校验失败：{exc.errors()[0].get('msg', exc)}。"
                "请对照 schema 修正字段后重试。"
            )

        try:
            return spec.execute(params)
        except Exception as exc:
            return (
                f"错误：工具「{name}」执行失败：{exc}。"
                "请简化参数或换一种调用方式。"
            )

"""export_markdown：将草稿导出到 output/（路径白名单）。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from pm_agent.agent.session import SessionMode, SessionState
from pm_agent.export.path_guard import PathGuardError, resolve_safe_output_file
from pm_agent.export.render import (
    render_charter_markdown,
    render_decision_markdown,
    render_decision_matrix_markdown,
    render_risk_register_markdown,
)
from pm_agent.tools.registry import ToolRegistry, ToolSpec


class ExportMarkdownArgs(BaseModel):
    doc_type: Literal["charter", "risk_register", "decision", "decision_matrix"] = Field(
        description=(
            "导出文档类型：charter=项目章程，risk_register=风险登记册，"
            "decision=决策记录，decision_matrix=决策矩阵"
        )
    )
    filename: str | None = Field(
        default=None,
        description="可选文件名（仅文件名，禁止路径）。默认按时间戳自动命名",
    )
    confirmed: bool = Field(
        default=False,
        description="必须为 true 才执行写入；表示用户已确认导出",
    )


def _default_filename(doc_type: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    prefix = {
        "charter": "项目章程",
        "risk_register": "风险登记册",
        "decision": "决策记录",
        "decision_matrix": "决策矩阵",
    }
    return f"{prefix.get(doc_type, '文档')}-{stamp}.md"


def _unique_path(output_dir: Path, filename: str) -> Path:
    path = resolve_safe_output_file(output_dir, filename)
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for i in range(2, 100):
        candidate = resolve_safe_output_file(output_dir, f"{stem}-{i}{suffix}")
        if not candidate.exists():
            return candidate
    raise PathGuardError("无法生成不冲突的文件名，请稍后重试。")


def register_export_markdown(
    registry: ToolRegistry,
    state: SessionState,
    output_dir: Path,
) -> None:
    def _execute(args: ExportMarkdownArgs) -> str:
        if not args.confirmed:
            return json.dumps(
                {
                    "ok": False,
                    "instruction": (
                        "尚未确认导出。请先向用户展示草稿预览，"
                        "待用户明确说「确认导出」后再以 confirmed=true 调用本工具。"
                    ),
                },
                ensure_ascii=False,
            )

        try:
            if args.doc_type == "charter":
                if state.charter_draft is None:
                    return json.dumps(
                        {
                            "ok": False,
                            "instruction": (
                                "尚无项目章程草稿。请先调用 draft_project_charter 收集字段。"
                            ),
                        },
                        ensure_ascii=False,
                    )
                content = render_charter_markdown(state.charter_draft)
            elif args.doc_type == "decision_matrix":
                if state.matrix_draft is None:
                    return json.dumps(
                        {
                            "ok": False,
                            "instruction": (
                                "尚无决策矩阵草稿。请先调用 draft_decision_matrix 收集准则与方案。"
                            ),
                        },
                        ensure_ascii=False,
                    )
                content = render_decision_matrix_markdown(state.matrix_draft)
            elif args.doc_type == "decision":
                if state.decision_draft is None:
                    return json.dumps(
                        {
                            "ok": False,
                            "instruction": (
                                "尚无决策记录草稿。请先调用 draft_decision_record 收集字段。"
                            ),
                        },
                        ensure_ascii=False,
                    )
                content = render_decision_markdown(state.decision_draft)
            else:
                if state.risk_draft is None or not state.risk_draft.items:
                    return json.dumps(
                        {
                            "ok": False,
                            "instruction": (
                                "尚无风险登记册条目。请先调用 draft_risk_register 添加 1～3 条。"
                            ),
                        },
                        ensure_ascii=False,
                    )
                content = render_risk_register_markdown(state.risk_draft)

            filename = args.filename or _default_filename(args.doc_type)
            path = _unique_path(output_dir, filename)
            path.write_text(content, encoding="utf-8")
            state.mode = SessionMode.PREVIEW
            return json.dumps(
                {
                    "ok": True,
                    "path": str(path),
                    "doc_type": args.doc_type,
                    "bytes": path.stat().st_size,
                    "note": "导出成功。请把路径告诉用户，便于直接打开 Markdown。",
                },
                ensure_ascii=False,
            )
        except PathGuardError as exc:
            return json.dumps(
                {
                    "ok": False,
                    "instruction": str(exc),
                },
                ensure_ascii=False,
            )
        except OSError:
            return json.dumps(
                {
                    "ok": False,
                    "instruction": (
                        "无法写入文件（权限或路径问题）。草稿已在上方预览，"
                        "请复制保存，或更换可写目录后重试导出。"
                    ),
                },
                ensure_ascii=False,
            )

    registry.register(
        ToolSpec(
            name="export_markdown",
            description=(
                "将当前会话中的项目章程、风险登记册、决策记录或决策矩阵草稿"
                "导出为 Markdown，仅写入 output/ 目录。"
                "必须在用户确认后以 confirmed=true 调用。"
            ),
            parameters_model=ExportMarkdownArgs,
            execute=_execute,
            category="export",
            pure=False,
        )
    )

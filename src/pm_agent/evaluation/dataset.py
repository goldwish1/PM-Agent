"""黄金评测集加载、过滤与稳定摘要。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pm_agent.evaluation.models import EvaluationCase
from pm_agent.knowledge.repo import ToolsRepository


def load_evaluation_cases(path: Path | str) -> list[EvaluationCase]:
    """读取评测集并校验 ID 唯一。"""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"评测集文件不存在：{file_path}")
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("评测集根节点必须是数组")
    cases = [EvaluationCase.model_validate(item) for item in raw]
    ids = [case.id for case in cases]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise ValueError(f"评测集存在重复 id：{duplicates}")
    return cases


def filter_cases(
    cases: list[EvaluationCase],
    *,
    family: str | None = None,
    tag: str | None = None,
) -> list[EvaluationCase]:
    """按工具家族和标签筛选评测集。"""
    result = cases
    if family:
        result = [case for case in result if case.family == family]
    if tag:
        result = [case for case in result if tag in case.tags]
    return result


def validate_case_tools(cases: list[EvaluationCase], repo: ToolsRepository) -> None:
    """校验当前应启用用例引用的工具均存在。"""
    known = {tool.slug for tool in repo.all()}
    errors: list[str] = []
    for case in cases:
        if set(case.requires_tools) - known:
            continue
        referenced = (
            set(case.acceptable_top1)
            | set(case.required_top3)
            | set(case.forbidden_top3)
        )
        missing = sorted(referenced - known)
        if missing:
            errors.append(f"{case.id}: 未知工具 {missing}")
    if errors:
        raise ValueError("评测集引用非法：" + "；".join(errors))


def dataset_digest(cases: list[EvaluationCase]) -> str:
    """计算与顺序无关的评测集摘要。"""
    payload = [
        case.model_dump(mode="json")
        for case in sorted(cases, key=lambda item: item.id)
    ]
    return _digest(payload)


def tools_digest(repo: ToolsRepository) -> str:
    """计算与工具顺序无关的正式库摘要。"""
    payload = [
        tool.model_dump(mode="json", exclude_none=True)
        for tool in sorted(repo.all(), key=lambda item: item.slug)
    ]
    return _digest(payload)


def _digest(payload: object) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

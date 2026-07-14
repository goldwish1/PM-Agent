"""导出路径白名单：仅允许写入 output_dir 下。"""

from __future__ import annotations

from pathlib import Path


class PathGuardError(ValueError):
    """路径逃逸或不合法文件名。"""


def assert_under_output_dir(output_dir: Path, target: Path) -> Path:
    """
    确保 target.resolve() 落在 output_dir.resolve() 之下。
    成功返回规范化后的绝对路径。
    """
    root = output_dir.resolve()
    resolved = target.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathGuardError(
            f"拒绝写入：目标路径不在允许的导出目录内（{root}）。"
        ) from exc
    return resolved


def sanitize_filename(filename: str) -> str:
    """拒绝路径分隔与 ..；只保留文件名本身。"""
    name = filename.strip()
    if not name:
        raise PathGuardError("文件名不能为空。")
    if "/" in name or "\\" in name or ".." in name:
        raise PathGuardError(
            "错误：文件名不得包含路径分隔符或「..」。"
            "仅允许导出到 output/ 下的简单文件名。"
        )
    if name.startswith("."):
        raise PathGuardError("错误：不允许隐藏文件名。")
    if not name.endswith(".md"):
        name = f"{name}.md"
    return name


def resolve_safe_output_file(output_dir: Path, filename: str) -> Path:
    """将 filename 解析为 output_dir 下的安全绝对路径。"""
    safe_name = sanitize_filename(filename)
    root = output_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    candidate = (root / safe_name).resolve()
    return assert_under_output_dir(root, candidate)

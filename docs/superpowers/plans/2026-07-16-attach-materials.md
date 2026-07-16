# `@` 附带材料辅助推荐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户在 CLI 输入中用 `@路径` 附带 `.md`/`.txt`；发送前读入并打印 `[attach]`；把正文注入本轮 user 消息，使推荐更准、澄清更少。

**Architecture:** 纯函数模块 `cli_attach.py` 负责解析 `@`、读文件、截断与组装；`cli.py` 在元指令之后、`handle_user_turn` 之前调用并打印状态；`prompts.py` 增加「有附件块则少问快荐」条文。不新增 Agent 读盘工具。

**Tech Stack:** Python 3.11+、pytest、现有 `prompt_toolkit` REPL（本版不做 `@` 补全）、无新依赖。

**Spec:** `docs/superpowers/specs/2026-07-16-attach-materials-design.md`

## Global Constraints

- 仅 `.md` / `.txt`（大小写不敏感）；UTF-8 只读
- 单文件上限 64KB；单轮合计注入正文预算 128KB
- 路径：相对进程 cwd 或绝对路径；用户主动 `@` 即授权；不做项目根沙箱
- 不新增 `read_file` / `shell` / `grep`；不自扫目录；不做 `@` Tab 补全
- 附件不入 Session 长期状态；下一轮需再 `@`
- 提交信息用简体中文；实现后记 `doc/agent_learn.md`

## File Structure

| 文件 | 职责 |
|------|------|
| `src/pm_agent/cli_attach.py`（新） | 解析、加载、截断、组装、`[attach]` 行格式化 |
| `tests/test_cli_attach.py`（新） | 上述纯函数单测 |
| `src/pm_agent/cli.py` | 接入 `resolve_attachments`；更新 WELCOME/HELP |
| `src/pm_agent/agent/prompts.py` | 附件优先推荐条文 |
| `README.md` | 一行用法说明 |
| `doc/agent_learn.md` | 新增功能记录 |
| `doc/后续迭代注意点.md` | 可选：记下「起草侧吃材料」后续项 |

---

### Task 1: `@` 解析与自然语言剥离

**Files:**
- Create: `src/pm_agent/cli_attach.py`
- Test: `tests/test_cli_attach.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `AttachMention`（`raw: str`, `path_text: str`, `start: int`, `end: int`）
  - `looks_like_attach_path(path_text: str) -> bool`
  - `extract_mentions(text: str) -> list[AttachMention]`
  - `strip_mentions(text: str, mentions: list[AttachMention]) -> str`

- [ ] **Step 1: 写失败测试（解析 / 剥离 / 邮箱误判）**

在 `tests/test_cli_attach.py`：

```python
"""cli_attach：@ 解析、读文件、组装。"""

from __future__ import annotations

from pm_agent.cli_attach import (
    extract_mentions,
    looks_like_attach_path,
    strip_mentions,
)


def test_looks_like_path_accepts_relative_and_ext() -> None:
    assert looks_like_attach_path("./kickoff.md")
    assert looks_like_attach_path("../notes.txt")
    assert looks_like_attach_path("docs/a.md")
    assert looks_like_attach_path("kickoff.md")
    assert looks_like_attach_path("/tmp/x.txt")


def test_looks_like_path_rejects_email_local_part() -> None:
    assert not looks_like_attach_path("user")
    # extract 侧：整段 @user@x.com 不应产出附件 mention


def test_extract_single_and_quoted() -> None:
    text = '下周立项 @./kickoff.md 请推荐'
    ms = extract_mentions(text)
    assert len(ms) == 1
    assert ms[0].path_text == "./kickoff.md"
    assert strip_mentions(text, ms).strip() == "下周立项  请推荐".replace("  ", " ").strip() or (
        "下周立项" in strip_mentions(text, ms) and "请推荐" in strip_mentions(text, ms)
    )

    q = '看这个 @"我的 纪要.md" 谢谢'
    ms2 = extract_mentions(q)
    assert len(ms2) == 1
    assert ms2[0].path_text == "我的 纪要.md"


def test_extract_multiple_in_order() -> None:
    text = "参考 @./a.md 和 @./b.txt"
    ms = extract_mentions(text)
    assert [m.path_text for m in ms] == ["./a.md", "./b.txt"]


def test_email_not_extracted_as_attach() -> None:
    text = "联系 @user@example.com 再立项"
    assert extract_mentions(text) == []
    assert strip_mentions(text, []) == text
```

说明：`strip_mentions` 后允许把多余空白压成单空格或保留原空白再 `.strip()`——**实现时统一为：删除 mention 的 `[start,end)` 后，将连续空白折叠为单个空格，再 strip**。把上面第一条断言改成明确期望：

```python
def test_extract_single_and_quoted() -> None:
    text = "下周立项 @./kickoff.md 请推荐"
    ms = extract_mentions(text)
    assert len(ms) == 1
    assert ms[0].path_text == "./kickoff.md"
    assert strip_mentions(text, ms) == "下周立项 请推荐"

    q = '看这个 @"我的 纪要.md" 谢谢'
    ms2 = extract_mentions(q)
    assert len(ms2) == 1
    assert ms2[0].path_text == "我的 纪要.md"
    assert strip_mentions(q, ms2) == "看这个 谢谢"
```

- [ ] **Step 2: 跑测确认失败**

Run: `uv run pytest tests/test_cli_attach.py::test_extract_single_and_quoted -v`

Expected: FAIL（`cli_attach` 未定义或导入失败）

- [ ] **Step 3: 最小实现解析与剥离**

创建 `src/pm_agent/cli_attach.py`：

```python
"""CLI @附件：解析路径、读 .md/.txt、组装注入文本。"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AttachMention:
    raw: str
    path_text: str
    start: int
    end: int


_QUOTED = re.compile(r'@(?:"([^"]+)"|\'([^\']+)\')')
_BARE = re.compile(r"@([^\s@]+)")


def looks_like_attach_path(path_text: str) -> bool:
    p = path_text.strip()
    if not p:
        return False
    lower = p.lower()
    if lower.endswith(".md") or lower.endswith(".txt"):
        return True
    if p.startswith("./") or p.startswith("../"):
        return True
    if "/" in p:
        return True
    return False


def extract_mentions(text: str) -> list[AttachMention]:
    mentions: list[AttachMention] = []
    used: list[tuple[int, int]] = []

    def _overlap(a: int, b: int) -> bool:
        return any(not (b <= s or a >= e) for s, e in used)

    for cre in (_QUOTED, _BARE):
        for m in cre.finditer(text):
            start, end = m.span()
            if _overlap(start, end):
                continue
            if cre is _QUOTED:
                path_text = m.group(1) if m.group(1) is not None else m.group(2)
            else:
                path_text = m.group(1)
            if not looks_like_attach_path(path_text):
                continue
            used.append((start, end))
            mentions.append(
                AttachMention(raw=m.group(0), path_text=path_text, start=start, end=end)
            )
    mentions.sort(key=lambda x: x.start)
    return mentions


def strip_mentions(text: str, mentions: list[AttachMention]) -> str:
    if not mentions:
        return text
    parts: list[str] = []
    cursor = 0
    for m in sorted(mentions, key=lambda x: x.start):
        parts.append(text[cursor : m.start])
        cursor = m.end
    parts.append(text[cursor:])
    joined = "".join(parts)
    return re.sub(r"\s+", " ", joined).strip()
```

注意：先扫引号再扫裸路径，并用 `used` 防重叠；裸路径 `[^\s@]+` 避免把 `@user@x.com` 吃成奇怪片段——邮箱因 `looks_like_attach_path("user")` 为假且第二段不会单独成 `@` 附件。

- [ ] **Step 4: 跑测确认通过**

Run: `uv run pytest tests/test_cli_attach.py -v`

Expected: PASS（本 Task 相关用例全绿）

- [ ] **Step 5: Commit**

```bash
git add src/pm_agent/cli_attach.py tests/test_cli_attach.py
git commit -m "$(cat <<'EOF'
解析 CLI @路径提及并剥离自然语言。

EOF
)"
```

---

### Task 2: 读文件、校验、单文件截断与合计预算

**Files:**
- Modify: `src/pm_agent/cli_attach.py`
- Modify: `tests/test_cli_attach.py`

**Interfaces:**
- Consumes: `looks_like_attach_path`（Task 1）
- Produces:
  - 常量：`MAX_FILE_BYTES = 64 * 1024`，`MAX_TOTAL_BYTES = 128 * 1024`，`TRUNCATION_SUFFIX = "\n\n…[内容已截断]"`
  - `AttachItem`：`ok: bool`, `display_name: str`, `path: Path | None = None`, `reason: str = ""`, `content: str = ""`, `truncated: bool = False`, `size_bytes: int = 0`
  - `load_attachment(path_text: str, *, cwd: Path, remaining_budget: int) -> AttachItem`

行为约定：
- `remaining_budget <= 0` → `ok=False`, reason 含「合计体积已满」
- 非文件 / 不存在 / 扩展名不对 / 解码失败 → `ok=False` + 中文 reason
- 可读成功：`size_bytes` 为**截断前**原文 UTF-8 字节数；`content` 为注入正文（可能截断）；单文件先按 `min(MAX_FILE_BYTES, remaining_budget)` 截断字符/字节（按 UTF-8 字节截断，避免截断半个字符：用 `encode` 后切片再 `decode(errors="ignore")`）
- 截断时 `truncated=True`，并追加 `TRUNCATION_SUFFIX`（后缀不计入预算亦可；为简单起见：**预算只约束正文原文切片长度，后缀额外追加**）

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path

import pytest

from pm_agent.cli_attach import MAX_FILE_BYTES, load_attachment


def test_load_ok_md(tmp_path: Path) -> None:
    f = tmp_path / "kickoff.md"
    f.write_text("立项下周\n", encoding="utf-8")
    item = load_attachment("kickoff.md", cwd=tmp_path, remaining_budget=MAX_FILE_BYTES)
    assert item.ok is True
    assert item.content == "立项下周\n"
    assert item.truncated is False
    assert item.display_name == "kickoff.md"


def test_load_rejects_extension(tmp_path: Path) -> None:
    f = tmp_path / "a.bin"
    f.write_bytes(b"\x00\x01")
    item = load_attachment("a.bin", cwd=tmp_path, remaining_budget=MAX_FILE_BYTES)
    assert item.ok is False
    assert "md" in item.reason.lower() or "txt" in item.reason.lower() or "仅支持" in item.reason


def test_load_rejects_directory(tmp_path: Path) -> None:
    d = tmp_path / "docs"
    d.mkdir()
    item = load_attachment("docs", cwd=tmp_path, remaining_budget=MAX_FILE_BYTES)
    # docs 无扩展名且是目录；若 looks 未过则不会调用；这里测 load 对目录
    item = load_attachment("./docs", cwd=tmp_path, remaining_budget=MAX_FILE_BYTES)
    assert item.ok is False


def test_load_truncates_to_budget(tmp_path: Path) -> None:
    f = tmp_path / "big.md"
    f.write_text("abcd" * 100, encoding="utf-8")
    item = load_attachment("big.md", cwd=tmp_path, remaining_budget=10)
    assert item.ok is True
    assert item.truncated is True
    assert "内容已截断" in item.content
    # 截断后原文部分的 utf-8 长度 <= 10
    body = item.content.split("\n\n…[内容已截断]")[0]
    assert len(body.encode("utf-8")) <= 10


def test_load_absolute_path(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("hi", encoding="utf-8")
    item = load_attachment(str(f.resolve()), cwd=Path("/"), remaining_budget=MAX_FILE_BYTES)
    assert item.ok is True
    assert item.content == "hi"
```

- [ ] **Step 2: 跑测确认失败**

Run: `uv run pytest tests/test_cli_attach.py::test_load_ok_md -v`

Expected: FAIL（`load_attachment` 未定义）

- [ ] **Step 3: 实现 `load_attachment`**

在 `cli_attach.py` 追加（保持文件顶部 import `from pathlib import Path`）：

```python
MAX_FILE_BYTES = 64 * 1024
MAX_TOTAL_BYTES = 128 * 1024
TRUNCATION_SUFFIX = "\n\n…[内容已截断]"
_ALLOWED_SUFFIX = {".md", ".txt"}


@dataclass(frozen=True)
class AttachItem:
    ok: bool
    display_name: str
    path: Path | None = None
    reason: str = ""
    content: str = ""
    truncated: bool = False
    size_bytes: int = 0


def _truncate_utf8(text: str, max_bytes: int) -> tuple[str, bool]:
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text, False
    cut = raw[:max_bytes].decode("utf-8", errors="ignore")
    return cut + TRUNCATION_SUFFIX, True


def load_attachment(
    path_text: str,
    *,
    cwd: Path,
    remaining_budget: int,
) -> AttachItem:
    display = Path(path_text).name or path_text
    if remaining_budget <= 0:
        return AttachItem(ok=False, display_name=display, reason="合计体积已满，未载入")

    path = Path(path_text)
    if not path.is_absolute():
        path = (cwd / path).resolve()
    else:
        path = path.resolve()

    display = path.name
    if path.suffix.lower() not in _ALLOWED_SUFFIX:
        return AttachItem(
            ok=False,
            display_name=display,
            path=path,
            reason="仅支持 .md / .txt",
        )
    if not path.exists():
        return AttachItem(ok=False, display_name=display, path=path, reason="文件不存在")
    if not path.is_file():
        return AttachItem(ok=False, display_name=display, path=path, reason="不是普通文件")

    try:
        data = path.read_bytes()
    except OSError as exc:
        return AttachItem(
            ok=False, display_name=display, path=path, reason=f"无法读取：{exc}"
        )

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return AttachItem(
            ok=False,
            display_name=display,
            path=path,
            reason="无法按 UTF-8 解码，请另存为 UTF-8",
        )

    limit = min(MAX_FILE_BYTES, remaining_budget)
    content, truncated = _truncate_utf8(text, limit)
    return AttachItem(
        ok=True,
        display_name=display,
        path=path,
        content=content,
        truncated=truncated,
        size_bytes=len(data),
    )
```

- [ ] **Step 4: 跑测确认通过**

Run: `uv run pytest tests/test_cli_attach.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pm_agent/cli_attach.py tests/test_cli_attach.py
git commit -m "$(cat <<'EOF'
实现 @附件读盘校验与体积截断。

EOF
)"
```

---

### Task 3: `resolve_attachments` 组装注入文本

**Files:**
- Modify: `src/pm_agent/cli_attach.py`
- Modify: `tests/test_cli_attach.py`

**Interfaces:**
- Consumes: `extract_mentions`, `strip_mentions`, `load_attachment`, `MAX_TOTAL_BYTES`
- Produces:
  - `AttachResult`：`user_text: str`, `assembled: str`, `items: list[AttachItem]`，以及方法/属性 `should_enter_loop: bool`（`bool(user_text.strip()) or any(i.ok for i in items)`）
  - `resolve_attachments(raw: str, *, cwd: Path | None = None) -> AttachResult`
  - `format_attach_line(item: AttachItem) -> str`  
    成功：`[attach] ok  {name}  ({human_size}{, truncated})`  
    失败：`[attach] fail  {name}  {reason}`  
    `human_size`：`<1024` 用 `N B`，否则 `NKB`（整数 KB 即可）

组装规则（有成功附件时）：

```text
{user_text}

---
[附件 1] path={path} name={name} truncated={true|false}
{content}
---
[附件 2] ...
```

`user_text` 为空且有成功附件时，`assembled` 仍含附件块（可无前导自然语言行，直接从 `---` 开始，或保留空行——**统一：若 user_text 非空则先写 user_text 再空行再附件；若为空则直接从第一个 `---` 块开始**）。

无成功附件时：`assembled == user_text`（不拼块）。

合计预算：按 mention 顺序调用 `load_attachment`；成功注入的 `content` 按**截断前原文**占用预算：用 `min(len(原文 utf-8), MAX_FILE_BYTES)` 累加；简单实现：成功后 `remaining_budget -= min(item.size_bytes, MAX_FILE_BYTES)`（若 truncated 则减去 `MAX_FILE_BYTES` 与 budget 的实际切片——与 `load` 内 `limit` 一致：`used = min(size_bytes, limit_applied)`；可在 `AttachItem` 增加 `budget_used: int` 或在 resolve 里用 `min(size_bytes, MAX_FILE_BYTES, remaining_before)`）。

推荐在 `AttachItem` 增加 `budget_used: int = 0`：成功时为实际计入合计的字节数（不含后缀）。

- [ ] **Step 1: 写失败测试**

```python
from pm_agent.cli_attach import format_attach_line, resolve_attachments


def test_resolve_no_mention_identity(tmp_path: Path) -> None:
    r = resolve_attachments("下周立项不知道从哪下手", cwd=tmp_path)
    assert r.user_text == "下周立项不知道从哪下手"
    assert r.assembled == r.user_text
    assert r.items == []
    assert r.should_enter_loop is True


def test_resolve_injects_block(tmp_path: Path) -> None:
    f = tmp_path / "kickoff.md"
    f.write_text("目的：上线支付", encoding="utf-8")
    r = resolve_attachments("下周立项 @kickoff.md 请推荐", cwd=tmp_path)
    assert r.user_text == "下周立项 请推荐"
    assert r.should_enter_loop is True
    assert len(r.items) == 1 and r.items[0].ok
    assert "[附件 1]" in r.assembled
    assert "path=" in r.assembled
    assert "目的：上线支付" in r.assembled
    assert "truncated=false" in r.assembled


def test_resolve_all_fail_empty_nl_no_loop(tmp_path: Path) -> None:
    r = resolve_attachments("@missing.md", cwd=tmp_path)
    assert r.user_text == ""
    assert r.should_enter_loop is False
    assert r.items and r.items[0].ok is False


def test_resolve_total_budget_skips_later(tmp_path: Path) -> None:
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_bytes(b"x" * 100)
    b.write_text("second", encoding="utf-8")
    # 临时：通过很小的 monkeypatch 测合计——若不想 patch 常量，
    # 可在 resolve_attachments 增加可选参数 total_budget（仅测试用，默认 MAX_TOTAL_BYTES）
    r = resolve_attachments(
        "@a.md @b.md",
        cwd=tmp_path,
        total_budget=50,
    )
    assert r.items[0].ok is True
    assert r.items[1].ok is False
    assert "合计" in r.items[1].reason or "未载入" in r.items[1].reason


def test_format_attach_line_ok_and_fail(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("hi", encoding="utf-8")
    r = resolve_attachments("@a.md", cwd=tmp_path)
    line = format_attach_line(r.items[0])
    assert line.startswith("[attach] ok")
    assert "a.md" in line

    r2 = resolve_attachments("@nope.md", cwd=tmp_path)
    line2 = format_attach_line(r2.items[0])
    assert line2.startswith("[attach] fail")
```

同步扩展签名：

```python
def resolve_attachments(
    raw: str,
    *,
    cwd: Path | None = None,
    total_budget: int | None = None,
) -> AttachResult: ...
```

- [ ] **Step 2: 跑测确认失败**

Run: `uv run pytest tests/test_cli_attach.py::test_resolve_injects_block -v`

Expected: FAIL

- [ ] **Step 3: 实现 `AttachResult` / `resolve_attachments` / `format_attach_line`**

```python
@dataclass(frozen=True)
class AttachResult:
    user_text: str
    assembled: str
    items: tuple[AttachItem, ...]

    @property
    def should_enter_loop(self) -> bool:
        if self.user_text.strip():
            return True
        return any(i.ok for i in self.items)


def format_attach_line(item: AttachItem) -> str:
    if item.ok:
        kb = max(1, (item.size_bytes + 1023) // 1024) if item.size_bytes >= 1024 else None
        size = f"{kb}KB" if kb is not None else f"{item.size_bytes}B"
        extra = ", truncated" if item.truncated else ""
        return f"[attach] ok  {item.display_name}  ({size}{extra})"
    return f"[attach] fail  {item.display_name}  {item.reason}"


def resolve_attachments(
    raw: str,
    *,
    cwd: Path | None = None,
    total_budget: int | None = None,
) -> AttachResult:
    base = cwd if cwd is not None else Path.cwd()
    budget = MAX_TOTAL_BYTES if total_budget is None else total_budget
    mentions = extract_mentions(raw)
    user_text = strip_mentions(raw, mentions)
    items: list[AttachItem] = []
    remaining = budget
    for m in mentions:
        item = load_attachment(m.path_text, cwd=base, remaining_budget=remaining)
        items.append(item)
        if item.ok:
            used = min(item.size_bytes, MAX_FILE_BYTES, remaining)
            remaining -= used

    ok_items = [i for i in items if i.ok]
    if not ok_items:
        return AttachResult(user_text=user_text, assembled=user_text, items=tuple(items))

    blocks: list[str] = []
    for idx, item in enumerate(ok_items, start=1):
        path_s = str(item.path) if item.path is not None else item.display_name
        header = (
            f"[附件 {idx}] path={path_s} name={item.display_name} "
            f"truncated={'true' if item.truncated else 'false'}"
        )
        blocks.append(f"---\n{header}\n{item.content}")
    body = "\n".join(blocks)
    assembled = f"{user_text}\n\n{body}" if user_text else body
    return AttachResult(user_text=user_text, assembled=assembled, items=tuple(items))
```

若 `AttachItem` 尚未含 `budget_used`，上面用 `remaining` 扣减即可，不必强行加字段。

- [ ] **Step 4: 跑测确认通过**

Run: `uv run pytest tests/test_cli_attach.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pm_agent/cli_attach.py tests/test_cli_attach.py
git commit -m "$(cat <<'EOF'
组装 @附件注入文本并格式化 attach 行。

EOF
)"
```

---

### Task 4: CLI 接入

**Files:**
- Modify: `src/pm_agent/cli.py`
- Test: 以手动 / 轻量函数测为主；可选在 `tests/test_cli_attach.py` 测「无 loop 提示文案常量」

**Interfaces:**
- Consumes: `resolve_attachments`, `format_attach_line`, `AttachResult.should_enter_loop`
- Produces: REPL 在业务输入路径上打印 `[attach]`；无正文且无成功附件时不进 loop

- [ ] **Step 1: 增加空附件提示常量（可测）**

在 `cli_attach.py` 或 `cli.py`：

```python
ATTACH_EMPTY_HINT = (
    "未载入任何材料。请使用 @./notes.md 附带 .md/.txt，"
    "或直接描述卡点后再试。"
)
```

若放在 `cli_attach.py`，测试：

```python
from pm_agent.cli_attach import ATTACH_EMPTY_HINT

def test_attach_empty_hint_non_empty() -> None:
    assert "@" in ATTACH_EMPTY_HINT
    assert ".md" in ATTACH_EMPTY_HINT
```

- [ ] **Step 2: 修改 `cli.py` 主循环**

在处理完 `/quit` `/help` `/debug` `/dump` 之后、`user_turn += 1` 之前：

```python
from pm_agent.cli_attach import (
    ATTACH_EMPTY_HINT,
    format_attach_line,
    resolve_attachments,
)

# ... inside loop, after meta commands ...

        attach = resolve_attachments(raw)
        for item in attach.items:
            print(format_attach_line(item), flush=True)
        if not attach.should_enter_loop:
            print(ATTACH_EMPTY_HINT, flush=True)
            continue

        user_turn += 1
        llm = _client_for_turn(
            use_fake=settings.use_fake_llm,
            real_client=real_client,
            user_text=attach.assembled,
        )
        reply = handle_user_turn(
            attach.assembled,
            state,
            llm,
            registry,
            ...
        )
```

注意：FakeLLM 的 `demo_script_for_user_text` 改为看 `attach.assembled`（或仍看 `raw`——推荐看 `assembled`，以便附件正文触发剧本；若现有剧本靠关键词「立项」，剥离后仍在 `user_text` 里即可）。

- [ ] **Step 3: 更新 WELCOME / HELP 各加一行**

WELCOME 能力列表增加：

```text
  · 输入中用 @./notes.md 附带 .md/.txt，辅助更准推荐
```

HELP 演示句增加：

```text
  · 「下周立项 @./kickoff.md」→ 先 [attach] 再推荐
```

- [ ] **Step 4: 跑全量测试**

Run: `uv run pytest -v`

Expected: PASS

- [ ] **Step 5: 手动冒烟（可选但推荐）**

```bash
printf 'hello\n' > /tmp/pmbox-kickoff.md
USE_FAKE_LLM=true uv run pmbox
# 输入：下周立项 @/tmp/pmbox-kickoff.md 不知道从哪下手
# 期望：先见 [attach] ok，再进 loop / 假推荐
# 输入：@/tmp/no-such.md
# 期望：[attach] fail + ATTACH_EMPTY_HINT，不进 loop
```

- [ ] **Step 6: Commit**

```bash
git add src/pm_agent/cli.py src/pm_agent/cli_attach.py tests/test_cli_attach.py
git commit -m "$(cat <<'EOF'
在 CLI 接入 @附件解析与 attach 可见反馈。

EOF
)"
```

---

### Task 5: Prompt 与文档

**Files:**
- Modify: `src/pm_agent/agent/prompts.py`
- Modify: `README.md`
- Modify: `doc/agent_learn.md`
- Modify: `doc/后续迭代注意点.md`（追加一条后续项即可）

**Interfaces:**
- Consumes: 无新代码接口
- Produces: 系统提示含附件优先推荐规则；文档与变更记录齐全

- [ ] **Step 1: 更新 `SYSTEM_PROMPT`**

在「## 澄清」一节改为（或紧接其后增加「## 用户附件」）：

```text
## 用户附件
- 若本轮用户消息含「附件」块（由 CLI @文件注入）：优先依据材料理解卡点并调用 recommend_tools；
  仅当仍缺阶段/卡点类型等关键信息时，再问至多 1 个澄清问题
- 附件只服务本轮；用户未再 @ 时不要假装仍有该文件

## 澄清
- 最多 5 轮；达上限必须 recommend_tools，禁止空转追问
- 有附件时偏好少问快荐，但硬上限仍为 5
```

- [ ] **Step 2: 更新 README**

在命令/用法附近加一句：

```markdown
输入中可用 `@./notes.md` 附带本地 `.md`/`.txt`（发送前显示 `[attach]`），辅助更准确的工具推荐。
```

- [ ] **Step 3: 写 `doc/agent_learn.md` 新增功能条目**

```markdown
### 2026-07-16 · CLI @ 附带材料辅助推荐

- **新增加了什么功能**：输入 `@路径` 附带 `.md/.txt`；CLI 打印 `[attach]` 并将正文注入本轮消息，prompt 引导少问快荐。
- **原因**：用户常有卡点相关纪要，纯对话澄清成本高。
- **一句话方案**：`cli_attach` 解析/截断/组装 + CLI 接入；不新增通用读盘工具。
```

- [ ] **Step 4: `doc/后续迭代注意点.md` 追加**

```text
3. 起草侧「吃材料」：从 @附件或粘贴中抽取字段填章程/风险登记册（本版附件只服务推荐）。
4. `@` 路径 Tab 补全（prompt_toolkit）。
```

- [ ] **Step 5: 跑测 + ruff（若项目惯用）**

Run:

```bash
uv run pytest -v
uv run ruff check src/pm_agent/cli_attach.py src/pm_agent/cli.py src/pm_agent/agent/prompts.py tests/test_cli_attach.py
```

Expected: PASS / 无新 lint 问题

- [ ] **Step 6: Commit**

```bash
git add src/pm_agent/agent/prompts.py README.md doc/agent_learn.md doc/后续迭代注意点.md
git commit -m "$(cat <<'EOF'
补充附件优先推荐提示与使用文档。

EOF
)"
```

- [ ] **Step 7: 将 spec 状态改为已落地（可选同 commit 或下一次）**

把 `docs/superpowers/specs/2026-07-16-attach-materials-design.md` 文首 **状态** 改为 `已实现（见 plans/2026-07-16-attach-materials.md）`。

---

## Spec Coverage Checklist（自检）

| Spec 要求 | Task |
|-----------|------|
| Claude Code 式 `@`、被动不扫盘 | 1–4 |
| `.md`/`.txt`、UTF-8、64KB/128KB | 2–3 |
| cwd 相对 + 绝对路径 | 2 |
| 剥离所有识别到的 `@` | 1、3 |
| 注入块格式 | 3 |
| `[attach]` 可见 | 3–4 |
| 全失败且无正文不进 loop | 3–4 |
| Prompt 少问快荐、澄清上限 5 | 5 |
| 不新增 read_file/shell/grep | 全局遵守 |
| HELP/README/agent_learn | 4–5 |
| 测试覆盖解析/路径/截断/组装 | 1–3 |

## Placeholder / 一致性自检

- 无 TBD；`resolve_attachments(..., total_budget=)` 为测试钩子，默认行为符合 spec
- `AttachItem` / `AttachResult` / `format_attach_line` 命名在 Task 2–4 一致
- 提交信息均为简体中文

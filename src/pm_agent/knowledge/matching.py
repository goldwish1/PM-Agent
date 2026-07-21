"""触发规则匹配引擎：all_of + any_of + 同义词展开。"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from pm_agent.config import REPO_ROOT

DEFAULT_SYNONYMS_PATH = REPO_ROOT / "data" / "recommendation_synonyms.json"


class TriggerMatchRule(BaseModel):
    """工具命中规则：必须满足全量 all_of，且命中至少一个 any_of。"""

    all_of: list[str] = Field(default_factory=list)
    any_of: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_non_empty(self) -> TriggerMatchRule:
        all_len = len([s for s in self.all_of if s.strip()])
        any_len = len([s for s in self.any_of if s.strip()])
        if all_len == 0 or any_len == 0:
            raise ValueError("TriggerMatchRule 必须同时包含非空 all_of 和 any_of")
        return self


_SPACE_SPLIT_RE = re.compile(r"[\s,，]+")
_PUNCT_RE = re.compile(r"[\u3000\s,，.。!?！？;；:：、“”\"'()\[\]{}<>/\\]+")

# 常见“噪声字符”用于从 n-gram 里过滤掉纯装饰性的片段。
_STOP_CHARS = set(
    "我你他她它我们你们他们她们它们的了着吗呢吧呀呀就都还要会把把把与及和或但而又去来在内外对错不没无"
)

# 2~4 字 n-gram 的噪声过滤：太短或纯停用字符会被丢弃。
_DIGIT_RE = re.compile(r"^\d+$")


def normalize_text(text: str) -> str:
    """统一大小写与空白，保留中文内容本体。"""

    return " ".join(_SPACE_SPLIT_RE.split(text.strip())).lower()


def _strip_to_ngrams(text: str) -> str:
    # 先把常见标点空白删掉，避免把“，”“：”“.”拆成 n-gram。
    return _PUNCT_RE.sub("", text)


def _is_noise_ngram(ngram: str) -> bool:
    if not ngram or ngram.isspace():
        return True
    if _DIGIT_RE.match(ngram):
        return True
    non_stop = [c for c in ngram if c not in _STOP_CHARS]
    # 例如“的了吧”“不过不”“我我我”这类就属于噪声。
    if len(non_stop) == 0:
        return True
    # 2 字片段很容易变成“的/是/和”这种，直接过滤掉。
    if len(ngram) <= 2 and len(non_stop) <= 1:
        return True
    return False


def iter_ngrams(text: str, *, min_len: int, max_len: int) -> Iterable[str]:
    """枚举所有连续 n-gram（不做分词）。"""

    core = _strip_to_ngrams(text)
    if len(core) < min_len:
        return []
    out: list[str] = []
    for L in range(min_len, max_len + 1):
        if len(core) < L:
            continue
        for i in range(0, len(core) - L + 1):
            ng = core[i : i + L]
            if _is_noise_ngram(ng):
                continue
            out.append(ng)
    return out


def _count_ngrams_by_phrase(
    phrases: list[str], *, min_len: int, max_len: int
) -> dict[str, dict[str, int]]:
    """统计每个 n-gram 在多少条触发短语里出现（phrase_count）以及总出现次数。"""

    phrase_counts: dict[str, int] = {}
    total_counts: dict[str, int] = {}
    for phrase in phrases:
        seen: set[str] = set()
        for ng in iter_ngrams(phrase, min_len=min_len, max_len=max_len):
            total_counts[ng] = total_counts.get(ng, 0) + 1
            if ng in seen:
                continue
            seen.add(ng)
        for ng in seen:
            phrase_counts[ng] = phrase_counts.get(ng, 0) + 1
    return {
        ng: {"phrase_count": phrase_counts[ng], "total_count": total_counts.get(ng, 0)}
        for ng in phrase_counts
    }


def exact_phrase_rules(trigger_phrases: list[str]) -> list[TriggerMatchRule]:
    """为每条 trigger_phrase 生成等价精确子串规则（all_of/any_of 均为整句）。"""

    rules: list[TriggerMatchRule] = []
    seen: set[str] = set()
    for phrase in trigger_phrases:
        cleaned = phrase.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        rules.append(TriggerMatchRule(all_of=[cleaned], any_of=[cleaned]))
    return rules


def build_trigger_match_rules_for_tool(
    trigger_phrases: list[str],
    *,
    max_derived_rules: int = 6,
    include_exact_phrases: bool = True,
) -> list[TriggerMatchRule]:
    """合并精确子串规则与关键词派生规则，供正式库迁移写盘。"""

    merged: list[TriggerMatchRule] = []
    seen: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()

    def _append(rule: TriggerMatchRule) -> None:
        key = (tuple(rule.all_of), tuple(rule.any_of))
        if key in seen:
            return
        seen.add(key)
        merged.append(rule)

    if include_exact_phrases:
        for rule in exact_phrase_rules(trigger_phrases):
            _append(rule)

    for rule in derive_trigger_match_rules_from_phrases(
        trigger_phrases,
        max_rules=max_derived_rules,
    ):
        _append(rule)

    return merged


def derive_trigger_match_rules_from_phrases(
    trigger_phrases: list[str],
    *,
    max_all_of: int = 1,
    max_any_of: int = 6,
    max_rules: int = 6,
) -> list[TriggerMatchRule]:
    """从 trigger_phrases 自动导出规则（用于数据缺失时的兜底迁移）。

    目标是“召回优先”，因为真实用户提问会改写。
    具体做法是：对每条 trigger_phrase 抽取更长的关键词片段放进 all_of，
    再用同一条短语里的其它关键词放进 any_of；最后保留少量更具体的候选规则。
    """

    cleaned = [p.strip() for p in trigger_phrases if p.strip()]
    if not cleaned:
        return []

    candidate_rules: list[TriggerMatchRule] = []
    for phrase in cleaned:
        core = _strip_to_ngrams(phrase)
        # 派生阶段允许更长的片段：更长片段意味着更高精度，能显著降低误召回。
        raw_grams = [ng for ng in iter_ngrams(phrase, min_len=2, max_len=8) if ng]
        seen: set[str] = set()
        grams: list[str] = []
        for ng in raw_grams:
            if ng in seen:
                continue
            seen.add(ng)
            grams.append(ng)
        if not grams:
            continue

        # 关键词挑选优先“更长”，其次“更靠前”（避免把 all_of 锁在词尾尾巴上）。
        grams.sort(key=lambda g: (-len(g), core.find(g), g))

        all_of_candidates = [g for g in grams if len(g) >= 5]
        if not all_of_candidates:
            all_of_candidates = [g for g in grams if len(g) >= 3]
        if not all_of_candidates:
            continue

        selected_all_of = all_of_candidates[: max(1, max_all_of)]
        selected_all_of_set = set(selected_all_of)

        any_of_candidates = [g for g in grams if g not in selected_all_of_set and len(g) >= 3]
        selected_any_of = any_of_candidates[:max_any_of]
        if not selected_any_of:
            selected_any_of = selected_all_of[:1]

        candidate_rules.append(
            TriggerMatchRule(all_of=selected_all_of, any_of=selected_any_of)
        )

    if not candidate_rules:
        # 极端兜底：至少让规则校验通过。
        first = cleaned[0]
        fallback = first[:2] if len(first) >= 2 else first[:1]
        if not fallback:
            return []
        return [TriggerMatchRule(all_of=[fallback], any_of=[fallback])]

    # 按 trigger_phrases 的原始顺序保留，避免“只挑最长碎片”导致漏掉测试用例里最关键的那条。
    seen: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    out: list[TriggerMatchRule] = []
    for r in candidate_rules:
        key = (tuple(r.all_of), tuple(r.any_of))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= max_rules:
            break
    return out


@lru_cache(maxsize=1)
def load_synonyms(path: Path | str = DEFAULT_SYNONYMS_PATH) -> dict[str, set[str]]:
    """加载同义词表，并构建 variant -> expanded 集合映射。"""

    file_path = Path(path)
    if not file_path.is_file():
        # 同义词是增益项；缺失时完全不阻断服务。
        return {}
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("recommendation_synonyms.json 根节点必须是对象")

    expanded: dict[str, set[str]] = {}
    for canonical, variants in raw.items():
        if not isinstance(canonical, str) or not canonical.strip():
            continue
        if not isinstance(variants, list):
            continue
        group = {canonical.strip()}
        group.update({v.strip() for v in variants if isinstance(v, str) and v.strip()})
        for v in list(group):
            expanded.setdefault(v, set()).update(group)
    return expanded


def expand_keyword(keyword: str, *, synonyms: dict[str, set[str]] | None = None) -> set[str]:
    synonyms = synonyms or {}
    key = keyword.strip()
    if not key:
        return set()
    return synonyms.get(key, {key})


def match_trigger_rule(
    text: str,
    rule: TriggerMatchRule,
    *,
    synonyms: dict[str, set[str]] | None = None,
) -> bool:
    """判断单条触发规则是否命中。"""

    t = text.lower()
    synonyms = synonyms or {}

    # all_of：每个关键词都必须在 text 中出现（同义词集合任意一个出现即可）
    for kw in rule.all_of:
        variants = expand_keyword(kw, synonyms=synonyms)
        if not any(v.lower() in t for v in variants):
            return False

    # any_of：精度优先——当 any_of 较多时，不要只靠“命中一个点”就触发 +12。
    # 这能显著降低误召回（例如某个工具的 any_of 里可能包含通用短语片段）。
    if not rule.any_of:
        return False

    required_hits = 2 if len(rule.any_of) >= 4 else 1
    hit_count = 0
    for kw in rule.any_of:
        variants = expand_keyword(kw, synonyms=synonyms)
        if any(v.lower() in t for v in variants):
            hit_count += 1
            if hit_count >= required_hits:
                return True
    return False


def match_trigger_rules(
    text: str,
    rules: list[TriggerMatchRule],
    *,
    synonyms: dict[str, set[str]] | None = None,
) -> bool:
    """判断工具是否命中（任意一条规则命中即可）。"""

    if not rules:
        return False
    synonyms = synonyms or {}
    return any(match_trigger_rule(text, rule, synonyms=synonyms) for rule in rules)


def tokenize_query_for_search(text: str, *, max_tokens: int = 30) -> list[str]:
    """为 search 生成 token（尽量不引入外部分词依赖）。"""

    raw = text.strip().lower()
    if not raw:
        return []

    # 尝试保留原有“空格切分”行为（对中英混合文本更稳）
    tokens = [t for t in _SPACE_SPLIT_RE.split(raw) if t]
    if tokens:
        return tokens[:max_tokens]

    # 中文无空格：用 n-gram 提供弱召回
    grams = list({ng for ng in iter_ngrams(raw, min_len=2, max_len=4) if not _is_noise_ngram(ng)})
    # 按长度先（更精确），再按字典序保证确定性
    grams.sort(key=lambda s: (-len(s), s))
    return grams[:max_tokens]


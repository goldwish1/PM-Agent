"""LLM 客户端：LlmClient 协议 + FakeLLM + OpenAI 兼容 Real 客户端。"""

from __future__ import annotations

import json
from typing import Any, Protocol

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from pm_agent.config import Settings


class LlmClient(Protocol):
    """Fake / Real 统一接口。"""

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """返回统一形状：{"content", "tool_calls", "usage"}。"""
        ...


class LlmApiError(Exception):
    """已分类的 LLM API 错误，供 CLI / Loop 展示中文提示。"""

    def __init__(self, kind: str, user_message: str) -> None:
        super().__init__(user_message)
        self.kind = kind
        self.user_message = user_message


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(k.lower() in lowered for k in keywords)


def demo_script_for_user_text(user_text: str) -> list[dict[str, Any]]:
    """
    Fake 剧本路由（优先级从上到下）：
    - 导出确认 → export_markdown
    - 起草章程 → draft_project_charter
    - 起草风险 → draft_risk_register
    - 详情 → get_tool_detail
    - 立项推荐 / 风险推荐 / echo / 澄清 / 默认检索推荐
    """
    text = user_text.strip()
    snippet = text[:80] or "ping"

    # —— 拒绝：起草不支持的工具（WBS / 干系人登记册等）——
    draft_intent = _contains_any(
        text,
        ["起草", "填写", "写一份", "帮我写", "自动生成", "帮我填"],
    )
    unsupported_target = _contains_any(
        text,
        [
            "wbs",
            "工作分解",
            "干系人登记册",
            "stakeholder-register",
            "stakeholder register",
            "甘特图",
            "沟通管理计划",
            "采购管理计划",
            "需求跟踪",
            "质量核对",
        ],
    )
    allowed_draft_target = _contains_any(
        text,
        [
            "项目章程", "章程", "charter",
            "风险登记册", "risk-register", "风险条目",
            "决策记录", "decision-record",
            "决策矩阵", "decision-matrix",
        ],
    )
    if draft_intent and unsupported_target and not allowed_draft_target:
        slug = "wbs"
        if _contains_any(text, ["干系人", "stakeholder"]):
            slug = "stakeholder-register"
        elif _contains_any(text, ["甘特"]):
            slug = "gantt-chart"
        return [
            {
                "tool_calls": [
                    {
                        "id": "call_detail_unsupported",
                        "name": "get_tool_detail",
                        "arguments": {"slug": slug},
                    }
                ]
            },
            {
                "content": (
                    "本 MVP **仅支持自动起草「项目章程」「风险登记册」"
                    "「决策矩阵」和「决策记录」**，"
                    f"不支持自动填写「{slug}」完整模板。\n"
                    "你可查看上方工具说明（步骤/场景）；"
                    "若要开干，请改口：「帮我起草项目章程」「起草风险登记册」"
                    "「起草决策矩阵」或「起草决策记录」。"
                )
            },
        ]

    if _contains_any(text, ["重新起草章程", "重新起草项目章程"]):
        return [
            {
                "tool_calls": [
                    {
                        "id": "call_redraft_charter",
                        "name": "draft_project_charter",
                        "arguments": {
                            "reset": True,
                            "project_name": "学习型 PM Agent",
                            "sponsor": "自己",
                            "project_manager": "自己",
                            "business_case": "重新起草示例",
                            "high_level_scope": "CLI 推荐与导出",
                            "milestones": "待补充",
                            "budget": "待补充",
                            "risks": "待补充",
                            "signature": "待补充",
                        },
                    }
                ]
            },
            {
                "content": (
                    "已重新起草项目章程（见预览）。"
                    "确认无误后回复「确认导出」。"
                )
            },
        ]

    if _contains_any(
        text,
        [
            "确认导出", "导出章程", "导出项目章程", "导出风险", "导出登记册",
            "导出决策记录", "导出决策矩阵", "导出决策", "导出 markdown",
        ],
    ):
        doc_type = "charter"
        if _contains_any(text, ["风险", "登记册", "risk"]):
            doc_type = "risk_register"
        elif _contains_any(text, ["决策矩阵", "decision-matrix", "matrix"]):
            doc_type = "decision_matrix"
        elif _contains_any(text, ["决策", "decision"]):
            doc_type = "decision"
        labels = {
            "charter": "项目章程",
            "risk_register": "风险登记册",
            "decision": "决策记录",
            "decision_matrix": "决策矩阵",
        }
        label = labels.get(doc_type, "文档")
        return [
            {
                "tool_calls": [
                    {
                        "id": "call_export_1",
                        "name": "export_markdown",
                        "arguments": {
                            "doc_type": doc_type,
                            "confirmed": True,
                        },
                    }
                ]
            },
            {
                "content": (
                    f"已导出「{label}」Markdown（见上方 tool_result 返回的 path）。"
                    "请直接打开该文件继续修改。"
                )
            },
        ]

    if _contains_any(
        text,
        ["起草项目章程", "起草章程", "帮我起草章程", "填写项目章程", "写一份项目章程"],
    ) or (
        _contains_any(text, ["起草"])
        and _contains_any(text, ["章程", "charter"])
    ):
        return [
            {
                "tool_calls": [
                    {
                        "id": "call_draft_charter_1",
                        "name": "draft_project_charter",
                        "arguments": {
                            "project_name": "学习型 PM Agent",
                            "sponsor": "自己",
                            "project_manager": "自己",
                            "business_case": "从 0 到 1 练手造 Agent，跑通推荐与导出闭环",
                            "high_level_scope": "CLI：工具推荐 + 章程/风险起草导出",
                            "milestones": "阶段 0～4 可演示；阶段 5 验收",
                            "budget": "待补充",
                            "risks": "模型幻觉库外工具名",
                            "signature": "待补充",
                        },
                    }
                ]
            },
            {
                "content": (
                    "已生成项目章程草稿预览（字段见工具返回）。\n"
                    "缺项可用「待补充」。若确认无误，请回复「确认导出」写入 output/。"
                )
            },
        ]

    if _contains_any(
        text,
        ["起草风险登记册", "起草风险", "帮我起草风险", "填写风险登记册"],
    ):
        return [
            {
                "tool_calls": [
                    {
                        "id": "call_draft_risk_1",
                        "name": "draft_risk_register",
                        "arguments": {
                            "replace_all": True,
                            "items": [
                                {
                                    "risk_id": "R01",
                                    "description": "模型编造库外工具",
                                    "cause": "缺少白名单校验时的幻觉",
                                    "probability": "中",
                                    "impact": "高",
                                    "score": "高",
                                    "response": "推荐工具做 slug 白名单",
                                    "owner": "自己",
                                    "status": "开放",
                                },
                                {
                                    "risk_id": "R02",
                                    "description": "导出路径逃逸",
                                    "cause": "未做目录白名单",
                                    "probability": "低",
                                    "impact": "高",
                                    "score": "中",
                                    "response": "export 仅写 output/",
                                    "owner": "自己",
                                    "status": "缓解中",
                                },
                            ],
                        },
                    }
                ]
            },
            {
                "content": (
                    "已起草风险登记册（2 条）预览如上。"
                    "若确认，请回复「确认导出风险登记册」。"
                )
            },
        ]

    if _contains_any(
        text,
        ["起草决策矩阵", "帮我起草决策矩阵", "decision-matrix"],
    ):
        return [
            {
                "tool_calls": [
                    {
                        "id": "call_draft_matrix_1",
                        "name": "draft_decision_matrix",
                        "arguments": {
                            "title": "自研 vs 外采方案决策矩阵",
                            "context": "团队需要在自研与外采之间做量化比较，预算50万",
                            "replace_criteria": True,
                            "criteria": [
                                {"criterion_id": "C01", "name": "成本", "weight": "30%"},
                                {"criterion_id": "C02", "name": "周期", "weight": "25%"},
                                {"criterion_id": "C03", "name": "可控性", "weight": "25%"},
                                {"criterion_id": "C04", "name": "风险", "weight": "20%"},
                            ],
                            "replace_options": True,
                            "options": [
                                {
                                    "option_id": "O01",
                                    "name": "自研",
                                    "scores": {
                                        "C01": "6",
                                        "C02": "5",
                                        "C03": "9",
                                        "C04": "6",
                                    },
                                    "weighted_total": "6.5",
                                },
                                {
                                    "option_id": "O02",
                                    "name": "外采",
                                    "scores": {
                                        "C01": "7",
                                        "C02": "8",
                                        "C03": "5",
                                        "C04": "7",
                                    },
                                    "weighted_total": "6.8",
                                },
                            ],
                            "recommended_option": "外采（加权总分略高）",
                            "rationale": "周期与成本维度外采更优；若更看重可控性可选自研",
                        },
                    }
                ]
            },
            {
                "content": (
                    "已生成决策矩阵草稿预览（准则/方案/打分见工具返回）。\n"
                    "若确认无误，请回复「确认导出决策矩阵」写入 output/。"
                )
            },
        ]

    if _contains_any(
        text,
        ["起草决策记录", "起草决策", "帮我起草决策记录", "帮我起草决策"],
    ):
        return [
            {
                "tool_calls": [
                    {
                        "id": "call_draft_decision_1",
                        "name": "draft_decision_record",
                        "arguments": {
                            "decision_title": "自研 vs 外采方案决策",
                            "context": "团队需要决定自研还是外采方案，预算50万，团队3人",
                            "options_considered": (
                                "方案A：自研，可控但周期长\n"
                                "方案B：外采，快速上线但定制成本高"
                            ),
                            "decision": "采用自研方案",
                            "rationale": "长期可控，团队能力可沉淀",
                            "consequences": "开发周期3个月，需招聘1人",
                            "decision_maker": "张三",
                            "decision_date": "2026-07-17",
                            "status": "拟定",
                        },
                    }
                ]
            },
            {
                "content": (
                    "已生成决策记录草稿预览（字段见工具返回）。\n"
                    "若确认无误，请回复「确认导出决策记录」写入 output/。"
                )
            },
        ]

    if _contains_any(
        text,
        ["echo", "add", "演示工具", "算一下", "相加"],
    ):
        return [
            {
                "tool_calls": [
                    {
                        "id": "call_echo_1",
                        "name": "echo",
                        "arguments": {"text": snippet},
                    }
                ]
            },
            {
                "tool_calls": [
                    {
                        "id": "call_add_1",
                        "name": "add",
                        "arguments": {"a": 1, "b": 2},
                    }
                ]
            },
            {
                "content": (
                    f"已依次调用 echo / add。这是链路演示回复（「{snippet}」）。"
                    "正式推荐请描述立项/风险等卡点。"
                )
            },
        ]

    if _contains_any(text, ["看一下", "详情", "详细"]) or text.strip() in {
        "project-charter",
        "risk-register",
    }:
        slug = (
            "risk-register"
            if _contains_any(text, ["风险", "risk"])
            else "project-charter"
        )
        label = "风险登记册" if slug == "risk-register" else "项目章程"
        return [
            {
                "tool_calls": [
                    {
                        "id": "call_detail_1",
                        "name": "get_tool_detail",
                        "arguments": {"slug": slug},
                    }
                ]
            },
            {
                "content": (
                    f"已查询「{label}」（{slug}）详情。"
                    "若要起草，可说「帮我起草项目章程」或「起草风险登记册」。"
                )
            },
        ]

    if _contains_any(
        text,
        ["立项", "授权", "启动", "kickoff", "下周", "不知从哪", "从哪下手"],
    ):
        return [
            {
                "tool_calls": [
                    {
                        "id": "call_recommend_1",
                        "name": "recommend_tools",
                        "arguments": {
                            "question": text,
                            "candidate_slugs": [
                                "project-charter",
                                "stakeholder-register",
                                "assumption-log",
                            ],
                        },
                    }
                ]
            },
            {
                "content": (
                    "根据你的立项卡点，建议优先使用以下库内工具：\n"
                    "1. **项目章程**（project-charter，启动/整合）——正式授权项目，"
                    "明确目的与高层约束；适合「还没正式立项」的当下。\n"
                    "2. **干系人登记册**（stakeholder-register）——先认清发起人与关键干系人。\n"
                    "3. **假设日志**（assumption-log）——把未验证假设写清楚，降低后期翻车。\n"
                    "可继续说「帮我起草项目章程」进入起草导出。"
                )
            },
        ]

    if _contains_any(text, ["风险", "担心", "不确定", "隐患"]):
        return [
            {
                "tool_calls": [
                    {
                        "id": "call_recommend_risk",
                        "name": "recommend_tools",
                        "arguments": {
                            "question": text,
                            "candidate_slugs": [
                                "risk-register",
                                "risk-management-plan",
                                "risk-report",
                            ],
                        },
                    }
                ]
            },
            {
                "content": (
                    "针对风险类卡点，推荐：\n"
                    "1. **风险登记册**（risk-register）——记录风险、评估与应对。\n"
                    "2. **风险管理计划**——先对齐识别/评估方法。\n"
                    "3. **风险报告**——需要向发起人汇报态势时使用。\n"
                    "可说「起草风险登记册」开始录入 1～3 条。"
                )
            },
        ]

    if len(text) < 8:
        return [
            {
                "content": (
                    "信息有点少。请问：你当前更接近哪个阶段——"
                    "启动立项、规划排期，还是执行中冒出的风险/问题？"
                    "（这是澄清；下一轮将给出库内工具推荐。）"
                )
            }
        ]

    return [
        {
            "tool_calls": [
                {
                    "id": "call_search_1",
                    "name": "search_tools",
                    "arguments": {"query": snippet, "limit": 5},
                }
            ]
        },
        {
            "tool_calls": [
                {
                    "id": "call_recommend_2",
                    "name": "recommend_tools",
                    "arguments": {"question": text},
                }
            ]
        },
        {
            "content": (
                f"已根据「{snippet}」检索并推荐库内工具（见上方 tool_result）。"
                "请按编号查看；若需要详情或起草，直接说工具名。"
            )
        },
    ]


class FakeLlmClient:
    """按预设剧本逐步返回 tool_calls 或最终 content。"""

    def __init__(self, script: list[dict[str, Any]] | None = None) -> None:
        self._script = list(script or [])
        self._index = 0

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        _ = messages, tools
        if self._index >= len(self._script):
            return {
                "content": "（假模型剧本已用尽，结束本轮。）",
                "tool_calls": None,
                "usage": None,
            }

        turn = self._script[self._index]
        self._index += 1

        tool_calls = turn.get("tool_calls")
        content = turn.get("content")
        if tool_calls:
            normalized: list[dict[str, Any]] = []
            for raw in tool_calls:
                normalized.append(
                    {
                        "id": str(raw.get("id", f"call_{self._index}")),
                        "name": str(raw["name"]),
                        "arguments": raw.get("arguments") or {},
                    }
                )
            return {"content": content, "tool_calls": normalized, "usage": None}

        return {
            "content": content if content is not None else "",
            "tool_calls": None,
            "usage": None,
        }


def classify_api_error(exc: BaseException) -> LlmApiError:
    """将 openai SDK 异常映射为用户可读中文提示。"""
    if isinstance(exc, LlmApiError):
        return exc
    if isinstance(exc, AuthenticationError):
        return LlmApiError(
            "auth",
            "API 密钥无效或未配置，请检查本地配置后重启。",
        )
    if isinstance(exc, RateLimitError):
        return LlmApiError(
            "rate_limit",
            "请求过于频繁，请稍后再试。",
        )
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return LlmApiError(
            "network",
            "模型服务暂时不可用（网络或服务异常）。请稍后重试；"
            "你也可以直接说：起草项目章程 / 起草风险登记册。",
        )
    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", None)
        if status == 401:
            return LlmApiError(
                "auth",
                "API 密钥无效或未配置，请检查本地配置后重启。",
            )
        if status == 429:
            return LlmApiError(
                "rate_limit",
                "请求过于频繁，请稍后再试。",
            )
        return LlmApiError(
            "api",
            "模型服务暂时不可用（网络或服务异常）。请稍后重试；"
            "你也可以直接说：起草项目章程 / 起草风险登记册。",
        )
    return LlmApiError(
        "unknown",
        "模型服务暂时不可用（网络或服务异常）。请稍后重试；"
        "你也可以直接说：起草项目章程 / 起草风险登记册。",
    )


def _parse_tool_arguments(raw: str | None) -> dict[str, Any]:
    if not raw or not str(raw).strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}
    if isinstance(parsed, dict):
        return parsed
    return {"_raw": parsed}


def _extract_usage(response: Any) -> dict[str, int] | None:
    """从 OpenAI 兼容 response.usage 提取 token 计数。"""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    total = getattr(usage, "total_tokens", None)
    if prompt is None and completion is None and total is None:
        return None
    out: dict[str, int] = {}
    if prompt is not None:
        out["prompt_tokens"] = int(prompt)
    if completion is not None:
        out["completion_tokens"] = int(completion)
    if total is not None:
        out["total_tokens"] = int(total)
    elif "prompt_tokens" in out and "completion_tokens" in out:
        out["total_tokens"] = out["prompt_tokens"] + out["completion_tokens"]
    return out or None


def _normalize_messages_for_api(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """去掉仅本地使用的字段，保持 OpenAI Chat Completions 形状。"""
    cleaned: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        item: dict[str, Any] = {"role": role}
        if role == "tool":
            item["tool_call_id"] = msg.get("tool_call_id")
            item["content"] = msg.get("content") or ""
            # name 对部分兼容端可选；DeepSeek 通常可接受省略
            if msg.get("name"):
                item["name"] = msg["name"]
        elif role == "assistant":
            item["content"] = msg.get("content")
            if msg.get("tool_calls"):
                item["tool_calls"] = msg["tool_calls"]
        else:
            item["content"] = msg.get("content")
        cleaned.append(item)
    return cleaned


class OpenAICompatibleClient:
    """DeepSeek / OpenAI 兼容 Chat Completions + tools。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        *,
        timeout: float = 120.0,
        client: OpenAI | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._client = client or OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": _normalize_messages_for_api(messages),
        }
        if tools:
            kwargs["tools"] = tools

        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise classify_api_error(exc) from exc

        usage = _extract_usage(response)

        if not response.choices:
            return {
                "content": "（模型未返回任何 choice。）",
                "tool_calls": None,
                "usage": usage,
            }

        message = response.choices[0].message
        content = message.content
        raw_calls = getattr(message, "tool_calls", None) or []
        if not raw_calls:
            return {"content": content, "tool_calls": None, "usage": usage}

        tool_calls: list[dict[str, Any]] = []
        for tc in raw_calls:
            function = getattr(tc, "function", None)
            name = getattr(function, "name", None) if function else None
            arguments = getattr(function, "arguments", None) if function else None
            tool_calls.append(
                {
                    "id": str(getattr(tc, "id", "") or f"call_{len(tool_calls) + 1}"),
                    "name": str(name or ""),
                    "arguments": _parse_tool_arguments(arguments),
                }
            )
        return {"content": content, "tool_calls": tool_calls, "usage": usage}


def build_llm_client(
    settings: Settings,
    *,
    fake_script: list[dict[str, Any]] | None = None,
) -> LlmClient:
    """按 Settings 构造 Fake 或 Real 客户端。"""
    if settings.use_fake_llm:
        return FakeLlmClient(fake_script)
    return OpenAICompatibleClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )

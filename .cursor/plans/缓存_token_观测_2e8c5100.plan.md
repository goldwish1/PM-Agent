---
name: 缓存 token 观测
overview: 在 LLM usage 提取与 debug 观测链路中增加 DeepSeek 的 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`，并在终端摘要与 turn dump 中可聚合查看。
todos:
  - id: extract-usage
    content: openai_llm._extract_usage 增加 hit/miss 字段提取
    status: completed
  - id: debug-sum-format
    content: debug_log.sum_usage 与 _format_usage_line 支持聚合与展示
    status: completed
  - id: tests
    content: 更新 test_debug_log.py 覆盖提取/聚合/缺省兼容
    status: completed
  - id: agent-learn
    content: 在 doc/agent_learn.md 记录本次观测增强
    status: completed
isProject: false
---

# 添加 prompt cache hit/miss 观测字段

## 背景

DeepSeek（及兼容端）在 `usage` 中返回：

- `prompt_cache_hit_tokens`
- `prompt_cache_miss_tokens`

当前 [`_extract_usage`](src/pm_agent/agent/openai_llm.py) 只保留 prompt/completion/total，debug dump 无法验证 Agent 多轮前缀缓存是否生效。

## 改动点

### 1. 提取字段 — [`src/pm_agent/agent/openai_llm.py`](src/pm_agent/agent/openai_llm.py)

在 `_extract_usage` 中，与现有三字段同样用 `getattr` 读取；**有值才写入**（网关不支持时省略，不造 0）。

```python
for key in ("prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
    val = getattr(usage, key, None)
    if val is not None:
        out[key] = int(val)
```

不额外解析 OpenAI 的 `prompt_tokens_details.cached_tokens`（本项目主路径是 DeepSeek 字段；避免双源混淆）。

### 2. 聚合与终端展示 — [`src/pm_agent/agent/debug_log.py`](src/pm_agent/agent/debug_log.py)

- **`sum_usage`**：对两字段分别求和；仅当至少一轮出现过该键时才写入 `usage_total`（与 prompt/completion 一致，避免全无时塞 `0`）。
- **`_format_usage_line`**：有任一 cache 字段时追加，例如  
  `usage: prompt=… completion=… total=… cache_hit=… cache_miss=…`  
  缺省字段不显示，FakeLLM 仍为 `usage: fake`。

L2 落盘无需改结构：`record_iteration` 已原样写入 `usage`，`finalize` 的 `usage_total` 走 `sum_usage` 即可带上新字段。

### 3. 测试 — [`tests/test_debug_log.py`](tests/test_debug_log.py)

- 扩展 `test_openai_compatible_client_extracts_usage`：mock usage 带两字段，断言 result 包含。
- 新增/扩展：无 cache 字段时行为不变（兼容旧 mock）。
- 扩展 `sum_usage` / `format_llm_round`：有 hit/miss 时合计与 L1 文案正确；缺字段时不出现 `cache_`。

### 4. 变更记录 — [`doc/agent_learn.md`](doc/agent_learn.md)

按项目约定记一条「新增功能」：观测 DeepSeek prompt cache hit/miss；原因是验证 Agent 多轮前缀缓存；方案为 usage 提取 + debug/sum。

## 验收

```bash
uv run pytest tests/test_debug_log.py
```

真机（可选）：开 `PMBOX_DEBUG=1` 或看 `output/debug/turn-*.json` 的 `usage` / `usage_total` 是否出现两字段。

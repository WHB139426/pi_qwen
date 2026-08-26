# Minimal Qwen Agent Loop

A small, non-interactive Python agent inspired by Pi's core design:

```text
model -> tool calls -> tool results -> model -> final answer
```

The framework is split into small, single-purpose packages:

- `agent_core/`: model-independent types and the agent loop.
- `models/`: model adapters; `models/qwen.py` contains local Qwen3.8 inference.
- `tools/`: one module per tool plus the shared tool registry.
- `main.py`: configuration and dependency assembly.

`tools/web_search.py` implements the DuckDuckGo search tool, while
`tools/coding.py` groups the closely related coding tools. `tools/__init__.py`
exports the list consumed by the agent.

## Coding tools

The coding tool module provides `read`, `bash`, `edit`, and `write`. Text and
shell output is limited to 50 KB before being returned to the model. `edit`
requires one unique exact match; `write` creates parent directories and replaces
the complete target file. These tools run with the same filesystem and process
permissions as `main.py`; this minimal harness does not provide a sandbox or an
approval layer.

When no dedicated tool exists, the runtime instructions allow the model to use
`bash` to write or run a small Python or shell program for calculations, API
calls, and data processing. Temporary scripts, downloads, and intermediate
artifacts must be placed under `./tmp/` rather than the project root.

## Web search

The `web_search` tool queries DuckDuckGo's HTML search page and returns up to ten
results containing `title`, `url`, and `snippet`. It uses the `httpx` package
already available in the `pi_agent` environment and does not require an API key.

This endpoint is suitable for local experiments, but it is not a guaranteed
stable search API. Network access is required, and a production harness should
normally use an official search API such as Brave Search or Tavily.

## Run

Use the existing `pi_agent` environment:

```bash
cd /data4/haibo/code/pi_qwen
conda activate pi_agent
python main.py
```

Control thinking, reasoning effort, and raw tracing with the constants at the top
of `main.py`:

```python
ENABLE_THINKING = False
REASONING_EFFORT = "medium"
SHOW_RAW_TRACE = True
```

Raw tracing prints immediately after every model turn. The first turn contains
the initial context; later turns contain only context added since the previous
turn plus the new model output, so history is not repeated. Decoding uses
`skip_special_tokens=False`, preserving markers such as `<|im_start|>`,
`<|im_end|>`, `<think>`, and `<tool_call>`. Readability labels and turn numbers
are trace annotations and are not tokens seen by the model.

## Test without loading the model

```bash
python -m unittest -v
```

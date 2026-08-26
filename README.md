# Minimal Qwen Agent Loop

A small, non-interactive Python agent harness for Qwen3.8. It keeps the core
loop model-independent and supports two inference backends:

- Transformers: load the local checkpoint in the Agent process.
- vLLM: call a separately deployed OpenAI-compatible model server.

```text
user task
   -> model
   -> optional tool calls
   -> local tool execution
   -> tool results
   -> model
   -> final answer
```

There is no interactive UI, session database, sandbox, or approval layer. The
project is intentionally small enough to use as a reference implementation of
an agent loop.

## Project structure

```text
pi_qwen/
├── AGENTS.md             Runtime instructions loaded as the system message
├── main.py               Configuration and dependency assembly
├── agent_core/
│   ├── loop.py           Model-independent agent loop
│   └── types.py          Message, Tool, ChatModel, and AgentResult types
├── models/
│   ├── qwen.py           In-process Transformers adapter
│   └── vllm.py           OpenAI-compatible vLLM adapter
└── tools/
    ├── coding.py         read, bash, edit, and write
    └── web_search.py     DuckDuckGo HTML search
```

Both model adapters implement the same interface:

```python
complete(messages, tools) -> assistant_message
```

The `Agent` therefore does not need to know whether inference happens in the
same process or behind an HTTP server.

## Agent loop

`Agent.run()` creates a system message from `AGENTS.md`, appends the user task,
and builds the tool schemas once. Each step then:

1. Sends the complete message history and tool schemas to the model.
2. Appends the returned assistant message.
3. Returns the assistant content if there are no tool calls.
4. Otherwise executes every requested tool and appends its result.
5. Repeats until an answer is produced or `max_steps` is exceeded.

Tool results use this internal shape:

```python
{
    "role": "tool",
    "tool_call_id": "call_...",
    "name": "read",
    "content": "{\"ok\": true, \"result\": ...}",
}
```

The harness stores tool arguments as Python dictionaries. The vLLM adapter
serializes historical arguments to JSON strings before an API request and
parses returned argument strings back into dictionaries before tool execution.
It also normalizes the vLLM 0.28 `reasoning` response field to the internal
`reasoning_content` field so thinking can be preserved in later turns.

## Tools

The default registry contains:

- `read`: read a UTF-8 file with optional line offset and limit.
- `bash`: execute a Bash command in the current working directory.
- `edit`: replace one exact, uniquely matching block in a UTF-8 file.
- `write`: create or completely overwrite a UTF-8 file.
- `web_search`: query DuckDuckGo and return titles, URLs, and snippets.

Text and shell output is truncated at 50 KiB before it is returned to the
model. `web_search` returns at most ten results and does not require an API key,
but DuckDuckGo's HTML endpoint is not a guaranteed stable production API.

The coding tools run with the same filesystem and process permissions as
`main.py`. Treat model-generated shell commands and file writes as trusted code
only in a controlled environment. Runtime instructions ask the model to place
temporary scripts, downloads, and intermediate artifacts under `./tmp/`.

## Configuration

The main defaults are defined near the top of `main.py`:

```python
MODEL_PATH = "/data4/haibo/weights/Qwen3.8-27B"
BACKEND = "vllm"  # "vllm" or "transformers"
VLLM_MODEL_NAME = "qwen3.8-27b"
VLLM_BASE_URL = "http://127.0.0.1:8000/v1"

ENABLE_THINKING = True
REASONING_EFFORT = "xhigh"  # "xhigh", "medium", or "low"
SHOW_RAW_TRACE = True
```

The local model path and the vLLM served name have different purposes:

- `MODEL_PATH` locates the checkpoint and its Qwen chat template.
- `VLLM_MODEL_NAME` must match the server's `--served-model-name` value.
- `VLLM_BASE_URL` points to the OpenAI-compatible API.

Command-line options override the task, local model path, step limit, and output
limit:

```bash
python main.py \
    --prompt "Inspect this repository and summarize its architecture." \
    --model /data4/haibo/weights/Qwen3.8-27B \
    --max-steps 20 \
    --max-new-tokens 8192
```

## Run with vLLM

Use a separate environment for the model server so its PyTorch and CUDA
dependencies do not replace packages in `pi_agent`:

```bash
conda create -n vllm python=3.12 -y
conda activate vllm
python -m pip install --upgrade pip uv
uv pip install vllm --torch-backend=auto
```

Start Qwen3.8-27B and keep this terminal running:

```bash
CUDA_VISIBLE_DEVICES=0 vllm serve /data4/haibo/weights/Qwen3.8-27B \
    --served-model-name qwen3.8-27b \
    --host 127.0.0.1 \
    --port 8000 \
    --dtype bfloat16 \
    --tensor-parallel-size 1 \
    --max-model-len 262144 \
    --gpu-memory-utilization 0.90 \
    --reasoning-parser qwen3 \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder
```

Verify that the service is ready:

```bash
curl http://127.0.0.1:8000/v1/models
```

In another terminal, run the Agent client:

```bash
conda create -n pi_agent python=3.12 -y
conda activate pi_agent
cd /data4/haibo/code/pi_qwen
pip install -r requirements.txt
python main.py
```

The client does not load model weights. When tracing is enabled it only loads
the local processor/tokenizer so it can render the same Qwen chat template used
by the server.

## Run with Transformers

Change the backend in `main.py`:

```python
BACKEND = "transformers"
```

Then run:

```bash
conda activate pi_agent
cd /data4/haibo/code/pi_qwen
python main.py --max-new-tokens 8192
```

The current Transformers adapter requests `flash_attention_3`, so that package
must be installed in `pi_agent`. The optional linear-attention packages listed
in `requirements.txt` remove the Qwen fallback warning and may improve speed.

## Thinking and reasoning

Qwen3.8 supports thinking mode and three reasoning-effort levels:

- `xhigh`: adds an instruction encouraging thorough analysis.
- `medium`: uses the template's balanced baseline behavior.
- `low`: adds an instruction encouraging brief, focused reasoning.

`REASONING_EFFORT` only affects the prompt while `ENABLE_THINKING` is true. It
is a soft behavioral control, not a hard token budget. `max_new_tokens` or the
vLLM API's `max_tokens` remains the generation limit.

With `preserve_thinking=True`, historical reasoning is included in later model
turns. This can improve plan continuity in multi-step tasks, while also
increasing context usage.

## Trace output

Both backends print immediately after each completed model turn and avoid
repeating the common prefix from earlier turns.

The Transformers adapter decodes its actual input and output token IDs with
`skip_special_tokens=False`. Its trace therefore includes raw markers such as
`<|im_start|>`, `<|im_end|>`, `<think>`, and `<tool_call>`.

The vLLM adapter has no direct access to the remote engine's input tensor. It
uses the local Qwen processor with `apply_chat_template(tokenize=False)` to
print the template-rendered text sent conceptually to the model. This includes
the reasoning instruction, tool schemas, `AGENTS.md`, message history, tool
calls, and tool results.

The vLLM output section is reconstructed from the parsed API response. It
preserves reasoning, content, and structured tool calls, but it is not a
byte-for-byte copy of the model's pre-parser output whitespace.

## Basic checks

The repository currently has no automated test suite. Syntax can be checked
without loading the model:

```bash
python -m py_compile \
    main.py \
    agent_core/*.py \
    models/*.py \
    tools/*.py
```

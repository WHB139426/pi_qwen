# Minimal Qwen Agent Loop

A small, non-interactive Python agent harness for Qwen3.8. The harness owns
message persistence, context construction, output parsing, and tool execution;
a separately deployed vLLM server only performs text generation.

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
│   ├── conversation.py   JSON-backed conversation storage
│   ├── loop.py           Model-independent agent loop
│   └── types.py          Message, Tool, TextGenerator, and ChatProtocol types
├── backends/
│   └── vllm.py           vLLM raw Completions client
├── protocols/
│   └── qwen.py           Qwen context rendering and output parsing
└── tools/
    ├── coding.py         read, bash, edit, and write
    └── web_search.py     DuckDuckGo HTML search
```

The vLLM adapter is deliberately unaware of messages and tools. It implements
the minimal text-generation interface:

```python
generate(context: str) -> raw_text
```

`QwenProtocol` owns the model-family-specific boundary:

```python
render(messages, tools) -> context
parse(raw_text) -> assistant_message
```

The `Agent` constructs the complete context before inference, while vLLM only
tokenizes and generates from the supplied text.

## Agent loop

`Agent.run()` creates a system message from `AGENTS.md`, appends the user task,
and builds the tool schemas once. Each step then:

1. Reloads the complete message history from JSON.
2. Uses `QwenProtocol` to render messages, tools, thinking settings, and the
   Qwen chat template into one text context.
3. Sends only that context to the selected text-generation backend.
4. Parses the raw text into reasoning, content, and tool calls locally.
5. Saves the assistant message, executes any tools, and saves their results.
6. Repeats until an answer is produced or `max_steps` is exceeded.

`main.py` configures `./tmp/conversation.json` as the conversation store. The
loop writes every assistant message and tool result immediately, then reloads
the complete file before each model call. The JSON file is therefore the
authoritative cross-turn history; Python still creates a temporary list when it
deserializes the file for a model request.

Each `main.py` run starts a new conversation and overwrites the previous file.
The final record remains available after the process exits. `tmp/*` is ignored
by Git, and the store uses a temporary sibling file plus an atomic replace to
avoid leaving partially written JSON after an interrupted write.

Tool results use this internal shape:

```python
{
    "role": "tool",
    "tool_call_id": "call_...",
    "name": "read",
    "content": "{\"ok\": true, \"result\": ...}",
}
```

The harness stores tool arguments as Python dictionaries. `QwenProtocol`
renders those dictionaries into Qwen's XML tool-call format and parses the
model's XML back into dictionaries before execution. Reasoning is likewise
parsed locally and stored as `reasoning_content` for later turns.

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
VLLM_MODEL_NAME = "qwen3.8-27b"
VLLM_BASE_URL = "http://127.0.0.1:8000/v1"

ENABLE_THINKING = True
REASONING_EFFORT = "xhigh"  # "xhigh", "medium", or "low"
TRACE_PATH = Path("./tmp/trace.txt")
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
    --gpu-memory-utilization 0.90
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

The client does not load model weights. `QwenProtocol` loads only the local
tokenizer and renders the complete prompt before calling vLLM's
`/v1/completions` endpoint. The request contains `prompt`, sampling parameters,
and the served model name; it contains no `messages`, `tools`, `tool_choice`, or
`chat_template_kwargs` fields.

## Thinking and reasoning

Qwen3.8 supports thinking mode and three reasoning-effort levels:

- `xhigh`: adds an instruction encouraging thorough analysis.
- `medium`: uses the template's balanced baseline behavior.
- `low`: adds an instruction encouraging brief, focused reasoning.

`REASONING_EFFORT` is consumed by `QwenProtocol` while it renders the prompt and
only has an effect while `ENABLE_THINKING` is true. It is a soft behavioral
control, not a hard token budget. `max_new_tokens` or the vLLM API's
`max_tokens` remains the generation limit.

With `preserve_thinking=True`, historical reasoning is included in later model
turns. This can improve plan continuity in multi-step tasks, while also
increasing context usage.

## Trace output

The Agent writes tracing to `./tmp/trace.txt` instead of the terminal. After
each generation it overwrites the file with the complete rendered context plus
the raw model output:

```python
trace_path.write_text(context + raw_output, encoding="utf-8")
```

The newest context already contains all earlier messages, reasoning, tool calls,
and tool results, so the trace does not need turn labels or incremental-prefix
bookkeeping. The write happens before local output parsing, which preserves the
raw response even if parsing fails. Set `trace_path=None` when constructing the
Agent to disable tracing.

## Basic checks

The repository currently has no automated test suite. Syntax can be checked
without loading the model:

```bash
python -m py_compile \
    main.py \
    agent_core/*.py \
    backends/*.py \
    protocols/*.py \
    tools/*.py
```

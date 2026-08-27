# Minimal Python Agent Harness

A small Python agent harness inspired by [pi](https://github.com/earendil-works/pi).
It keeps the core loop explicit: a model generates text, the harness parses tool
calls, executes them, appends the results, and continues until the model returns
a final answer.

## Design

- The agent loop is independent of any particular model family or inference
  server.
- `conversation.json` is the harness's model-independent message protocol.
- Model protocols translate between those messages and model-specific text
  formats. Qwen and GLM currently have separate renderers and parsers.
- The vLLM backend receives a fully rendered text context and streams raw text
  back. It does not construct messages or tool definitions.
- Tools use one small interface and can be added without changing the loop.
- The CLI and Web application are clients around the same agent core.

Supporting a model with a different chat template or tool-call syntax should
mainly require a new protocol implementation rather than a new agent loop.

## Scope

This repository is for learning and research, not production deployment. It now
includes an interactive CLI and a lightweight multi-user Web application, but
intentionally omits several product-level features:

- context compaction, summarization, and automatic token-budget management;
- pause, resume, cancellation, and mid-tool human approval;
- an operating-system sandbox for model tools;
- a production database, persistent login sessions, rate limiting, CSRF
  protection, and administrative controls.

`AGENTS.md` instructs the model to keep filesystem work under `./tmp/`, but this
is a prompt-level policy rather than an OS security boundary. The tools run with
the same filesystem and process permissions as the harness. Use the project only
in a controlled environment.

## Project Structure

```text
pi_qwen/
├── AGENTS.md               # Runtime instructions supplied to the model
├── main.py                 # Model configuration, assembly, and interactive CLI
├── web.py                  # Authentication, conversations, SSE UI, and artifacts
├── agent_core/             # Model-independent agent components
│   ├── __init__.py         # Public agent-core exports
│   ├── conversation.py     # JSON conversation persistence
│   ├── loop.py             # Generate, parse, execute tools, and repeat
│   ├── types.py            # Shared protocols, messages, tools, and result types
│   └── usage.py            # Per-turn and cumulative token-usage persistence
├── backends/
│   ├── __init__.py         # Public backend exports
│   └── vllm.py             # Streaming vLLM Completions API backend
├── protocols/
│   ├── __init__.py         # Public protocol exports
│   ├── qwen.py             # Qwen context rendering and output parsing
│   └── glm.py              # GLM context rendering and output parsing
├── tools/
│   ├── __init__.py         # Default tool registry
│   ├── coding.py           # read, bash, edit, and write
│   └── web_search.py       # DuckDuckGo search
├── requirements.txt        # Python client and Web dependencies
└── tmp/                    # Git-ignored runtime state and model workspace
```

The Web application stores data per user and conversation:

```text
tmp/
├── web_users.json
└── users/<username>/conversations/<timestamp_uuid>/
    ├── conversation.json
    ├── metadata.json
    ├── usage.json
    ├── trace.txt
    └── artifacts/
        ├── downloads/      # User uploads and files downloaded by the model
        └── outputs/        # Files produced for the user
```

## Supported Models

- [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B)
- [zai-org/GLM-5.3-Flash](https://huggingface.co/zai-org/GLM-5.3-Flash)
- [vLLM](https://github.com/vllm-project/vllm) as the inference server

Select the active family in `main.py`:

```python
MODEL_FAMILY = "glm"  # "qwen" or "glm"
```

Each entry in `MODEL_CONFIGS` defines the tokenizer/checkpoint path, served
model name, context window, protocol options, and vLLM sampling options. A Hugging
Face identifier or a local checkpoint path can be used for `model_path`.
`served_model_name` must match the server's `--served-model-name` value.

## Tools

- `read`: read a UTF-8 text file with an optional line range;
- `bash`: execute a Bash command and return its exit code and output;
- `edit`: replace one exact, uniquely matching text block;
- `write`: create or overwrite a UTF-8 text file;
- `web_search`: search the Web through DuckDuckGo.

## Installation

Separate environments are recommended for the vLLM server and harness client.

Install the client:

```bash
conda create -n pi_agent python=3.12 -y
conda activate pi_agent
git clone https://github.com/WHB139426/pi_qwen.git
cd pi_qwen
pip install -r requirements.txt
```

For a standard vLLM installation suitable for Qwen:

```bash
conda create -n vllm python=3.12 -y
conda activate vllm
python -m pip install --upgrade pip uv
uv pip install -U vllm --pre \
    --extra-index-url https://wheels.vllm.ai/nightly/cu130 \
    --extra-index-url https://download.pytorch.org/whl/cu130 \
    --index-strategy unsafe-best-match
```

The exact vLLM build must be compatible with the host NVIDIA driver and CUDA
runtime.

## Model Servers on Four H200 GPUs

### Qwen3.8-27B

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3 vllm serve Qwen/Qwen3.8-27B \
    --served-model-name qwen3.8-27b \
    --host 127.0.0.1 \
    --port 8000 \
    --dtype bfloat16 \
    --tensor-parallel-size 4 \
    --max-model-len 262144 \
    --gpu-memory-utilization 0.90
```

### GLM-5.3-Flash

GLM-5.3-Flash uses the dedicated vLLM image below. Replace
`/path/to/GLM-5.3-Flash` with a local copy of
[`zai-org/GLM-5.3-Flash`](https://huggingface.co/zai-org/GLM-5.3-Flash).

```bash
sudo docker run --rm \
    --name glm53-vllm \
    --gpus '"device=0,1,2,3"' \
    --ipc=host \
    --network host \
    -e VLLM_ENGINE_READY_TIMEOUT_S=3600 \
    -v /path/to/GLM-5.3-Flash:/model:ro \
    vllm/vllm-openai:glm53-flash \
    /model \
    --served-model-name glm-5.3-flash \
    --host 127.0.0.1 \
    --port 8000 \
    --dtype bfloat16 \
    --tensor-parallel-size 4 \
    --max-model-len 1048576 \
    --max-num-seqs 16 \
    --gpu-memory-utilization 0.95 \
    --no-enable-flashinfer-autotune
```

The API is expected at `http://127.0.0.1:8000/v1`. Stop a foreground server or
container with `Ctrl+C`.

## Interactive CLI

After starting the matching vLLM server and selecting `MODEL_FAMILY`:

```bash
conda activate pi_agent
python main.py
```

CLI commands:

- `/new`: clear the current conversation;
- `/exit`: leave the CLI.

An optional initial prompt can be supplied while keeping the session interactive:

```bash
python main.py --prompt "Search for today's important AI news and summarize it."
```

The CLI stores its current conversation, usage state, and latest raw trace in:

```text
tmp/conversation.json
tmp/conversation_usage.json
tmp/trace.txt
```

`RESUME_CONVERSATION` in `main.py` controls whether a new CLI process resumes or
resets the saved conversation. The terminal reports the latest turn usage,
cumulative conversation usage, and current context-window occupancy.

## Web Application

Start the Web server after the matching vLLM server is ready:

```bash
conda activate pi_agent
python web.py
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765), register an account, and
create a conversation. There is no default account. Registered users persist in
`tmp/web_users.json`; login sessions are kept only in memory and are cleared when
`web.py` restarts.

The Web application currently provides:

- multiple users and multiple persistent conversations per user;
- concurrent execution across different conversations and serialization within
  one conversation;
- token-by-token SSE output with separate, collapsible reasoning and tool traces;
- Markdown rendering for final answers;
- low, high, and max GLM reasoning controls;
- per-turn, cumulative conversation, and current-context token statistics;
- drag-and-drop or file-picker uploads, with a 512 MB limit per file;
- authenticated artifact downloads and collision-safe filenames;
- per-conversation `downloads/` and `outputs/` directories.

Successful uploads are appended to `conversation.json` as user-role file events,
so the model sees the exact filename and path on its next turn without adding a
dynamic upload inventory to the system prompt. Files generated by the model
appear in the attachment list after the turn completes.

The server intentionally binds to `127.0.0.1`. Exposing it through a tunnel or
reverse proxy makes the registration page publicly reachable and should only be
done in a controlled research environment.

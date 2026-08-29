# Minimal Python Agent Harness

A small Python agent harness inspired by [pi](https://github.com/earendil-works/pi),
built for learning and research. The implementation keeps the essential agent
loop visible: render context, generate model output, parse tool calls, execute
tools, append results, and continue until the model returns a final answer.

## Design

- The agent loop operates on a model-independent JSON message format.
- Model protocols own chat-template rendering and tool-call parsing. Qwen and
  GLM use separate protocol implementations without duplicating the loop.
- The vLLM backend only performs generation from protocol-prepared input. Plain
  text uses the Completions API; multimodal turns use the Chat Completions API.
- Tools share a small interface and can return either persistent results or
  transient messages that are visible for one generation only.
- Skills are repository-owned instruction files loaded on demand. Their names
  and descriptions are injected into the system prompt, while their complete
  instructions are loaded only when a matching task requires them.
- The CLI and Web application are clients around the same agent core.

Supporting a model with a different chat template or tool-call syntax should
normally require a new protocol implementation, not a new agent loop.

## Scope

This repository is intended for learning and research rather than production
deployment. It includes a multi-turn CLI and a lightweight multi-user Web
application, but intentionally omits product-level features such as:

- context compaction, summarization, and automatic token-budget management;
- cancellation, pause/resume, mid-tool approval, and recovery of active jobs;
- an operating-system sandbox for model-executed tools;
- a production database, durable login sessions, password recovery, rate
  limiting, CSRF protection, audit logging, and administrative controls.

`AGENTS.md` defines a strict per-conversation workspace for the model, but this
is still a prompt-level policy. The coding tools execute with the operating-system
permissions of the harness process. Run the project only in a controlled
environment.

## Project Structure

```text
pi_qwen/
├── AGENTS.md                   # Dynamic runtime policy and workspace template
├── main.py                     # Model selection, agent assembly, and CLI
├── web.py                      # Authentication, conversations, streaming UI, and files
├── agent_core/
│   ├── __init__.py             # Public core exports
│   ├── conversation.py         # JSON conversation persistence
│   ├── loop.py                 # Model/tool execution loop
│   ├── skills.py               # Skill discovery, metadata validation, and loading
│   ├── types.py                # Messages, protocols, tools, multimodal input, and results
│   └── usage.py                # Per-turn and cumulative token usage
├── backends/
│   ├── __init__.py             # Public backend exports
│   └── vllm.py                 # Streaming vLLM client
├── protocols/
│   ├── __init__.py             # Public protocol exports
│   ├── qwen.py                 # Qwen rendering, multimodal conversion, and parsing
│   └── glm.py                  # GLM rendering, multimodal conversion, and parsing
├── tools/
│   ├── __init__.py             # Default tool registry
│   ├── coding.py               # read, bash, edit, and write
│   ├── skill.py                # Dynamic skill loader and system-prompt catalog
│   ├── view_image.py           # Workspace-scoped transient image inspection
│   └── web_search.py           # DuckDuckGo Web search
├── skills/
│   ├── financial-analysis/     # Finance research workflow
│   ├── html-slide-deck/        # Self-contained HTML presentation workflow
│   ├── ppt-creation/           # Native PowerPoint workflow
│   └── travel-planning/        # Travel research and itinerary workflow
├── requirements.txt            # Harness and Web dependencies
└── tmp/                        # Git-ignored runtime state
```

The Web application stores each conversation in its own workspace:

```text
tmp/
├── web_users.json
└── users/<username>/conversations/<timestamp_uuid>/
    ├── conversation.json
    ├── metadata.json
    ├── usage.json
    ├── trace.txt
    └── tmp/                    # The model's only permitted filesystem workspace
        └── artifacts/
            ├── downloads/     # User uploads and model downloads
            └── outputs/       # Final files exposed in the Web attachment list
```

At agent creation time, `{{WORKSPACE}}` in `AGENTS.md` is replaced with the
conversation-specific `tmp/` path. The available skill catalog is injected in
the same way.

## Supported Models

- [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B)
- [zai-org/GLM-5.3-Flash](https://huggingface.co/zai-org/GLM-5.3-Flash)
- [vLLM](https://github.com/vllm-project/vllm) as the inference server

Both configured protocols support text, image, and video messages through a
vLLM OpenAI-compatible server. Select the active family in `main.py`:

```python
MODEL_FAMILY = "glm"  # "qwen" or "glm"
```

`MODEL_CONFIGS` contains each model's tokenizer path, served model name, context
window, protocol settings, and sampling options. GLM runs with `max` reasoning
effort and Qwen with `xhigh` reasoning effort by default.

## Tools

- `read`: read a UTF-8 text file with an optional line range;
- `bash`: execute a Bash command and return its exit code and output;
- `edit`: replace one exact, uniquely matching text block;
- `write`: create or overwrite a UTF-8 text file;
- `web_search`: search the Web through DuckDuckGo;
- `skill`: load one registered specialized workflow;
- `view_image`: visually inspect an image inside the current conversation
  workspace.

`view_image` attaches the selected image to the next model generation only. The
tool result is persisted, but the temporary image message is not written to
`conversation.json`, so later turns do not keep the image in the context or
repeatedly perform visual processing. The same tool can inspect uploads,
downloaded images, generated graphics, charts, screenshots, and rendered PDF,
HTML, or presentation pages.

## Skills

The current skill registry includes:

- `financial-analysis`
- `html-slide-deck`
- `ppt-creation`
- `travel-planning`

Each skill lives at `skills/<name>/SKILL.md`. The harness validates its metadata,
lists its name and description in the system prompt, and exposes the complete
instructions through the `skill` tool. Skills do not grant additional filesystem
permissions and remain subordinate to the user's requested output and the
conversation workspace boundary.

## Installation

Separate environments are recommended for the vLLM server and harness client.

Install the harness:

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

The exact vLLM build must be compatible with the host NVIDIA driver, CUDA
runtime, model architecture, and chat template.

## Model Servers on Four H200 GPUs

The examples below assume the repository is the current working directory. The
media path passed to vLLM must be the absolute path to this repository's
`tmp/users` directory.

### Qwen3.8-27B

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3 vllm serve Qwen/Qwen3.8-27B \
    --served-model-name qwen3.8-27b \
    --host 127.0.0.1 \
    --port 8000 \
    --dtype bfloat16 \
    --tensor-parallel-size 4 \
    --max-model-len 1010000 \
    --hf-overrides '{"text_config": {"max_position_embeddings": 1010000}}' \
    --allowed-local-media-path "$PWD/tmp/users" \
    --limit-mm-per-prompt '{"image": 100, "video": 100}' \
    --gpu-memory-utilization 0.90
```

### GLM-5.3-Flash

GLM-5.3-Flash uses the dedicated vLLM image. Replace
`/path/to/GLM-5.3-Flash` with a local copy of
[`zai-org/GLM-5.3-Flash`](https://huggingface.co/zai-org/GLM-5.3-Flash), and
replace `/absolute/path/to/pi_qwen` with the repository's absolute path.

```bash
sudo docker run --rm \
    --name glm53-vllm \
    --gpus '"device=0,1,2,3"' \
    --ipc=host \
    --network host \
    -e VLLM_ENGINE_READY_TIMEOUT_S=3600 \
    -v /path/to/GLM-5.3-Flash:/model:ro \
    -v /absolute/path/to/pi_qwen/tmp/users:/absolute/path/to/pi_qwen/tmp/users:ro \
    vllm/vllm-openai:glm53-flash \
    /model \
    --served-model-name glm-5.3-flash \
    --host 127.0.0.1 \
    --port 8000 \
    --dtype bfloat16 \
    --tensor-parallel-size 4 \
    --max-model-len 1048576 \
    --allowed-local-media-path /absolute/path/to/pi_qwen/tmp/users \
    --limit-mm-per-prompt '{"image": 100, "video": 100}' \
    --max-num-seqs 16 \
    --gpu-memory-utilization 0.95 \
    --no-enable-flashinfer-autotune
```

The API is expected at `http://127.0.0.1:8000/v1`. Stop a foreground server or
container with `Ctrl+C`.

Do not enable vLLM's automatic tool-choice parser for this harness. The model
must return its raw tool-call text so the selected protocol can parse it.

## Interactive CLI

Start the matching vLLM server, select `MODEL_FAMILY`, and run:

```bash
conda activate pi_agent
python main.py
```

CLI commands:

- `/new`: reset the saved conversation;
- `/exit`: leave the CLI.

An optional first message can be supplied while keeping the session interactive:

```bash
python main.py --prompt "Search for today's important AI news and summarize it."
```

The CLI stores its conversation, cumulative usage, and latest rendered trace in
`tmp/conversation.json`, `tmp/conversation_usage.json`, and `tmp/trace.txt`.
`RESUME_CONVERSATION` controls whether a new process resumes or resets saved
state. The terminal reports per-turn usage, cumulative usage, and current
context-window occupancy.

## Web Application

After the selected vLLM server is ready:

```bash
conda activate pi_agent
python web.py
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Registration is required;
there is no default user. Usernames contain 3-32 lowercase letters, numbers, or
underscores. Passwords must be non-empty and are stored as salted PBKDF2 hashes.
Login sessions are held only in memory and are cleared when `web.py` restarts.

The Web application provides:

- multiple users and multiple persistent conversations per user;
- a conversation-history sidebar with creation and deletion controls;
- concurrent execution across conversations and serialized execution within a
  single conversation;
- token-by-token Server-Sent Events streaming;
- distinct final-answer, reasoning, intermediate-content, tool-call, and
  tool-result presentation, with secondary traces collapsible;
- Markdown rendering for assistant content;
- per-turn, cumulative conversation, and current-context token statistics;
- drag-and-drop, file-picker, and pasted image/video uploads;
- multimodal image and video input for both configured model families;
- authenticated, collision-safe file delivery with a 512 MiB per-file upload
  limit;
- output attachments listed below the composer using only their filenames;
- a styled confirmation dialog for permanent conversation deletion.

Uploads are stored under the current conversation's `artifacts/downloads/`
directory. An upload notification is appended as a user message so the model
knows the exact stored path; image and video uploads are represented as
multimodal message content. Final files intended for download must be written to
`artifacts/outputs/`, which is the only directory shown in the Web attachment
list.

The Web server binds to `127.0.0.1`. A tunnel or reverse proxy can expose it to
other machines, but doing so also exposes account registration and the agent's
powerful tools. Use public access only in a controlled research environment.

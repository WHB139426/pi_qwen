# Minimal Qwen Agent

A minimal Python agent harness inspired by [**pi**](https://github.com/earendil-works/pi). It demonstrates the essential
agent loop: the model decides whether to call a tool, the harness executes it
and returns the result, and the model continues until it produces a final
answer.

## Design Philosophy

The project is designed to remain small, explicit, and replaceable:

- The agent loop handles message flow, tool execution, and iteration without
  depending on a particular model.
- `conversation.json` stores the harness's model-independent message format.
- A model protocol translates between those messages and a model-specific chat
  template. `QwenProtocol` currently renders and parses the Qwen format.
- The inference backend receives a complete text context and returns raw text.
  It does not construct messages or tools.
- Tools share one small interface and can be added or removed independently.

Supporting a model with a different tool-calling format should mainly require a
new protocol implementation, while leaving the core agent loop unchanged.

## Scope and Limitations

This repository is intended for learning and research. It deliberately focuses
on the smallest useful agent loop rather than a production-ready agent product.
It currently does not provide:

- A web, desktop, or terminal user interface.
- Interactive multi-turn chat or streaming output.
- Context compaction, summarization, or automatic token-budget management.
- Task interruption, pause, resume, cancellation, or cross-run recovery.
- Human-in-the-loop interaction or approval before tool execution.
- Tool sandboxing, permission isolation, or other production security controls.

These features can be built around the core loop later, but are kept out of the
current implementation so that its essential architecture remains easy to
study.

## Project Structure

```text
pi_qwen/
├── AGENTS.md              # Runtime system instructions for the model
├── main.py                # CLI configuration and dependency assembly
├── agent_core/            # Model-independent agent components
│   ├── __init__.py        # Public agent-core exports
│   ├── conversation.py    # JSON-backed conversation persistence
│   ├── loop.py            # Core generate, tool execution, and repeat loop
│   └── types.py           # Shared messages, interfaces, tools, and results
├── backends/              # Text-generation backends
│   ├── __init__.py        # Public backend exports
│   └── vllm.py            # Raw generation through the vLLM Completions API
├── protocols/             # Model-family context adapters
│   ├── __init__.py        # Public protocol exports
│   └── qwen.py            # Qwen chat-template rendering and output parsing
├── tools/                 # Tools exposed to the model
│   ├── __init__.py        # Default tool registry
│   ├── coding.py          # read, bash, edit, and write tools
│   └── web_search.py      # DuckDuckGo web search tool
├── requirements.txt       # Agent-client Python dependencies
├── README.md              # Project overview and usage
└── tmp/                   # Git-ignored conversations and raw traces
```

## Supported Model

The current implementation supports:

- [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B)
- [zai-org/GLM-5.3-Flash](https://huggingface.co/zai-org/GLM-5.3-Flash)
- vLLM as the inference backend

Use the official Hugging Face model identifier for both tokenizer loading and
vLLM deployment:

```python
MODEL_PATH = "Qwen/Qwen3.8-27B"
VLLM_MODEL_NAME = "qwen3.8-27b"
VLLM_BASE_URL = "http://127.0.0.1:8000/v1"
```

`VLLM_MODEL_NAME` must match the value passed to
`--served-model-name`.

## Tools

- `read`: Read a UTF-8 text file.
- `bash`: Execute a Bash command.
- `edit`: Replace one uniquely matching text block in a file.
- `write`: Create or overwrite a UTF-8 text file.
- `web_search`: Search the web through DuckDuckGo.

The tools run with the same filesystem and process permissions as `main.py`.
There is no additional sandbox or approval layer, so run the agent only in a
controlled environment.

## Installation

Separate environments are recommended for the vLLM server and agent client.

Install the vLLM server:

```bash
conda create -n vllm python=3.12 -y
conda activate vllm
python -m pip install --upgrade pip uv
uv pip install -U vllm --pre \
    --extra-index-url https://wheels.vllm.ai/nightly/cu130 \
    --extra-index-url https://download.pytorch.org/whl/cu130 \
    --index-strategy unsafe-best-match
```

Install the agent client:

```bash
conda create -n pi_agent python=3.12 -y
conda activate pi_agent
git clone <repository-url>
cd pi_qwen
pip install -r requirements.txt
```

## Running on Four H200 GPUs

The model is deployed with tensor parallelism across four NVIDIA H200 GPUs:

```bash
conda activate vllm
CUDA_VISIBLE_DEVICES=0,1,2,3 vllm serve Qwen/Qwen3.8-27B \
    --served-model-name qwen3.8-27b \
    --host 127.0.0.1 \
    --port 8000 \
    --dtype bfloat16 \
    --tensor-parallel-size 4 \
    --max-model-len 262144 \
    --gpu-memory-utilization 0.90
```

### GLM-5.3-Flash Server

GLM-5.3-Flash currently requires its dedicated vLLM Docker image. The following
command serves local FP8 weights on four H200 GPUs with the native 1M-token
context window:

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

Replace `/path/to/GLM-5.3-Flash` with the local checkpoint directory for
[`zai-org/GLM-5.3-Flash`](https://huggingface.co/zai-org/GLM-5.3-Flash).
The server name used by API clients is `glm-5.3-flash`. Stop the foreground
container with `Ctrl+C`.

In another terminal, run the agent:

```bash
conda activate pi_agent
cd pi_qwen
python main.py \
    --model Qwen/Qwen3.8-27B \
    --prompt "Search for today's important AI news and summarize it."
```

To run the task configured in `main.py`:

```bash
python main.py
```

The final answer is printed to the terminal. The structured conversation and
complete model trace are written to:

```text
./tmp/conversation.json
./tmp/trace.txt
```

The terminal also reports cumulative token usage across all model calls in the
task: input tokens, output tokens, and their sum. Input usage follows the API
counting convention, so repeated conversation history is included on every
agent step.

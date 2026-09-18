"""Non-interactive example for the minimal agent harness."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from agent_core import Agent, AgentResult, JsonConversationStore, JsonUsageStore, TokenUsage
from backends import VLLMBackend, VLLMOptions
from protocols import DeepSeekProtocol, GLMProtocol, QwenProtocol
from tools import TOOLS, make_view_image_tool
from tools.skill import render_skill_catalog

"""
ngrok http 127.0.0.1:8765
"""

"""
vllm start on 4 H200 (141GB) GPU:

Qwen3.8-27B:

CUDA_VISIBLE_DEVICES=0,1 vllm serve /data4/haibo/weights/Qwen3.8-27B \
    --served-model-name qwen3.8-27b \
    --host 127.0.0.1 \
    --port 8000 \
    --dtype bfloat16 \
    --tensor-parallel-size 2 \
    --max-model-len 1010000 \
    --hf-overrides '{"text_config": {"max_position_embeddings": 1010000}}' \
    --allowed-local-media-path /data4/haibo/code/pi_qwen/tmp/users \
    --limit-mm-per-prompt '{"image": 100, "video": 100}' \
    --enable-prefix-caching \
    --enable-prompt-tokens-details \
    --gpu-memory-utilization 0.90

CUDA_VISIBLE_DEVICES=2 vllm serve /data4/haibo/weights/Qwen3.8-27B \
    --served-model-name qwen3.8-27b \
    --host 127.0.0.1 \
    --port 8000 \
    --dtype bfloat16 \
    --tensor-parallel-size 1 \
    --max-model-len 1010000 \
    --hf-overrides '{"text_config": {"max_position_embeddings": 1010000}}' \
    --allowed-local-media-path /data4/haibo/code/pi_qwen/tmp/users \
    --limit-mm-per-prompt '{"image": 100, "video": 100}' \
    --enable-prefix-caching \
    --enable-prompt-tokens-details \
    --gpu-memory-utilization 0.90

Qwen3.8-Flash-Next:

sudo docker run --rm \
    --name qwen38-flash-next-vllm \
    --gpus '"device=2,3"' \
    --ipc=host \
    --network host \
    -e VLLM_ENGINE_READY_TIMEOUT_S=3600 \
    -e VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 \
    -e VLLM_PLE_CPU_OFFLOAD=1 \
    -v /data4/haibo/weights/Qwen3.8-Flash-Next-FP8:/model:ro \
    -v /data4/haibo/code/pi_qwen/tmp/users:/data4/haibo/code/pi_qwen/tmp/users:ro \
    vllm/vllm-openai:qwen38-flash-next \
    /model \
    --served-model-name qwen3.8-flash-next \
    --host 127.0.0.1 \
    --port 8000 \
    --tensor-parallel-size 2 \
    --max-model-len 1000000 \
    --hf-overrides '{"rope_parameters":{"rope_type":"yarn","factor":4.0,"original_max_position_embeddings":262144}}' \
    --max-num-seqs 16 \
    --gpu-memory-utilization 0.90 \
    --enable-prefix-caching \
    --enable-prompt-tokens-details \
    --no-enable-flashinfer-autotune \
    --allowed-local-media-path /data4/haibo/code/pi_qwen/tmp/users \
    --limit-mm-per-prompt '{"image": 100, "video": 100}'

GLM-5.3-Flash:

sudo docker run --rm \
    --name glm53-vllm \
    --gpus '"device=0,1,2,3"' \
    --ipc=host \
    --network host \
    -e VLLM_ENGINE_READY_TIMEOUT_S=3600 \
    -v /data4/haibo/weights/GLM-5.3-Flash:/model:ro \
    -v /data4/haibo/code/pi_qwen/tmp/users:/data4/haibo/code/pi_qwen/tmp/users:ro \
    vllm/vllm-openai:glm53-flash \
    /model \
    --served-model-name glm-5.3-flash \
    --host 127.0.0.1 \
    --port 8000 \
    --dtype bfloat16 \
    --tensor-parallel-size 4 \
    --max-model-len 1048576 \
    --allowed-local-media-path /data4/haibo \
    --limit-mm-per-prompt '{"image": 100, "video": 100}' \
    --max-num-seqs 16 \
    --gpu-memory-utilization 0.95 \
    --enable-prefix-caching \
    --enable-prompt-tokens-details \
    --no-enable-flashinfer-autotune

DeepSeek-V4.1-Flash:

sudo docker run --rm \
    --name deepseek-v41-flash-vllm \
    --gpus '"device=0,1,2,3"' \
    --privileged \
    --ipc=host \
    --network host \
    --ulimit memlock=-1:-1 \
    -e VLLM_ENGINE_READY_TIMEOUT_S=3600 \
    -v /data4/haibo/weights/DeepSeek-V4.1-Flash:/model:ro \
    -v /data4/haibo/code/pi_qwen/tmp/users:/data4/haibo/code/pi_qwen/tmp/users:ro \
    vllm/vllm-openai:nightly \
    /model \
    --served-model-name deepseek-v4.1-flash \
    --host 127.0.0.1 \
    --port 8000 \
    --tensor-parallel-size 4 \
    --tokenizer-mode deepseek_v41 \
    --engram-config '{"cpu_offload":true}' \
    --kv-cache-dtype fp8 \
    --max-model-len 1048576 \
    --max-num-seqs 16 \
    --max-num-batched-tokens 8192 \
    --gpu-memory-utilization 0.95 \
    --enable-prefix-caching \
    --enable-prompt-tokens-details \
    --no-enable-flashinfer-autotune \
    --mm-encoder-tp-mode data \
    --allowed-local-media-path /data4/haibo/code/pi_qwen/tmp/users \
    --limit-mm-per-prompt '{"image": 100}'

"""

MODEL_FAMILY = "deepseek-v4.1-flash"  # See MODEL_CONFIGS below.

MODEL_CONFIGS = {
    "qwen3.8-27b": {
        "display_name": "Qwen3.8-27B",
        "provider_name": "Qwen",
        "model_url": "https://huggingface.co/Qwen/Qwen3.8-27B",
        "deployment_hardware": "2× NVIDIA H200 GPUs",
        "pricing_per_million_usd": {
            "input": 0.35,
            "output": 2.55,
            "cached_input": 0.05,
        },
        "model_path": "/data4/haibo/weights/Qwen3.8-27B",
        "served_model_name": "qwen3.8-27b",
        "context_window": 1_010_000,
        "supports_multimodal": True,
        "supported_media_types": ("image", "video"),
        "vllm_base_url": "http://127.0.0.1:8000/v1",
        "vllm_options": VLLMOptions(
            max_tokens=128 * 1024,
            do_sample=True,
            temperature=1.0,
            top_p=0.95,
            top_k=20,
        ),
        "protocol": QwenProtocol,
        "protocol_options": {
            "enable_thinking": True,
            "reasoning_effort": "xhigh", # low, medium, xhigh
            "preserve_thinking": True,
        },
    },
    "qwen3.8-flash-next": {
        "display_name": "Qwen3.8-Flash-Next",
        "provider_name": "Qwen",
        "model_url": "https://huggingface.co/Qwen/Qwen3.8-Flash-Next-FP8",
        "deployment_hardware": "2× NVIDIA H200 GPUs",
        "pricing_per_million_usd": {
            "input": 0.15,
            "output": 0.47,
            "cached_input": 0.016,
        },
        "model_path": "/data4/haibo/weights/Qwen3.8-Flash-Next-FP8",
        "served_model_name": "qwen3.8-flash-next",
        "context_window": 1_000_000,
        "supports_multimodal": True,
        "supported_media_types": ("image", "video"),
        "vllm_base_url": "http://127.0.0.1:8000/v1",
        "vllm_options": VLLMOptions(
            max_tokens=128 * 1024,
            do_sample=True,
            temperature=1.0,
            top_p=0.95,
            top_k=20,
        ),
        "protocol": QwenProtocol,
        "protocol_options": {
            "enable_thinking": True,
            "reasoning_effort": "xhigh", # low, medium, xhigh
            "preserve_thinking": True,
        },
    },
    "glm-5.3-flash": {
        "display_name": "GLM-5.3-Flash",
        "provider_name": "Z.ai",
        "model_url": "https://docs.z.ai/guides/vlm/glm-5.3-flash",
        "deployment_hardware": "4× NVIDIA H200 GPUs",
        "pricing_per_million_usd": {
            "input": 0.15,
            "output": 0.50,
            "cached_input": 0.03,
        },
        "model_path": "/data4/haibo/weights/GLM-5.3-Flash",
        "served_model_name": "glm-5.3-flash",
        "context_window": 1024 * 1024,
        "supports_multimodal": True,
        "supported_media_types": ("image", "video"),
        "vllm_base_url": "http://127.0.0.1:8000/v1",
        "vllm_options": VLLMOptions(
            max_tokens=128 * 1024,
            do_sample=True,
            temperature=1.0,
            top_p=0.95,
            top_k=20,
        ),
        "protocol": GLMProtocol,
        "protocol_options": {
            "reasoning_effort": "max", # low, high, max
            "preserve_thinking": True,
        },
    },
    "deepseek-v4.1-flash": {
        "display_name": "DeepSeek-V4.1-Flash",
        "provider_name": "DeepSeek",
        "model_url": "https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash",
        "deployment_hardware": "4× NVIDIA H200 GPUs",
        # No API-equivalent token price is configured for this local checkpoint.
        "pricing_per_million_usd": {
            "input": 0.15,
            "output": 0.6,
            "cached_input": 0.015,
        },
        "model_path": "/data4/haibo/weights/DeepSeek-V4.1-Flash",
        "served_model_name": "deepseek-v4.1-flash",
        "context_window": 1024 * 1024,
        "supports_multimodal": True,
        "supported_media_types": ("image",),
        "vllm_base_url": "http://127.0.0.1:8000/v1",
        "vllm_options": VLLMOptions(
            max_tokens=256 * 1024,
            do_sample=True,
            temperature=1.0,
            top_p=0.95,
            top_k=0,
        ),
        "protocol": DeepSeekProtocol,
        "protocol_options": {
            "reasoning_effort": 100,
            "preserve_thinking": True,
        },
    },
}

MODEL_CONFIG = MODEL_CONFIGS[MODEL_FAMILY]
MODEL_DISPLAY_NAME = str(MODEL_CONFIG["display_name"])
MODEL_PROVIDER_NAME = str(MODEL_CONFIG["provider_name"])
MODEL_INFO_URL = str(MODEL_CONFIG["model_url"])
MODEL_DEPLOYMENT_HARDWARE = str(MODEL_CONFIG["deployment_hardware"])
MODEL_PATH = MODEL_CONFIG["model_path"]
VLLM_MODEL_NAME = MODEL_CONFIG["served_model_name"]
CONTEXT_WINDOW = MODEL_CONFIG["context_window"]
SUPPORTS_MULTIMODAL = MODEL_CONFIG["supports_multimodal"]
SUPPORTED_MEDIA_TYPES = frozenset(MODEL_CONFIG["supported_media_types"])
VLLM_BASE_URL = MODEL_CONFIG["vllm_base_url"]
MODEL_PRICING = MODEL_CONFIG["pricing_per_million_usd"]
INPUT_PRICE_PER_MILLION_USD = float(MODEL_PRICING["input"])
OUTPUT_PRICE_PER_MILLION_USD = float(MODEL_PRICING["output"])
CACHED_INPUT_PRICE_PER_MILLION_USD = float(MODEL_PRICING["cached_input"])


def calculate_usage_cost(usage: TokenUsage) -> float:
    """Estimate cost using separate uncached-input, output, and cache rates."""
    return (
        usage.uncached_input_tokens * INPUT_PRICE_PER_MILLION_USD
        + usage.output_tokens * OUTPUT_PRICE_PER_MILLION_USD
        + usage.cached_input_tokens * CACHED_INPUT_PRICE_PER_MILLION_USD
    ) / 1_000_000

CONVERSATION_PATH = Path("./tmp/conversation.json")
TRACE_PATH = Path("./tmp/trace.txt")
RESUME_CONVERSATION = False

PROMPT = "9月初从上海出发，意大利入，法国出。情侣两人，帮我规划意大利，瑞士，法国的十二日行程，节奏不要太赶，喜欢拍照出片，体验当地人文特色，预算总共4w以内，推荐酒店以及特色美食，但是不要吃太奇怪的食物，考虑天气因素，给我一份具体规划路线，最后计划写成一个.md在./tmp目录下. 在写计划的时候，记得标注新闻、报道、信息以及数据这些东西的来源"
# PROMPT = "解读英伟达最新财报，并由此分析九月份AI相关产业的股价走势，结合历史上的数据，给出你认为比较适合投资的公司，最后计划写成一个.md在 ./tmp目录下。在写计划的时候，记得标注新闻、报道、信息以及数据这些东西的来源"
AGENTS_PATH = Path(__file__).with_name("AGENTS.md")
WORKSPACE_PLACEHOLDER = "{{WORKSPACE}}"
SKILLS_PLACEHOLDER = "{{SKILLS}}"
DEFAULT_WORKSPACE_PATH = Path("./tmp")


def load_agent_instructions(workspace_path: str | Path = DEFAULT_WORKSPACE_PATH) -> str:
    workspace = Path(workspace_path).as_posix().rstrip("/") or "."
    if not Path(workspace_path).is_absolute() and not workspace.startswith("./"):
        workspace = f"./{workspace}"
    workspace = f"{workspace}/"
    template = AGENTS_PATH.read_text(encoding="utf-8")
    if WORKSPACE_PLACEHOLDER not in template:
        raise RuntimeError(f"AGENTS.md is missing {WORKSPACE_PLACEHOLDER}")
    if SKILLS_PLACEHOLDER not in template:
        raise RuntimeError(f"AGENTS.md is missing {SKILLS_PLACEHOLDER}")
    return (
        template.replace(WORKSPACE_PLACEHOLDER, workspace)
        .replace(SKILLS_PLACEHOLDER, render_skill_catalog())
    )


def create_agent(
    *,
    model_path: str = MODEL_PATH,
    max_steps: int = 10000,
    conversation_path: str | Path = CONVERSATION_PATH,
    usage_path: str | Path | None = None,
    trace_path: str | Path = TRACE_PATH,
    workspace_path: str | Path = DEFAULT_WORKSPACE_PATH,
    reasoning_effort: str | int | None = None,
    event_callback: Callable[[dict[str, object]], None] | None = None,
) -> Agent:
    conversation_path = Path(conversation_path)
    if usage_path is None:
        usage_path = conversation_path.with_name(f"{conversation_path.stem}_usage.json")
    protocol_options = dict(MODEL_CONFIG["protocol_options"])
    if reasoning_effort is not None:
        protocol_options["reasoning_effort"] = reasoning_effort
    protocol = MODEL_CONFIG["protocol"](
        model_path,
        **protocol_options,
    )
    model = VLLMBackend(
        VLLM_MODEL_NAME,
        base_url=VLLM_BASE_URL,
        options=MODEL_CONFIG["vllm_options"],
    )
    tools = [*TOOLS, make_view_image_tool(workspace_path)]
    return Agent(
        model,
        tools,
        protocol=protocol,
        system_prompt=load_agent_instructions(workspace_path),
        max_steps=max_steps,
        conversation_store=JsonConversationStore(conversation_path),
        usage_store=JsonUsageStore(usage_path),
        trace_path=trace_path,
        event_callback=event_callback,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local multi-turn agent conversation.")
    parser.add_argument("--prompt", default=None, help="Optional first user message.")
    parser.add_argument("--model", default=MODEL_PATH)
    parser.add_argument("--max-steps", type=int, default=10000)
    args = parser.parse_args()

    agent = create_agent(
        model_path=args.model,
        max_steps=args.max_steps,
    )

    if not RESUME_CONVERSATION:
        agent.reset()

    pending_prompt = args.prompt
    print("Local agent chat. Commands: /new, /exit")

    while True:
        try:
            prompt = pending_prompt if pending_prompt is not None else input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        pending_prompt = None
        prompt = prompt.strip()

        if not prompt:
            continue
        if prompt == "/exit":
            break
        if prompt == "/new":
            agent.reset()
            print("Started a new conversation.")
            continue

        result = agent.run(prompt)
        print_result(result)


def print_result(result: AgentResult) -> None:
    print('=' * 24, 'Final Answer', '=' * 24)
    print(result.answer)
    print('=' * 25, 'Turn Usage', '=' * 25)
    print(f"Input tokens:  {result.usage.input_tokens:,}")
    cache_suffix = "" if result.usage.cache_details_available else " (unavailable)"
    print(f"Cached input: {result.usage.cached_input_tokens:,}{cache_suffix}")
    print(f"Uncached input: {result.usage.uncached_input_tokens:,}")
    print(f"Cache hit rate: {result.usage.cache_hit_rate:.2%}{cache_suffix}")
    print(f"Output tokens: {result.usage.output_tokens:,}")
    print(f"Total tokens:  {result.usage.total_tokens:,}")
    print('=' * 21, 'Conversation Usage', '=' * 21)
    print(f"Input tokens:  {result.conversation_usage.input_tokens:,}")
    conversation_cache_suffix = (
        "" if result.conversation_usage.cache_details_available else " (unavailable)"
    )
    print(
        f"Cached input: {result.conversation_usage.cached_input_tokens:,}"
        f"{conversation_cache_suffix}"
    )
    print(f"Uncached input: {result.conversation_usage.uncached_input_tokens:,}")
    print(
        f"Cache hit rate: {result.conversation_usage.cache_hit_rate:.2%}"
        f"{conversation_cache_suffix}"
    )
    print(f"Output tokens: {result.conversation_usage.output_tokens:,}")
    print(f"Total tokens:  {result.conversation_usage.total_tokens:,}")
    cost_suffix = (
        "" if result.conversation_usage.cache_details_available
        else " (cache data incomplete)"
    )
    print(
        f"Estimated cost: ${calculate_usage_cost(result.conversation_usage):.6f}"
        f"{cost_suffix}"
    )
    context_tokens = result.current_context_tokens
    context_usage = context_tokens / CONTEXT_WINDOW * 100
    print('=' * 22, 'Current Context', '=' * 22)
    print(f"{context_tokens:,}/{CONTEXT_WINDOW:,} ({context_usage:.2f}%)")


if __name__ == "__main__":
    main()

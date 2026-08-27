"""Non-interactive example for the minimal agent harness."""

from __future__ import annotations

import argparse
from pathlib import Path

from agent_core import Agent, JsonConversationStore
from backends import VLLMBackend, VLLMOptions
from protocols import GLMProtocol, QwenProtocol
from tools import TOOLS


"""
vllm start on 4 H200 (141GB) GPU:

Qwen3.8-27B:

CUDA_VISIBLE_DEVICES=0,1,2,3 vllm serve /data4/haibo/weights/Qwen3.8-27B \
    --served-model-name qwen3.8-27b \
    --host 127.0.0.1 \
    --port 8000 \
    --dtype bfloat16 \
    --tensor-parallel-size 4 \
    --max-model-len 262144 \
    --gpu-memory-utilization 0.90

GLM-5.3-Flash:

sudo docker run --rm \
    --name glm53-vllm \
    --gpus '"device=0,1,2,3"' \
    --ipc=host \
    --network host \
    -e VLLM_ENGINE_READY_TIMEOUT_S=3600 \
    -v /data4/haibo/weights/GLM-5.3-Flash:/model:ro \
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

"""

MODEL_FAMILY = "glm"  # qwen, glm

MODEL_CONFIGS = {
    "qwen": {
        "model_path": "/data4/haibo/weights/Qwen3.8-27B",
        "served_model_name": "qwen3.8-27b",
        "context_window": 256 * 1024,
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
            "reasoning_effort": "xhigh",
            "preserve_thinking": True,
        },
    },
    "glm": {
        "model_path": "/data4/haibo/weights/GLM-5.3-Flash",
        "served_model_name": "glm-5.3-flash",
        "context_window": 1024 * 1024,
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
            "reasoning_effort": "max",
            "preserve_thinking": True,
        },
    },
}

MODEL_CONFIG = MODEL_CONFIGS[MODEL_FAMILY]
MODEL_PATH = MODEL_CONFIG["model_path"]
VLLM_MODEL_NAME = MODEL_CONFIG["served_model_name"]
CONTEXT_WINDOW = MODEL_CONFIG["context_window"]
VLLM_BASE_URL = MODEL_CONFIG["vllm_base_url"]

CONVERSATION_PATH = Path("./tmp/conversation.json")
TRACE_PATH = Path("./tmp/trace.txt")

PROMPT = "9月初从上海出发，意大利入，法国出。情侣两人，帮我规划意大利，瑞士，法国的十二日行程，节奏不要太赶，喜欢拍照出片，体验当地人文特色，预算总共4w以内，推荐酒店以及特色美食，但是不要吃太奇怪的食物，考虑天气因素，给我一份具体规划路线，最后计划写成一个.md在./tmp目录下. 在写计划的时候，记得标注新闻、报道、信息以及数据这些东西的来源"
# PROMPT = "解读英伟达最新财报，并由此分析九月份AI相关产业的股价走势，结合历史上的数据，给出你认为比较适合投资的公司，最后计划写成一个.md在 ./tmp目录下。在写计划的时候，记得标注新闻、报道、信息以及数据这些东西的来源"
AGENTS_PATH = Path(__file__).with_name("AGENTS.md")


def load_agent_instructions() -> str:
    return AGENTS_PATH.read_text(encoding="utf-8")


def create_agent(
    *,
    model_path: str = MODEL_PATH,
    max_steps: int = 100,
    conversation_path: str | Path = CONVERSATION_PATH,
    trace_path: str | Path = TRACE_PATH,
) -> Agent:
    protocol = MODEL_CONFIG["protocol"](
        model_path,
        **MODEL_CONFIG["protocol_options"],
    )
    model = VLLMBackend(
        VLLM_MODEL_NAME,
        base_url=VLLM_BASE_URL,
        options=MODEL_CONFIG["vllm_options"],
    )
    return Agent(
        model,
        TOOLS,
        protocol=protocol,
        system_prompt=load_agent_instructions(),
        max_steps=max_steps,
        conversation_store=JsonConversationStore(conversation_path),
        trace_path=trace_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one non-interactive agent task.")
    parser.add_argument("--prompt", default=PROMPT)
    parser.add_argument("--model", default=MODEL_PATH)
    parser.add_argument("--max-steps", type=int, default=100)
    args = parser.parse_args()

    agent = create_agent(
        model_path=args.model,
        max_steps=args.max_steps,
    )

    result = agent.run(args.prompt)

    print('=' * 24, 'Final Answer', '=' * 24)
    print(result.answer)
    print('=' * 24, 'Token Usage', '=' * 25)
    print(f"Input tokens:  {result.usage.input_tokens:,}")
    print(f"Output tokens: {result.usage.output_tokens:,}")
    print(f"Total tokens:  {result.usage.total_tokens:,}")
    context_usage = result.current_context_tokens / CONTEXT_WINDOW * 100
    print('=' * 22, 'Current Context', '=' * 22)
    print(f"{result.current_context_tokens:,}/{CONTEXT_WINDOW:,} ({context_usage:.2f}%)")


if __name__ == "__main__":
    main()

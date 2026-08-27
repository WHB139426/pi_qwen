"""Non-interactive example for the minimal agent harness."""

from __future__ import annotations

import argparse
from dataclasses import replace
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

# PROMPT = "从杭州出发，9月初，进行山西五日游，两个大人一个小孩一个老人，推荐特色美食和酒店，总预算10000之内，想要尽可能多的欣赏著名景点，但是节奏不想太赶，并考虑天气因素，请给出具体的行程路线，最后计划写成一个.md在/tmp目录下"
PROMPT = "解读英伟达最新财报，并由此分析九月份AI相关产业的股价走势，结合历史上的数据，给出你认为比较适合投资的公司"
PROMPT = "你知道GLM5.3 FLASH这个模型吗, 详细介绍一下，比较他和其他先进模型的性能比较，并且告诉我官方推荐推理参数的最优设置，比如temperature， topp/k那些"
AGENTS_PATH = Path(__file__).with_name("AGENTS.md")


def load_agent_instructions() -> str:
    return AGENTS_PATH.read_text(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one non-interactive agent task.")
    parser.add_argument("--prompt", default=PROMPT)
    parser.add_argument("--model", default=MODEL_PATH)
    parser.add_argument("--max-steps", type=int, default=100)
    args = parser.parse_args()

    protocol = MODEL_CONFIG["protocol"](
        args.model,
        **MODEL_CONFIG["protocol_options"],
    )

    model = VLLMBackend(
        VLLM_MODEL_NAME,
        base_url=VLLM_BASE_URL,
        options=replace(
            MODEL_CONFIG["vllm_options"],
        ),
    )
    agent = Agent(
        model,
        TOOLS,
        protocol=protocol,
        system_prompt=load_agent_instructions(),
        max_steps=args.max_steps,
        conversation_store=JsonConversationStore(CONVERSATION_PATH),
        trace_path=TRACE_PATH,
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

"""Non-interactive example for the minimal Qwen agent."""

from __future__ import annotations

import argparse
from pathlib import Path

from agent_core import Agent
from models import GenerationOptions, QwenModel, VLLMModel, VLLMOptions
from tools import TOOLS


"""
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
"""

MODEL_PATH = "/data4/haibo/weights/Qwen3.8-27B"
BACKEND = "vllm"  # "vllm" or "transformers"
VLLM_MODEL_NAME = "qwen3.8-27b"
VLLM_BASE_URL = "http://127.0.0.1:8000/v1"

PROMPT = "从杭州出发，9月初，进行山西五日游，两个大人一个小孩一个老人，推荐特色美食和酒店，总预算10000之内，想要尽可能多的欣赏著名景点，但是节奏不想太赶，并考虑天气因素，请给出具体的行程路线，最后计划写成一个.md在/tmp目录下"
PROMPT = "你知道这几天的GTA6泄露事件吗"
ENABLE_THINKING = True
REASONING_EFFORT = "xhigh" # xhigh, medium, low
SHOW_RAW_TRACE = True
AGENTS_PATH = Path(__file__).with_name("AGENTS.md")


def load_agent_instructions() -> str:
    return AGENTS_PATH.read_text(encoding="utf-8")

def main() -> None:
    parser = argparse.ArgumentParser(description="Run one non-interactive Qwen agent task.")
    parser.add_argument("--prompt", default=PROMPT)
    parser.add_argument("--model", default=MODEL_PATH)
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument("--max-new-tokens", type=int, default=32*1024)
    args = parser.parse_args()

    if BACKEND == "transformers":
        model = QwenModel(
            args.model,
            options=GenerationOptions(
                max_new_tokens=args.max_new_tokens,
                enable_thinking=ENABLE_THINKING,
                reasoning_effort=REASONING_EFFORT,
            ),
            show_raw_trace=SHOW_RAW_TRACE,
        )
    elif BACKEND == "vllm":
        model = VLLMModel(
            args.model,
            served_model_name=VLLM_MODEL_NAME,
            base_url=VLLM_BASE_URL,
            options=VLLMOptions(
                max_tokens=args.max_new_tokens,
                enable_thinking=ENABLE_THINKING,
                reasoning_effort=REASONING_EFFORT,
            ),
            show_trace=SHOW_RAW_TRACE,
        )
    else:
        raise ValueError(f"unknown backend: {BACKEND}")
    agent = Agent(
        model,
        TOOLS,
        system_prompt=load_agent_instructions(),
        max_steps=args.max_steps,
    )

    result = agent.run(args.prompt)

    print('=' * 24, 'Final Answer', '=' * 24)
    print(result.answer)


if __name__ == "__main__":
    main()

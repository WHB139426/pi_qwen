"""Non-interactive example for the minimal Qwen agent."""

from __future__ import annotations

import argparse
from pathlib import Path

from agent_core import Agent, JsonConversationStore
from backends import VLLMBackend, VLLMOptions
from protocols import QwenProtocol
from tools import TOOLS


"""
CUDA_VISIBLE_DEVICES=0 vllm serve /data4/haibo/weights/Qwen3.8-27B \
    --served-model-name qwen3.8-27b \
    --host 127.0.0.1 \
    --port 8000 \
    --dtype bfloat16 \
    --tensor-parallel-size 1 \
    --max-model-len 262144 \
    --gpu-memory-utilization 0.90
"""

MODEL_PATH = "/data4/haibo/weights/Qwen3.8-27B"
VLLM_MODEL_NAME = "qwen3.8-27b"
VLLM_BASE_URL = "http://127.0.0.1:8000/v1"
CONVERSATION_PATH = Path("./tmp/conversation.json")

# PROMPT = "从杭州出发，9月初，进行山西五日游，两个大人一个小孩一个老人，推荐特色美食和酒店，总预算10000之内，想要尽可能多的欣赏著名景点，但是节奏不想太赶，并考虑天气因素，请给出具体的行程路线，最后计划写成一个.md在/tmp目录下"
PROMPT = "皇马最新一轮西甲比赛的过程结果，以及赛后新闻发布会的内容"
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

    protocol = QwenProtocol(
        args.model,
        enable_thinking=ENABLE_THINKING,
        reasoning_effort=REASONING_EFFORT,
        preserve_thinking=True,
    )

    model = VLLMBackend(
        VLLM_MODEL_NAME,
        base_url=VLLM_BASE_URL,
        options=VLLMOptions(
            max_tokens=args.max_new_tokens,
        ),
    )
    agent = Agent(
        model,
        TOOLS,
        protocol=protocol,
        system_prompt=load_agent_instructions(),
        max_steps=args.max_steps,
        conversation_store=JsonConversationStore(CONVERSATION_PATH),
        show_trace=SHOW_RAW_TRACE,
    )

    result = agent.run(args.prompt)

    print('=' * 24, 'Final Answer', '=' * 24)
    print(result.answer)


if __name__ == "__main__":
    main()

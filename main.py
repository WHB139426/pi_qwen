"""Non-interactive example for the minimal Qwen agent."""

from __future__ import annotations

import argparse
from pathlib import Path

from agent_core import Agent, JsonConversationStore
from backends import VLLMBackend, VLLMOptions
from protocols import QwenProtocol
from tools import TOOLS


"""
CUDA_VISIBLE_DEVICES=0,1,2,3 vllm serve /data4/haibo/weights/Qwen3.8-27B \
    --served-model-name qwen3.8-27b \
    --host 127.0.0.1 \
    --port 8000 \
    --dtype bfloat16 \
    --tensor-parallel-size 4 \
    --max-model-len 262144 \
    --gpu-memory-utilization 0.90
"""

MODEL_PATH = "/data4/haibo/weights/Qwen3.8-27B"
VLLM_MODEL_NAME = "qwen3.8-27b"
VLLM_BASE_URL = "http://127.0.0.1:8000/v1"
CONVERSATION_PATH = Path("./tmp/conversation.json")
TRACE_PATH = Path("./tmp/trace.txt")

# PROMPT = "从杭州出发，9月初，进行山西五日游，两个大人一个小孩一个老人，推荐特色美食和酒店，总预算10000之内，想要尽可能多的欣赏著名景点，但是节奏不想太赶，并考虑天气因素，请给出具体的行程路线，最后计划写成一个.md在/tmp目录下"
PROMPT = "我想知道最新的GLM-5.3-Flash和Qwen3.8-Flash-Next这两个模型的各种相关信息，模型的细节，和性能的比较等，你可以重点搜索huggingface的网站，比较的时候把其他先进模型的性能也带上"
ENABLE_THINKING = True
REASONING_EFFORT = "xhigh" # xhigh, medium, low
AGENTS_PATH = Path(__file__).with_name("AGENTS.md")


def load_agent_instructions() -> str:
    return AGENTS_PATH.read_text(encoding="utf-8")

def main() -> None:
    parser = argparse.ArgumentParser(description="Run one non-interactive Qwen agent task.")
    parser.add_argument("--prompt", default=PROMPT)
    parser.add_argument("--model", default=MODEL_PATH)
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument("--max-new-tokens", type=int, default=128*1024)
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
        trace_path=TRACE_PATH,
    )

    result = agent.run(args.prompt)

    print('=' * 24, 'Final Answer', '=' * 24)
    print(result.answer)


if __name__ == "__main__":
    main()

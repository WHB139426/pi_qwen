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
CONTEXT_WINDOW = 262_144

# PROMPT = "从杭州出发，9月初，进行山西五日游，两个大人一个小孩一个老人，推荐特色美食和酒店，总预算10000之内，想要尽可能多的欣赏著名景点，但是节奏不想太赶，并考虑天气因素，请给出具体的行程路线，最后计划写成一个.md在/tmp目录下"
PROMPT = "解读英伟达最新财报，并由此分析九月份AI相关产业的股价走势，结合历史上的数据，给出你认为比较适合投资的公司"
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
    print('=' * 24, 'Token Usage', '=' * 25)
    print(f"Input tokens:  {result.usage.input_tokens:,}")
    print(f"Output tokens: {result.usage.output_tokens:,}")
    print(f"Total tokens:  {result.usage.total_tokens:,}")
    context_usage = result.current_context_tokens / CONTEXT_WINDOW * 100
    print('=' * 22, 'Current Context', '=' * 22)
    print(f"{result.current_context_tokens:,}/{CONTEXT_WINDOW:,} ({context_usage:.2f}%)")


if __name__ == "__main__":
    main()

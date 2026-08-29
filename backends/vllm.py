"""Raw text-generation backend for a vLLM OpenAI-compatible server."""

from __future__ import annotations

from dataclasses import dataclass

from agent_core import Generation, ModelInput, TokenUsage
from agent_core.types import TokenDeltaCallback


@dataclass(frozen=True)
class VLLMOptions:
    max_tokens: int = 32 * 1024
    do_sample: bool = True
    temperature: float = 1.0
    top_p: float = 0.95
    top_k: int = 20


class VLLMBackend:
    """Send a fully rendered context to vLLM and return raw generated text."""

    def __init__(
        self,
        model: str,
        *,
        base_url: str = "http://127.0.0.1:8000/v1",
        options: VLLMOptions | None = None,
    ) -> None:
        from openai import OpenAI

        self.model = model
        self.options = options or VLLMOptions()
        self.client = OpenAI(base_url=base_url, api_key="EMPTY")

    def generate(
        self,
        model_input: str | ModelInput,
        *,
        on_delta: TokenDeltaCallback | None = None,
    ) -> Generation:
        if isinstance(model_input, ModelInput) and model_input.is_multimodal:
            return self._generate_multimodal(model_input, on_delta=on_delta)

        context = (
            model_input.context
            if isinstance(model_input, ModelInput)
            else model_input
        )
        temperature = self.options.temperature if self.options.do_sample else 0.0
        stream = self.client.completions.create(
            model=self.model,
            prompt=context,
            max_tokens=self.options.max_tokens,
            temperature=temperature,
            top_p=self.options.top_p,
            stream=True,
            stream_options={"include_usage": True},
            extra_body={
                "top_k": self.options.top_k,
                "skip_special_tokens": False,
            },
        )
        parts: list[str] = []
        usage = None
        for chunk in stream:
            if chunk.usage is not None:
                usage = chunk.usage
            for choice in chunk.choices:
                delta = choice.text
                if not delta:
                    continue
                parts.append(delta)
                if on_delta is not None:
                    on_delta(delta)

        if usage is None:
            raise RuntimeError("vLLM response did not include token usage")
        return Generation(
            text="".join(parts),
            usage=TokenUsage(
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
            ),
        )

    def _generate_multimodal(
        self,
        model_input: ModelInput,
        *,
        on_delta: TokenDeltaCallback | None = None,
    ) -> Generation:
        """Use vLLM's chat endpoint so it can resolve and encode media inputs."""
        temperature = self.options.temperature if self.options.do_sample else 0.0
        extra_body: dict[str, object] = {
            "top_k": self.options.top_k,
            "skip_special_tokens": False,
            "chat_template_kwargs": model_input.chat_template_kwargs or {},
        }
        if model_input.mm_processor_kwargs:
            extra_body["mm_processor_kwargs"] = model_input.mm_processor_kwargs

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=model_input.api_messages or [],
            tools=model_input.tools,
            tool_choice="none",
            max_tokens=self.options.max_tokens,
            temperature=temperature,
            top_p=self.options.top_p,
            stream=True,
            stream_options={"include_usage": True},
            extra_body=extra_body,
        )

        parts: list[str] = []
        usage = None
        separate_reasoning = False
        reasoning_closed = False

        def emit(delta: str) -> None:
            parts.append(delta)
            if on_delta is not None:
                on_delta(delta)

        for chunk in stream:
            if chunk.usage is not None:
                usage = chunk.usage
            for choice in chunk.choices:
                delta = choice.delta
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning is None:
                    reasoning = getattr(delta, "reasoning", None)
                if reasoning:
                    if not separate_reasoning:
                        separate_reasoning = True
                        emit("<think>\n")
                    emit(reasoning)

                content = delta.content
                if content:
                    if separate_reasoning and not reasoning_closed:
                        emit("\n</think>\n\n")
                        reasoning_closed = True
                    emit(content)

                if getattr(delta, "tool_calls", None):
                    raise RuntimeError(
                        "vLLM returned parsed tool calls. Start the model server without "
                        "--enable-auto-tool-choice/--tool-call-parser so the harness can "
                        "parse the model's raw tool-call text itself."
                    )

        if separate_reasoning and not reasoning_closed:
            emit("\n</think>")
        if usage is None:
            raise RuntimeError("vLLM response did not include token usage")
        return Generation(
            text="".join(parts),
            usage=TokenUsage(
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
            ),
        )

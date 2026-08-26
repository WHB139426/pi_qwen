"""Raw text-generation backend for a vLLM OpenAI-compatible server."""

from __future__ import annotations

from dataclasses import dataclass


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

    def generate(self, context: str) -> str:
        temperature = self.options.temperature if self.options.do_sample else 0.0
        response = self.client.completions.create(
            model=self.model,
            prompt=context,
            max_tokens=self.options.max_tokens,
            temperature=temperature,
            top_p=self.options.top_p,
            extra_body={
                "top_k": self.options.top_k,
                "skip_special_tokens": False,
            },
        )
        return response.choices[0].text

"""Workspace-scoped visual inspection tool with transient multimodal output."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from agent_core import Tool, ToolOutput


MAX_IMAGE_BYTES = 50 * 1024 * 1024
MAX_IMAGE_PIXELS = 100_000_000
SUPPORTED_FORMATS = {"BMP", "GIF", "JPEG", "PNG", "TIFF", "WEBP"}


def make_view_image_tool(workspace_path: str | Path) -> Tool:
    """Create a view_image tool restricted to one conversation workspace."""
    workspace = Path(workspace_path).expanduser().resolve()

    def view_image(path: str) -> ToolOutput:
        requested = Path(path).expanduser()
        candidate = requested if requested.is_absolute() else Path.cwd() / requested
        if candidate.is_symlink():
            raise ValueError("image path must not be a symbolic link")

        resolved = candidate.resolve(strict=True)
        if resolved != workspace and workspace not in resolved.parents:
            raise ValueError("image path is outside the conversation workspace")
        if not resolved.is_file():
            raise ValueError("image path must refer to a file")

        size = resolved.stat().st_size
        if size > MAX_IMAGE_BYTES:
            raise ValueError(
                f"image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MiB limit"
            )

        with Image.open(resolved) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
            if image_format not in SUPPORTED_FORMATS:
                raise ValueError(f"unsupported image format: {image_format or 'unknown'}")
            if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                raise ValueError("image dimensions are invalid or too large")
            image.verify()

        display_path = resolved.as_posix()
        metadata = {
            "path": display_path,
            "format": image_format,
            "width": width,
            "height": height,
            "bytes": size,
            "attached_for_next_generation": True,
            "persisted_in_conversation": False,
        }
        inspection_prompt = (
            "[Image inspection]\n"
            f"Inspect the actual image at `{display_path}`. Use its visible content as "
            "evidence for the current task. Describe, analyze, compare, extract, or verify "
            "what is relevant to the user's request. If this is an artifact being "
            "validated, identify concrete content and layout defects, fix the source, and "
            "render it again when problems are present. Do not infer that an image is "
            "correct merely because it opened successfully."
        )
        return ToolOutput(
            value=metadata,
            transient_messages=(
                {
                    "role": "user",
                    "message_type": "transient_image_inspection",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": resolved.as_uri()},
                        },
                        {"type": "text", "text": inspection_prompt},
                    ],
                },
            ),
        )

    return Tool(
        name="view_image",
        description=(
            "View any image inside the current conversation workspace as an actual "
            "multimodal input. Use it for user uploads, downloaded web images, reference "
            "images, generated images, charts, diagrams, screenshots, and rendered pages "
            "or slides. Download internet images into the workspace before viewing them."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path to any uploaded, downloaded, generated, or otherwise "
                        "available image inside the conversation workspace."
                    ),
                },
            },
            "required": ["path"],
        },
        function=view_image,
    )

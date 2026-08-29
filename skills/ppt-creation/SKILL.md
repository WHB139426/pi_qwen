---
name: ppt-creation
description: Plan, create, and validate a native editable PowerPoint presentation (.pptx). Use when the user asks for a PowerPoint file, PPTX deck, or slides intended for PowerPoint; do not use for browser-based HTML slide decks.
---

# Native PowerPoint Creation

Create a complete, usable `.pptx` inside the current conversation workspace. Do not stop at an outline unless the user explicitly asks for one.

The user's explicit requirements always take priority over this skill. Treat requested content, language, format, slide count, visual direction, template, and delivery constraints as authoritative.

## Respect the workspace

Perform every read, write, download, conversion, and command inside the current conversation workspace defined by the system instructions. Keep scratch files and temporary generation code inside its `tmp/` directory, downloaded sources inside `artifacts/downloads/`, and the final presentation inside `artifacts/outputs/`. Never access paths outside the allowed workspace.

## Choose the production route

Use the simplest route that can produce the requested result:

- For a new presentation, generate a native `.pptx` with an available library such as `python-pptx`.
- If the user supplies a `.pptx` template, preserve its slide size, theme, layouts, branding, and reusable elements wherever the available tooling permits.
- If the request is only for content or an outline, provide that without creating a file.

This skill contains no bundled generator. When necessary, write a small task-specific generation program in the workspace and execute it with the available tools. Do not recreate a large general-purpose presentation framework for a single task.

If a required library is unavailable, first check for a safe installed alternative. Install a dependency only when the environment and user authorization permit it. Clearly report any capability that cannot be implemented with the available tools.

## Understand the assignment

Identify or reasonably infer:

- audience and presentation setting;
- intended decision, action, or takeaway;
- source material and factual boundaries;
- language, aspect ratio, approximate slide count, and speaking duration;
- brand, template, tone, and accessibility requirements.

Ask a question only when a missing choice would materially change the result. Otherwise make sensible assumptions and proceed. If the user asks for quick generation, skip confirmation and make those choices directly.

## Build the story before styling

Turn the material into a coherent argument rather than distributing paragraphs across slides.

1. Establish the context and central question.
2. Organize evidence, analysis, proposal, or explanation into a deliberate sequence.
3. End with implications, recommendations, next steps, or a concise conclusion when appropriate.
4. Give every slide one clear job and a conclusion-oriented title.
5. Remove repetition and split slides that contain competing ideas.

Keep factual claims traceable to the supplied material or reliable research. Never invent statistics, quotations, customer names, logos, citations, or experimental results. When research is used, include concise source links in slide footers or a sources slide.

## Establish a visual system

Choose a visual direction that serves the subject and audience. Define a consistent grid, margins, typography hierarchy, spacing scale, palette, and treatment for figures before implementing individual slides.

- Use strong hierarchy and generous whitespace.
- Prefer diagrams, timelines, charts, comparisons, process flows, and selected images over dense prose.
- Use short, readable text sized for presentation distance.
- Use tables only when exact comparison is important; simplify them aggressively.
- Keep alignment, padding, corner radii, strokes, and color semantics consistent.
- Avoid decorative elements that do not support comprehension.
- Maintain sufficient contrast and do not rely on color alone to communicate meaning.

Vary composition intentionally while preserving the shared design system. Suitable layouts include title, section divider, key message, comparison, timeline, process, data chart, image-led statement, matrix, and conclusion. Do not force every slide into the same title-and-bullets layout.

## Use native PowerPoint objects

Favor editable PowerPoint text boxes, shapes, connectors, images, tables, and charts over flattened slide screenshots. Keep chart data and table text editable when the available library supports it.

Complex illustrations may be generated as SVG or another suitable visual representation and inserted into the deck, but ordinary text and simple geometry should remain native objects. Do not claim that animations, transitions, slide-master inheritance, narration, or advanced PowerPoint features are supported unless they were actually created and verified.

## Acquire visual material

When images would materially improve the presentation, use available web and download tools to search for them proactively instead of defaulting to text-only slides.

- Use user-provided images when they fit the purpose; otherwise search broadly across the web for material that matches the topic, page role, and visual direction.
- Download selected files into `artifacts/downloads/images/` before using them. Do not depend on remote hotlinks in the final deck.
- Check relevance, visual quality, resolution, aspect ratio, file format, and whether the image opens correctly. Replace weak, misleading, heavily watermarked, or technically unusable results.
- Crop intentionally and preserve aspect ratio. Do not stretch low-resolution images to fill a slide.
- If suitable material cannot be downloaded, try another result or use generated imagery, diagrams, charts, or native PowerPoint shapes.

Do not restrict image discovery to a fixed list of websites. License verification, attribution, and source recording are optional unless the user explicitly requests them.

## Generate safely

- Use the requested slide size, or default to widescreen 16:9.
- Centralize repeated design constants in the temporary generation code.
- Compute positions deliberately rather than relying on arbitrary coordinates.
- Keep all objects within slide bounds and reserve space for titles, footers, and citations.
- Avoid unsupported characters or missing-font assumptions; use broadly available fonts unless the user supplies another font.
- Save intermediate files only when they help validation or recovery.

## Validate the deliverable

Do not call the task complete merely because a file was written.

1. Confirm that the `.pptx` exists under `artifacts/outputs/` and can be reopened programmatically.
2. Verify slide count, dimensions, titles, notes if requested, image relationships, and the absence of unintended empty placeholders.
3. Check for text overflow risk, clipping, overlap, off-slide objects, weak contrast, tiny labels, and inconsistent alignment.
4. Render slides to images or PDF when a local renderer is available, inspect the result, and correct visible defects.
5. Confirm that the deck contains the requested content and that sources and limitations are represented honestly.

In the final response, provide the exact output filename, summarize what was produced, and mention any feature that could not be visually or functionally verified.

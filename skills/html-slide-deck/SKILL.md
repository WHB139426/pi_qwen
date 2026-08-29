---
name: html-slide-deck
description: Plan, create, and validate a polished browser-based slide presentation as a self-contained HTML file. Use for web slides, swipe decks, interactive presentations, or an HTML alternative to PowerPoint; do not use when the user specifically requires a .pptx file.
---

# HTML Slide Deck Creation

Create a polished browser presentation as a self-contained `.html` file inside the current conversation workspace. The result must be usable by opening the file directly in a modern browser, without a build step or web server.

The user's explicit requirements always take priority over this skill. Treat requested content, language, style, dimensions, interaction, and delivery constraints as authoritative.

## Respect the workspace

Perform every read, write, download, conversion, and command inside the current conversation workspace defined by the system instructions. Keep scratch files inside its `tmp/` directory, downloaded sources inside `artifacts/downloads/`, and the final HTML presentation inside `artifacts/outputs/`. Never access paths outside the allowed workspace.

## Understand the assignment

Identify or reasonably infer:

- audience, viewing environment, and intended takeaway;
- source material and factual boundaries;
- language, slide count, aspect ratio, and presentation duration;
- desired visual character, brand constraints, and interaction needs.

Ask a question only when a missing decision would materially change the result. Otherwise make sensible assumptions and proceed. If the user requests quick generation, choose the structure and visual direction directly.

## Shape the narrative

Plan the deck before implementing its visual surface.

1. Define the central message and narrative arc.
2. Give every slide one job and a conclusion-oriented title.
3. Use evidence, examples, diagrams, and comparisons to advance the story.
4. Remove redundant slides and split overloaded ones.
5. Finish with implications, recommendations, next steps, or a clear closing thought when appropriate.

Do not fabricate facts, metrics, quotations, logos, or citations. When research is used, include concise source links on relevant slides or in a sources section.

## Select a visual direction

Choose a coherent system suited to the material rather than mixing unrelated styles. Two useful starting directions are:

### Editorial presentation

Use expressive typography, strong image crops, asymmetry, generous whitespace, restrained color, pull quotes, chapter openers, and deliberate pacing. This direction suits narratives, talks, cultural topics, personal viewpoints, and image-led storytelling.

### Swiss grid presentation

Use a strict modular grid, clear typographic hierarchy, disciplined alignment, high information density with strong organization, and one restrained accent color. This direction suits products, research, analysis, frameworks, reports, and data-heavy subjects.

These are starting points, not mandatory themes. Adapt or replace them when the user requests another aesthetic.

## Compose the slides

Establish shared design tokens for color, typography, spacing, borders, shadows, and motion. Use multiple layouts while preserving the same visual grammar. Appropriate layouts include:

- cover and closing slides;
- section dividers;
- single key statement or quotation;
- editorial image with caption;
- two-column comparison;
- timeline or process;
- metric dashboard or chart;
- matrix, framework, or architecture diagram;
- case study and before/after;
- sources or appendix.

Prefer visual explanation over paragraphs. Keep text readable at presentation distance, preserve whitespace, align elements precisely, and maintain sufficient contrast. Avoid gratuitous gradients, excessive cards, generic icon grids, and animation that competes with the content.

## Acquire visual material

When images would materially improve the deck, use available web and download tools to search for them proactively.

- Use user-provided images when appropriate; otherwise search broadly across the web for visuals that fit the subject, slide role, composition, and chosen style.
- Download selected files into `artifacts/downloads/images/` and inspect the actual file before placing it in the deck.
- Check relevance, visual quality, resolution, aspect ratio, format, and successful decoding. Replace weak, misleading, heavily watermarked, or technically unusable results.
- Crop and position images deliberately rather than stretching them or treating them as generic decoration.
- If a download fails or no suitable image is found, try another result or use generated imagery, CSS illustration, diagrams, charts, or typography-led composition.

Do not restrict image discovery to a fixed list of websites. License verification, attribution, and source recording are optional unless the user explicitly requests them.

## Produce a self-contained HTML file

Write task-specific HTML, CSS, and JavaScript directly; this skill contains no bundled template or generator.

- Inline CSS and JavaScript in the final HTML.
- Avoid external runtime dependencies and CDNs unless the user explicitly permits them.
- Embed essential images as data URLs when practical. If embedding would make the document unreasonably large, use relative files under `artifacts/outputs/` and report that the deliverable is no longer a single standalone file.
- Use semantic HTML where practical and include useful document metadata.
- Keep the source organized with reusable CSS variables and clear slide sections.
- Use responsive scaling so the designed canvas fits different viewport sizes without changing the intended composition.
- Avoid browser features that require a local server when the file is opened with `file://`.

Default to a 16:9 stage unless the user specifies another ratio.

## Provide presentation interaction

Unless the user requests a static document, support:

- previous and next navigation with arrow keys;
- wheel or trackpad navigation with throttling to prevent accidental multi-slide jumps;
- touch swipe navigation;
- clickable progress dots or another compact position indicator;
- current slide number and total slide count;
- Home and End navigation;
- optional overview or index, commonly toggled with Escape;
- optional fullscreen control using the browser Fullscreen API.

Update the URL hash or an equivalent local state when useful, but ensure the deck still works when opened directly. Respect `prefers-reduced-motion`, keep transitions brief, and avoid motion that obscures reading.

## Accessibility and robustness

- Use semantic headings and meaningful alternative text for informative images.
- Ensure keyboard navigation works without a mouse.
- Maintain readable contrast and visible focus states.
- Do not convey essential meaning through color alone.
- Prevent long text, URLs, code, and tables from overflowing their containers.
- Escape or safely encode user-provided content inserted into HTML.

## Validate the deliverable

Do not call the task complete merely because the HTML file was written.

1. Confirm that the final file exists under `artifacts/outputs/` and contains all required inline styles and scripts.
2. Check slide count, titles, navigation controls, links, image references, and source citations.
3. Open or render the HTML with an available browser tool and inspect representative slides at desktop and smaller viewport sizes.
4. Test keyboard navigation, touch or pointer controls where possible, overview mode, URL state, and fullscreen controls if included.
5. Correct clipping, overlap, unreadable text, weak contrast, broken media, excessive animation, and console errors.

In the final response, provide the exact output filename, summarize the presentation and interaction features, and disclose any browser behavior that could not be tested.

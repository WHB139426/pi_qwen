---
name: html-creation
description: Plan, create, edit, and validate polished HTML deliverables, including webpages, reports, dashboards, guides, interactive tools, documents, and browser slide decks. Use when the requested final artifact is HTML; use ppt-creation instead when the user specifically requires a native .pptx file.
---

# General HTML Creation

Create a complete, usable HTML deliverable inside the current conversation
workspace. The result should open directly in a modern browser unless the user
explicitly requests an application that requires a server or build process.

The user's explicit requirements always take priority over this skill. Treat
requested content, format, structure, language, visual style, interaction,
technology, and delivery constraints as authoritative.

## Respect the workspace

Perform every read, write, download, conversion, and command inside the current
conversation workspace defined by the system instructions. Keep scratch files
inside its `tmp/` directory, downloaded sources inside `artifacts/downloads/`,
and final deliverables inside `artifacts/outputs/`. Never access paths outside
the allowed workspace.

## Determine the HTML mode

Identify the kind of artifact before choosing its structure and interactions.
Common modes include:

- a responsive webpage, landing page, profile, portal, or microsite;
- a long-form article, guide, research report, itinerary, or printable document;
- a dashboard, comparison, data story, or analytical report;
- an interactive calculator, explorer, form, prototype, or small browser tool;
- a browser-based slide deck or swipe presentation;
- an edit or extension of an existing HTML artifact supplied by the user.

Do not impose slide behavior, fixed 16:9 dimensions, page-by-page navigation,
or presentation controls unless the requested artifact is actually a slide
deck. Conversely, do not turn an explicitly requested presentation into a
scrolling webpage.

Infer the audience, viewing environment, primary task, content boundaries,
information hierarchy, desired visual character, and important interactions.
Ask a question only when a missing decision would materially change the result;
otherwise make sensible choices and proceed.

## Structure the content

Plan the information architecture before styling it.

- Give every section a clear purpose and arrange sections in a coherent order.
- Lead with the main answer, purpose, or value when appropriate.
- Use headings, summaries, navigation, tables of contents, anchors, filters, or
  progressive disclosure when they genuinely improve comprehension.
- Prefer diagrams, charts, comparisons, timelines, maps, and selected images
  over dense prose when they communicate the idea more effectively.
- Keep factual claims traceable to user-provided material or reliable research.
  Do not fabricate metrics, quotations, identities, logos, or citations.
- Include concise links or source notes when research is used and attribution is
  useful to the requested artifact.

For slide decks, give each slide one job and a conclusion-oriented title. For
reports and articles, optimize the reading flow and print structure. For tools
and dashboards, optimize task completion, state clarity, and data legibility.

## Establish a visual system

Choose a coherent design direction suited to the subject rather than applying
a generic template. Define reusable CSS variables for colors, typography,
spacing, radii, borders, shadows, and motion. Maintain deliberate hierarchy,
alignment, whitespace, contrast, and visual rhythm across the artifact.

Use layouts appropriate to the selected mode: editorial flow, modular grid,
responsive sections, dashboard panels, data tables, comparison bands, timelines,
image-led compositions, or fixed presentation stages. Vary composition where it
improves communication while preserving a shared visual grammar.

Avoid gratuitous gradients, excessive card grids, decorative icons without
meaning, tiny text, weak contrast, and animation that competes with content.

## Acquire and use visual material

When images would materially improve the result, use available web and download
tools to search for them proactively.

- Prefer relevant user-provided visuals; otherwise search broadly for material
  that fits the subject, composition, and chosen style.
- Download selected files into `artifacts/downloads/images/` and inspect the
  actual files before placing them in the deliverable.
- Check relevance, decoding, resolution, aspect ratio, cropping, and visual
  quality. Replace weak, misleading, or technically unusable results.
- Use deliberate crops and captions rather than stretching images or treating
  them as generic decoration.
- When no useful image is available, use generated imagery, CSS illustration,
  SVG, diagrams, charts, maps, or typography-led composition.

Do not restrict image discovery to a fixed list of websites. License
verification, attribution, and source recording are optional unless the user
explicitly requests them.

## Implement the deliverable

Use the simplest implementation that satisfies the request. This skill contains
no bundled template or generator.

- Default to a self-contained HTML file with inline CSS and JavaScript.
- Avoid runtime dependencies, package installs, and CDNs unless they provide a
  concrete benefit or the user requests them.
- Embed essential images as data URLs when practical. If that would make the
  file unreasonably large, place relative assets beside the final HTML under
  `artifacts/outputs/` and disclose that the deliverable has multiple files.
- Use semantic HTML, useful metadata, reusable CSS classes, and clear source
  organization.
- Make ordinary pages responsive rather than scaling a desktop canvas down.
- For a requested fixed-layout artifact such as slides, preserve the intended
  canvas while fitting it safely into different viewports.
- Do not require a local server when the artifact can work under `file://`.
- Safely escape or encode untrusted user-provided content inserted into HTML.

If the user requests an existing framework, multiple files, or a server-backed
application, follow that requirement instead of forcing a single-file design.

## Add interaction intentionally

Include interaction only when it serves the selected mode.

- For webpages and documents, support useful navigation, anchors, disclosures,
  search, filtering, or print controls where appropriate.
- For dashboards and tools, provide clear inputs, states, validation, feedback,
  reset behavior, and keyboard operation.
- For browser slide decks, support previous/next navigation, arrow keys, touch
  gestures, a position indicator, Home/End, and optional overview or fullscreen
  controls unless the user requests a static deck.
- Preserve state in the URL only when sharing or restoration benefits from it.
- Respect `prefers-reduced-motion` and keep transitions brief.

Do not add controls that have no working behavior.

## Accessibility and resilience

- Use semantic landmarks and a logical heading structure.
- Give informative images meaningful alternative text.
- Ensure keyboard access, visible focus states, readable contrast, and usable
  control labels.
- Do not communicate essential meaning through color alone.
- Prevent long text, code, tables, URLs, media, and user input from overflowing.
- Provide sensible empty, loading, error, and disabled states when applicable.
- Avoid browser features that silently fail when opened from a local file.

## Validate the actual result

Do not declare completion merely because the HTML file was written.

1. Confirm that every final file exists under `artifacts/outputs/` and that all
   links, scripts, styles, media, and relative paths resolve correctly.
2. Open or render the actual HTML and inspect it visually at a normal desktop
   viewport and a narrow mobile viewport.
3. Inspect content-heavy and visually distinct sections at readable resolution;
   for slide decks, inspect every slide.
4. Test important navigation, forms, controls, scrolling, responsive states,
   keyboard behavior, and URL state where applicable.
5. Check browser console errors when tooling permits. For printable documents,
   inspect print or PDF output; for slide decks, test presentation navigation and
   fullscreen behavior if implemented.
6. Correct clipping, overlap, broken media, unreadable text, weak hierarchy,
   inconsistent spacing, unusable controls, excessive motion, and console errors,
   then render and inspect the corrected result again.

In the final response, provide the exact output filename, summarize the artifact
and its important interactions, and disclose any behavior that could not be
tested.

---
name: travel-planning
description: Research and build feasible multi-day travel plans with coherent routing, timed daily itineraries, transport, lodging areas, food, reservations, weather, budgets, and an optional self-contained HTML guide. Use for trip planning and destination itineraries, not for a simple destination fact lookup.
---

# Travel Planning

Create an actionable trip plan tailored to the travelers, not a generic attraction list. Optimize the route, timing, budget, and practical details as one connected system.

The user's explicit requirements always take priority over this skill. Preserve their destination, dates, pace, interests, budget, transport preferences, accessibility needs, and requested output format.

## Respect the workspace

Perform every read, write, download, conversion, and command inside the current conversation workspace defined by the system instructions. Keep scratch files inside its `tmp/` directory, downloaded material inside `artifacts/downloads/`, and any final travel guide inside `artifacts/outputs/`. Never access paths outside the allowed workspace.

## Establish the trip constraints

Identify or reasonably infer:

- origin, destination, dates or season, and number of days;
- number and ages of travelers, including children or older adults;
- transport mode and fixed arrival or departure times;
- total budget, currency, and desired comfort level;
- pace, interests, food preferences, dietary restrictions, and nightlife preferences;
- mobility, health, accessibility, visa, passport, or driving constraints;
- confirmed flights, hotels, tickets, and other fixed reservations.

Ask only for missing information that would materially alter the route. When the user has supplied enough information, state any important assumptions and proceed without unnecessary confirmation. If exact dates are unavailable, distinguish seasonal guidance from date-specific facts.

## Research current information

Travel facts change frequently. Use available web tools to verify details that affect feasibility, cost, safety, or booking. Prioritize sources according to the kind of claim:

1. Government, immigration, tourism authority, transport operator, airport, and venue sources for entry rules, schedules, closures, tickets, and official policies.
2. Maps, hotel or ticket platforms, and established travel providers for representative routing, availability, and current price ranges.
3. Recent local reporting, specialist travel publications, and user-generated accounts for atmosphere, crowd patterns, practical friction, hidden costs, and subjective experience.

Cross-check consequential claims. Treat user reports as anecdotal rather than authoritative, and prefer recent reports when describing conditions that change quickly. Never present an old price, timetable, opening hour, visa rule, weather forecast, or availability result as current without verification.

Research only what the plan needs. Typical targets include:

- entry requirements, permits, insurance, and health rules;
- arrival options and airport or station transfers;
- intercity and local transport, last departures, parking, tolls, and driving restrictions;
- attraction opening days, timed entry, reservation windows, and realistic visit duration;
- weather, daylight, seasonal closures, public holidays, and crowd pressure;
- lodging areas and representative nightly prices;
- local food, dietary suitability, customary meal times, and reservation needs;
- common tourist traps, accessibility limitations, and practical alternatives.

Attach links close to the claims they support. Clearly separate verified facts, representative prices, estimates, and recommendations.

## Construct a feasible route

Group activities by geography and logical sequence. Minimize backtracking, unnecessary hotel changes, and fragile transfers.

- Do not count arrival and departure days as full sightseeing days unless the actual times justify it.
- Include check-in, luggage storage, queues, meals, transit, rest, and recovery from long flights or altitude.
- Check that every transfer fits operating hours and realistic travel time, not merely map distance.
- Consider daylight, heat, rain, elevation, weekly closures, and peak-period congestion.
- Balance major sights with neighborhoods, food, unstructured time, and recovery.
- Avoid packing every day to maximum capacity; preserve buffers around reservations and long transfers.
- Provide a weather-resistant or reservation-independent alternative for vulnerable activities.

For road trips, account for driving time, fuel or charging, tolls, parking, one-way restrictions, rental conditions, and the driver's daily workload. For public transport, identify the relevant station, approximate duration, transfer count, booking channel, and last practical departure when important.

## Design each day

Give each day a clear geographical or thematic focus. Present a realistic sequence such as morning, afternoon, and evening, or use clock times when reservations and transfers require precision.

For each day include:

- base location and daily theme;
- activities in visit order with approximate duration;
- transport between major stops and approximate travel time;
- meal area or food suggestion where useful;
- tickets, reservation deadlines, opening-day constraints, and accessibility notes;
- one or two high-value practical tips;
- a fallback or flexible option when appropriate.

Explain briefly why the grouping is efficient. Add photography locations and lighting times only when they match the user's interests. Do not prescribe three to five attractions per day mechanically; choose a count that matches travel time and pace.

## Recommend lodging and food

Recommend lodging by neighborhood before naming individual properties. Explain each area's transport convenience, atmosphere, noise, safety, and suitability for the itinerary. Give only a small number of representative properties when useful, and label room rates as date-specific observations or estimates.

Recommend regional dishes and practical dining areas rather than producing an unfiltered restaurant list. Respect dietary restrictions and identify when reservations, queues, local payment methods, service charges, or limited opening hours matter.

## Build a reconciled budget

Use the requested currency and clarify whether amounts are per person, per room, per vehicle, or for the whole group. Include relevant categories:

- travel to and from the destination;
- accommodation, including taxes and fees;
- intercity and local transport, fuel, tolls, parking, or rental costs;
- food and drinks;
- admissions, tours, and activities;
- visas, permits, insurance, communications, and other trip-specific costs;
- contingency.

Show quantity and unit assumptions where they help the user verify the calculation. Avoid double-counting costs already included in passes, packages, or accommodation. Reconcile category subtotals with the final total. Use ranges when uncertainty is material and provide economy, comfortable, or premium scenarios only when they are useful to the request.

## Acquire destination imagery

When producing a travel guide or when visuals would improve the result, use available web and download tools to search proactively for destination, landscape, neighborhood, attraction, food, or transport images.

- Use user-provided images when they fit; otherwise search broadly across the web for images that support the actual itinerary and destination.
- Download selected files into `artifacts/downloads/images/` and inspect them before use.
- Check that each image depicts the intended place or subject and has adequate visual quality, resolution, aspect ratio, format, and successful decoding.
- For an HTML travel guide, use plentiful relevant imagery and, whenever a suitable image is available or can be found, pair every named attraction with an image of that specific attraction rather than reusing generic destination pictures. Replace misleading, heavily watermarked, repetitive, or technically unusable results.
- If a download fails or suitable material cannot be found, try another result or use generated imagery, CSS illustration, typography, or an ordered route diagram.

Do not restrict image discovery to a fixed list of websites. License verification, attribution, and source recording are optional unless the user explicitly requests them.

## Choose the deliverable

Answer directly in chat for an ordinary itinerary request. When the user asks for a guide, a downloadable file, a polished report, or an HTML page, produce a self-contained travel guide at `artifacts/outputs/<descriptive-name>.html`.

The HTML guide should work when opened directly in a modern browser and normally contain:

- destination summary and trip assumptions;
- route overview;
- day-by-day timeline;
- transport and lodging guidance;
- bookings and preparation checklist;
- food and practical recommendations;
- itemized budget with assumptions;
- weather, packing, safety, and contingency notes;
- sources with clickable links.

Write task-specific HTML and inline its CSS and JavaScript. Embed selected images as data URLs when practical so the result remains a single file. Do not depend on a bundled template, CDN, build process, or server. Use a responsive layout, readable typography, strong hierarchy, restrained color, accessible contrast, and print styles that avoid breaking itinerary cards awkwardly. Adapt the visual direction to the destination and user rather than forcing one fixed theme.

Avoid decorative maps that imply geographic accuracy. If an accurate interactive map cannot be produced, use a clear ordered route diagram or link to verified map locations instead.

## Validate the plan

Before finishing:

1. Check dates, weekdays, nights, travel legs, and arrival or departure logic for consistency.
2. Confirm that opening hours, reservations, transfers, and daily pacing do not contradict one another.
3. Recalculate the budget and verify whether totals are per person or for the group.
4. Ensure recommendations respect stated preferences, mobility, dietary, and budget constraints.
5. Verify that important volatile claims have nearby sources and that estimates are labelled.
6. If an HTML guide was created, confirm it exists under `artifacts/outputs/`, opens without external runtime dependencies, contains the complete itinerary, and is readable on desktop, mobile, and print layouts where testing is available.

End with the highest-priority advance bookings, unresolved decisions, and the exact output filename when a file was created. Never claim to have booked, guaranteed, or reserved anything unless a tool result proves it.

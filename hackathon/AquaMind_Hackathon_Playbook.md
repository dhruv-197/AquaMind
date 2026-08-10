# AquaMind AI — Final Round Playbook

**Format:** 4 min slides · 4 min live demo · 2 min Q&A
**Team roles:** Presenter 1 (slides 1–5) · Presenter 2 (slides 6–7, 9–10) · Business lead (slide 8) · Demo driver (4-min walkthrough) · Floater (Q&A + backup)

Everything below is grounded in what is actually in the repo. Where a claim would need a number I cannot verify from your code or a primary source, I have said so rather than inventing one.

---

## 0. The one strategic decision

Two of your four models do not beat their naive baseline on held-out test data — shortage (MAE 1.3125 vs persistence 0.6687) and leak (F1 0.8466 vs majority-class 0.8571). Your README already says this out loud.

**Do not hide it. Lead with it.** A jury that finds it themselves in Q&A will read it as a lie of omission and you lose Technical Accuracy *and* trust. A jury that hears you say it in minute two reads it as rigour, and you become the only team in the room whose numbers they believe.

The reframe you say out loud: **the fused index and the decision layer are the product; the component models are replaceable parts, and we have told you exactly which ones need replacing and what data replaces them.**

---

## 0b. What already changed in the build

These went into the repo since the first version of this playbook. **Rehearse against them — three screens look different now.** TypeScript compiles clean (`npx tsc --noEmit`) after every change. `node_modules` was not touched, so your Windows dev setup is unaffected.

| Area | Before | Now | Why |
|------|--------|-----|-----|
| Stress + Reservoir KPI cards | 7 sparklines were hardcoded arrays (`[42, 44, 43, 46, 48, …]`, `[55, 54, 53, 52, 51, …]`) — invented trend shapes | Drawn from the returned series; no series means no line (`src/components/ui/sparkline.ts`) | A sparkline is a claim about history. Inventing one contradicts the whole pitch. |
| Dashboard header | "Prediction Confidence" was `0.72 + 0.12` — a constant rendered as a model output | **"Live Fusion Inputs — 4 / 5 reporting"**, counted from each component's `availability` in the fusion metadata | Replaces a fabricated number with a real one that also demonstrates the provenance system |
| Dashboard "Predicted Demand" | Was `current × 1.04` whenever no forecast was passed | Uses the real 14-day demand forecast the dashboard already fetches; shows `-` / "Awaiting forecast feed" if it fails | It was labelling a 4% markup as a model prediction |
| Dashboard demand trend | Hardcoded `+3.8% vs 7d` and `Rising` | Computed from current → forecast, or omitted when either is missing | A specific fabricated percentage was the most quotable thing on the screen |
| Dashboard KPI footers | Every card read "vs prior period · <label>" even for labels like "Clear" | Removed; the trend chip stands alone | It asserted a period comparison that was never made |
| Groundwater KPI trend | Always "Depth rising" | Derived from the measured average depth, omitted when unavailable | Same reason |
| Population at Risk | Heuristic fallback presented like a measurement | Now labelled "Planning heuristic" with the derivation spelled out in the tooltip when it isn't from fusion context | Keeps the number, discloses what it is |
| Water Stress fusion card | Showed contribution share only | Adds a **`weight NN%` chip** per component, read straight from the API response | This is the on-screen proof of the auditability claim |
| `/water-stress` page header | Titled "Water Stress Index" — the same name as the dashboard index, but a different module with different weights | Retitled **"Regional Water Stress"** with the module version badge and an explicit note that it is per-region and separate from the system-wide index | Closes a real jury trap — see Q2b |
| Landing hero | Generic "Water Intelligence for Smarter Infrastructure Decisions" | "Predict water shortages, leakages and groundwater depletion" + the fusion sentence | Relevance to the problem statement, visible in the first 10 seconds |

**What was deliberately left alone:** the whole Python backend. It is in good shape, the heuristic confidence multipliers are already disclosed in the README, and changing model-facing code hours before a demo trades a small credibility gain for a large stability risk.

**Two things to check on the first run**, because the sandbox here cannot run Vite (your `node_modules` holds Windows binaries and reinstalling them would have broken your dev machine):

1. The dashboard KPI row — confirm "Live Fusion Inputs" shows a count, not `-`, once the fusion resolves.
2. The `/water-stress` breakdown — confirm the `weight NN%` chips appear. If the API omits `weight` for a component, that chip is hidden by design.

---

## 1. High-impact UI/UX and demo tweaks

Ranked by score-per-minute-of-work. Judges see the screen for 4 minutes — anything not visible in those 4 minutes is worth zero.

### P0 — do these no matter what (≈45 min total)

| # | Fix | Why it scores |
|---|-----|---------------|
| 1 | **Pre-warm the backend before you present.** Your own README measures a cold `/analytics/water-stress` at ~11 s and `/recommendation` at ~4 s; warm they are ~300 ms. Hit both endpoints (and the pages you'll open) 2 minutes before you walk up. | 15 seconds of spinner in a 240-second demo is 6% of your time and reads as "not finished". Implementation Quality. |
| 2 | **`AQUAMIND_DEMO_MODE=true` in the presenting `.env.local`.** Rehearse once with `AQUAMIND_DEMO_FORCE_FIXTURES=true` to prove the walkthrough survives a dead venue Wi-Fi. | Fixtures carry `source: demo_fixture` and `data_quality: low`, so this is honest, not faked. A demo that survives the network is worth more than one extra feature. |
| 3 | **Put the problem statement's own words on the landing hero.** "Predict water shortages, leakages and groundwater depletion using weather, consumption, reservoir and sensor data" — verbatim, above the fold. | "Relevance to the problem statement" is a scored line item. Make it impossible to miss in the first 10 seconds. |
| 4 | **Surface provenance chips on the Water Stress page.** You already return `metadata.{component}.source` and `.method` (`trained_model` · `database_telemetry` · `weather_provider` · `engineering_estimate` · `rules_engine`). Render them as small labelled pills next to each component in the breakdown. | This is the single most credibility-dense pixel you can add. Almost no hackathon dashboard shows where each number came from. Technical Accuracy + Innovation. |
| 5 | **Make the drivers list visible without scrolling** on `/water-stress`. If the judge has to scroll to see *why* the score is what it is, the auditability story never lands. | Your core differentiator, currently possibly below the fold. |
| 6 | **Kill every placeholder, encoding artefact and truncated string** on the six pages you will actually open. Your own `PROTOTYPE_IMPROVEMENT_PLAN.md` flags "visible encoding and copy defects" — finish that item. | One mojibake character in a screenshot costs more Implementation Quality than a missing feature. |

### P1 — high visibility, do if time remains (≈45 min)

| # | Fix | Why it scores |
|---|-----|---------------|
| 7 | **Make the scenario slider recolour the WSI number in place** (Low→Moderate→High→Critical) with the stage word changing next to it. | This is your demo's peak moment. A number that visibly moves when a judge's imagined drought is applied is the thing they will remember at scoring time. Innovation. |
| 8 | **Show a data-freshness timestamp and the `stale` pill in the dashboard header.** You already track `{status, data, error, updatedAt, stale}` per panel — expose it. | Proves you distinguish loading / empty / failed / stale. Almost no prototype does. Implementation Quality. |
| 9 | **One-click path from an alert to its ranked action.** Alert Centre → Decision Intelligence, carrying the asset. | Turns "dashboard" into "decision system" visually, in two seconds, without saying it. |
| 10 | **Pin a deterministic demo state**: one reservoir, one well, one site name for AquaLens with a prior scan already stored (so the before/after trend renders instantly), one acoustic sample. | Removes the "which one do I click" hesitation that eats 20 seconds and reads as unfamiliarity with your own product. |
| 11 | **Open the Readiness panel once** near the end (`/readiness` — DB latency, which artefacts are loaded, provider configuration, demo mode). | Judges rarely see a prototype that self-reports its own dependency health. 8 seconds, disproportionate credibility. |

### P2 — presentation hygiene (10 min, do not skip)

- Browser at 100% zoom, full screen (F11), bookmarks bar hidden, no dev tools, OS notifications off, second monitor mirrored not extended.
- Dark mode or light mode — pick one and stay in it. Do not toggle themes on stage.
- Log **out** before you start. Spend 8 seconds logging in on stage: it proves the auth and RBAC are real, which is otherwise invisible and is worth Implementation Quality points.
- Have the four modules you are *not* demoing already open in background tabs, ready for Q&A.

---

## 2. The 4-minute demo script

Six stops. Five would be safer; seven is too many. Demo driver speaks; nobody else interrupts.

**Rehearse this twice with a timer. The most common failure is spending 90 seconds on the dashboard and rushing the ending.**

| Time | Screen | What you say (compressed) | What you click |
|------|--------|---------------------------|----------------|
| **0:00–0:30** | Landing → Login | "Our problem statement asked for shortage, leakage and groundwater prediction from weather, consumption, reservoir and sensor data. Every one of those is a live module here. This is a real login — every route except health checks is behind JWT with four roles." | Land on hero, read the one-line promise, log in. Do not linger. |
| **0:30–1:15** | Dashboard / Command Centre | "This is the operations view. One number at the top: the Water Stress Index, currently *X*, stage *Y*. It is a weighted fusion of shortage, groundwater, leakage, demand and climate. Next to it — Live Fusion Inputs, *N* of 5 reporting: the system tells you how much of itself is actually online right now rather than quietly filling gaps. Reservoirs and leak alerts render first; the fusion streams in behind them, because it is the expensive call and we do not block first paint on it." | KPI row → **point at Live Fusion Inputs** → map → alert centre. Point, don't scroll aimlessly. |
| **1:15–2:10** | `/water-stress` **(the hero moment)** | "This is the regional view — same idea, scoped to one region, and the header says so. Look at the fusion breakdown: every input carries the weight the model actually applied, printed next to its contribution and read straight from the API response. Nothing here is a design decision; you can check it against the endpoint. Now watch what happens if rainfall drops 20% and reservoir storage falls to 34%." | Component breakdown → **point at the `weight NN%` chips** → drivers → **drag the scenario sliders and let the index move on screen.** Pause for one beat after it changes. |
| **2:10–2:50** | AquaLens (`/vision-analysis`) | "Satellite or drone imagery of a water body. The model returns hydrology metrics — health score, water spread, shoreline exposure, algae risk — with its own confidence. We store every scan against a site name, so re-uploading gives you a before/after delta and a trend. And this is evidence *alongside* the index, deliberately not a weighted input, because we haven't validated it enough to let it move the score." | Upload the pre-chosen image → show metrics → show the site trend. |
| **2:50–3:35** | `/decision-intelligence` | "A score is not a decision. This ranks what to do first when a leak, a dry aquifer and a heatwave compete for the same crew. Every recommendation reports which path produced it — remote AI, our local rules engine, or a demo fixture — so a rules result can never be dressed up as AI." | Ranked actions → strategy comparison → point at the source label. |
| **3:35–4:00** | Settings → Readiness, then stop | "Last thing: the system reports its own health — database latency, which model artefacts are loaded, which providers are configured. There are four more modules I haven't opened — reservoir forecast, demand, leak detection, climate risk. Ask me and I'll open any of them." | Readiness panel. Then **stop talking and hand over.** |

**Two lines to have ready if something breaks:**

- Slow load: "That's the cold fusion path — it reloads four models. Warm it's about 300 milliseconds, and we don't block first paint on it." (Keep talking, don't stare at the spinner.)
- Provider down: "That's demo mode falling back to a stored fixture — you can see it's labelled `demo_fixture` with data quality low. We'd rather show you a labelled fixture than a fabricated number."

---

## 3. Slide-by-slide structure (the deck is built)

`AquaMind_AI_Pitch_Deck.pptx` — 10 slides, timings in the speaker notes. Total narration ≈ 4:00.

| # | Slide | Guideline factor covered | Time | Speaker |
|---|-------|--------------------------|------|---------|
| 1 | AquaMind AI — title + roles | Team/individual identity | 0:20 | P1 |
| 2 | Four signals, four clocks, zero shared answer | Ideation / original idea (the gap) | 0:25 | P1 |
| 3 | The Water Stress Index — one score you can audit | Ideation / original idea (the solution) | 0:30 | P1 |
| 4 | How the platform is assembled | Technical plan / product specification | 0:30 | P1 |
| 5 | From public datasets to a running system | Materialising process + implementation steps | 0:30 | P1 |
| 6 | We publish our held-out numbers — including where we lose | Technical accuracy (evaluation criterion) | 0:35 | P2 |
| 7 | Who is better off, and how | Social impact and benefits to society | 0:25 | P2 |
| 8 | Sold to the people who already own the pipes | Business model + revenue + growth expectations | 0:30 | Business lead |
| 9 | What we built on, and on what terms | Technical platform + legal software considerations | 0:20 | P2 |
| 10 | What runs now — and what comes next | Output and future plans | 0:25 | P2 |

**Before you present:** replace the placeholder names on slide 1 (Presenter 1 / Presenter 2 / …) with real names, and fill in team name + institute at the bottom.

Handoffs: P1 → P2 happens between slides 5 and 6 (natural break — the tone shifts from "what we built" to "how honest we are about it"). P2 → Business lead between 7 and 8. Business lead → P2 between 8 and 9. Each handoff is a walk, not a sentence: do not say "and now over to…", it costs 3 seconds each time.

---

## 4. Jury Q&A — the five sharpest questions

Two minutes means roughly **three questions, 35–40 seconds each**. Answer, then stop. The most common Q&A failure is a 90-second answer that eats the other two questions.

### Q1. "Your shortage model doesn't beat a persistence baseline. Why is this useful?"

*Almost certain to be asked if a technical judge reads slide 6. Have the answer memorised.*

"Correct, and we publish that rather than hiding it. Shortage trains on a single March 2024 CWC extract — the test partition spans very few unique calendar days, so persistence is extremely hard to beat by construction. What the prototype proves is the end-to-end contract: ingestion, chronological evaluation, fusion, decision output. Replace that one month with multi-season storage and station-matched rainfall and the same pipeline retrains without a line of interface code changing. We'd rather ship a system whose weakness is a dataset than one whose weakness is a claim."

### Q2. "How did you choose the WSI weights? Aren't they arbitrary?"

*The sharpest available question, and the one most teams fumble.*

"They're a transparent heuristic, not a learned parameter — and we say so. Three things make that defensible: we publish them in every API response so nobody has to guess; the what-if endpoint lets you re-fuse under any override, so their sensitivity is inspectable rather than hidden; and they're configuration, so a utility that knows its own system is leakage-dominated can re-weight it. Learning the weights needs labelled stress outcomes over multiple seasons, which is exactly the data a pilot deployment would generate."

### Q2b. "The dashboard index and the Water Stress page use different weights. Which one is the real index?"

*This is the question a genuinely sharp judge asks, and the reason the page was retitled. Know it cold.*

"Both, and they answer different questions. The dashboard carries the **system-wide** Water Stress Index — shortage 30, groundwater 25, leakage 20, demand 15, climate 10 — fused across the whole network. The Water Stress page is the **regional** Stress Intelligence module: demand and reservoir at 28 each, then rainfall, groundwater, population and recent history. A network-level index and a per-region index shouldn't share a weight vector, because leakage is a network property and population is a regional one. Every weight is returned in its own API response and printed on the screen, which is exactly how you were able to notice the difference."

### Q3. "How does this scale from a SQLite prototype to a state?"

"The scaling boundary is already drawn. The API is stateless FastAPI behind an Express proxy, containerised with Docker Compose and CI on every push; the database is SQLAlchemy with `DATABASE_URL`, so it's a connection-string change to PostgreSQL. The expensive path is the fusion call — measured at about 11 seconds cold, 300 milliseconds warm — so it's cached with TTLs and the dashboard loads in tiers rather than one blocking batch. What's genuinely outstanding for scale-out, and I'd rather tell you than have you find it: Alembic migrations instead of `create_all`, and multi-tenancy for more than one utility on one deployment."

### Q4. "Isn't this just a wrapper around Gemini?"

"No, and that's a deliberate architectural choice. The four predictive models are local scikit-learn artefacts and the decision ranking is a local rules engine — the entire index and the action queue answer with no LLM in the path. Gemini does two bounded things: phrasing recommendations, and vision analysis. And it only ever receives compact numeric context, never raw user text, so there's no prompt-injection surface. If it's unreachable, the local rules fallback produces the same actions and the response is labelled `rules_fallback` — we never dress a rules result up as AI."

### Q5. "Who pays for this, and why wouldn't a utility build it themselves?"

*Business lead answers this one.*

"The buyer is the utility or the municipal water board — they already carry a budget line for water loss and emergency supply. The wedge is a paid 90-day single-city pilot retrained on their own historical feed, with a success metric agreed before we start, then a per-utility annual licence priced on served population. They don't build it in-house for the same reason they don't build their own SCADA: the hard part isn't any single model, it's the fusion, the provenance discipline and the evaluation rigour, and that's a maintained product, not a one-off project. I'd also say plainly — we have not validated a market-size number we could stand behind, so I'm not going to quote you one."

### Q6 (if asked). "What's the biggest weakness you haven't mentioned?"

*If you get this, you have already won the trust battle. Answer fast and concretely.*

"The acoustic model is lab-trained, not field DMA data, and the litres-per-minute figure is an orifice-flow heuristic rather than a learned output. Both are labelled as such in the API. Field labelling is the first thing a pilot buys us."

---

## 5. The next three hours — prioritised checklist

Time-boxed backwards from the presentation. **Freeze code at T-45 minutes.** Nothing after that is worth the risk of breaking a working demo.

### T-180 → T-150 · Lock the demo path (all 5, together, 30 min)
- [ ] Walk the six-stop demo route end to end once, in the room's conditions if possible. Time it.
- [ ] Choose and fix the exact demo entities: one reservoir, one well, one AquaLens site name, one acoustic file. Write them on paper.
- [ ] Pre-run one AquaLens scan on the chosen site name so the before/after trend has history.
- [ ] Note every page that stalls, errors, or shows a defect. That list is the work queue below.

### T-150 → T-90 · P0 fixes (frontend pair, 60 min)
- [x] ~~Problem-statement wording on the landing hero (P0-3).~~ **Done — see §0b.**
- [x] ~~Weight chips on the Water Stress breakdown (P0-4).~~ **Done — see §0b.**
- [x] ~~Encoding sweep.~~ `python scripts/check_encoding.py` passes on 338 files.
- [ ] **Run the app once and eyeball the three changed screens** (landing, dashboard KPI row, `/water-stress` breakdown). This is the only verification that could not be done for you — Vite could not be run here without reinstalling `node_modules` and breaking your Windows binaries.
- [ ] Drivers visible without scrolling on `/water-stress` (P0-5) — still open.
- [ ] `AQUAMIND_DEMO_MODE=true` set in the presenting machine's env; one rehearsal with `FORCE_FIXTURES=true` (P0-2).

### T-150 → T-90 · In parallel (presenters, 60 min)
- [ ] Real names + team name + institute onto slide 1.
- [ ] Each presenter reads their slides' speaker notes aloud twice, standing.
- [ ] Business lead rehearses Q5 verbatim.
- [ ] Everyone memorises the four numbers on slide 6. If a judge asks "what's your groundwater R²", the answer is "0.5176 on the held-out test, 0.8251 on validation, and the gap is distribution shift" — said without looking.

### T-90 → T-60 · P1 fixes, only if P0 is fully green (30 min)
- [ ] Scenario slider recolours the index (P1-7) — highest demo value.
- [ ] Freshness timestamp / stale pill in header (P1-8).
- [ ] Skip P1-9 and P1-10 if either looks like more than 15 minutes. A half-wired feature is worse than no feature.

### T-60 → T-45 · Full dress rehearsal (all 5, 15 min)
- [ ] Slides start to finish with a timer. If you're over 4:00, cut words from slides 4 and 5, not from 6.
- [ ] Demo start to finish with a timer, on the presenting laptop, on the presenting browser profile.
- [ ] The floater watches and calls out every stumble. Fix delivery, not code.

### T-45 · Code freeze
- [ ] `git commit` everything. Do not touch the repo again.
- [ ] Confirm both servers start clean from cold: uvicorn on :8000, `npm run dev` on :3000.
- [ ] Take screenshots of all six demo pages in a working state. If the live demo dies, you present screenshots and keep your composure — that costs you far less than freezing.

### T-15 → T-0 · Room setup
- [ ] Both servers running, laptop plugged in, sleep disabled, notifications off.
- [ ] **Pre-warm:** load dashboard, `/water-stress`, and decision intelligence once so every cache is hot. Then log out.
- [ ] Browser full screen, 100% zoom, bookmarks hidden, background tabs opened for the four Q&A modules.
- [ ] Deck open in presenter view; phone timer on the demo driver's podium set to 4:00.
- [ ] Water. Genuinely — you're presenting for ten minutes about water.

---

## 6. What I could not verify

Stated plainly, per your accuracy rules:

- **Market size, water-loss percentages, and cost-of-non-revenue-water figures** — I have not included any, because I cannot cite a verified primary source for them from here. If you want a market number on slide 8, pull it yourself from a citable source (a national water board report, a published utility audit) and put the citation on the slide. An uncited figure is a Q&A trap.
- **Impact claims on slide 7** are written as *intended outcomes of a pilot*, not measured results, with that caveat printed on the slide. Keep it that way unless you have a measured baseline.
- **Licence statements on slide 9** describe your engineering posture. The permissive licensing of React, FastAPI, SQLAlchemy and scikit-learn is well established, but the terms attached to the specific CWC/CGWB extracts you used should be re-read by you before you make any commercial claim about them.
- **The model metrics on slide 6** are transcribed from your README's model-metrics table. Confirm they still match `ai/*.metadata.json` if you have retrained since that table was written.

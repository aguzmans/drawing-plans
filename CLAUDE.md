# Engineering rules — draw-plans

This is a product that will be used by many contractors. Build it like one. These
rules are binding for anyone (human or AI) working in this repo. If a rule blocks
you, raise it — don't quietly break it.

## 1. Docker-first

- Every runnable component ships with a `Dockerfile` and is run via Docker. The
  viewer runs in Docker in dev and in production; `docker compose up -d viewer`
  is the canonical way to start it. Do not rely on a host Python environment for
  anything shippable.
- `docker compose` is the source of truth for how services fit together (ports,
  networks, volumes, health checks). Add new services there, not in ad-hoc scripts.
- Containers bind `0.0.0.0` and take config from env / CLI flags, never hard-coded
  host paths.

## 2. Dependencies: pinned, latest-stable, deliberate

- **Pin exact versions** (`pkg==X.Y.Z`) in `requirements.txt`. No ranges, no
  unpinned installs, no `latest` tags on base images — pin the base image too
  (e.g. `python:3.13.15-slim`).
- Use the **current stable latest release** of each package. Before pinning or
  bumping, **verify the version on PyPI / the source** — do not trust memory
  (model knowledge lags real releases).
- **Separate runtime deps from dev/test deps** (`requirements.txt` vs
  `tests/requirements.txt`). Keep runtime deps minimal — only what the service
  actually imports.
- Bumping a pin is a deliberate change: note why, and re-run the E2E suite.

## 3. Testing: Playwright E2E, and verify in a real browser

- UI/behaviour is covered by **Playwright E2E tests** (`viewer/tests/e2e/`) that
  run against the containerised service via `docker compose run --rm e2e`.
- **Never claim a UI change works without seeing it in a real browser.** Static
  SVG/rsvg checks are not sufficient — the stroke-width "blob" bug passed a
  static raster and only showed up in a browser (`vector-effect:non-scaling-stroke`
  is browser-only). When in doubt, screenshot via Playwright.
- **Every fixed bug gets a regression test.** (e.g. `test_strokes_are_not_a_blob`.)
- Tests must actually pass, headless, from a clean build. A skipped or commented
  test is a failing test.

## 4. No AI slop

Concretely, that means:

- **No dead or speculative code.** Don't add abstractions, options, or config for
  cases that don't exist yet. Build for the requirement in front of you.
- **Delete, don't comment out.** Git is the history. No `# old version` blocks,
  no `_v2` copies left beside the original.
- **No placeholder content.** No lorem, no fake sample data presented as real, no
  "TODO: implement" in a path that's claimed as done.
- **Match the surrounding code** — its naming, structure, comment density. New
  files should look like they belong.
- **One source of truth.** Don't duplicate the same data/logic in two places
  (e.g. layer→colour mapping lives in one spot).
- **Comments say *why*, not *what*.** If a comment restates the code, cut it.
- **Right-size the change.** Don't rewrite a working module to add one feature;
  don't gold-plate a throwaway script.

## 5. Domain correctness & provenance (this is infrastructure)

- Coordinates are **SVY21 (EPSG:3414)**, levels **SHD** — per the SLA *Standard
  and Specifications for Utility Survey in Singapore*. Don't silently work in a
  local frame.
- **Every real-world number is sourced or marked assumed.** Clearances, cover
  depths, costs, quality levels: tag `# SLA` / `# SS576` / etc. for authoritative
  values and `# ASSUMED` for placeholders. A placeholder must never be presented
  as authoritative.
- **Faithfulness first for ingestion.** Read true geometry (vector PDF, converted
  DXF) over OCR/guessing. If a source is a scan, that's the *only* place vision/OCR
  enters, and its output stays low-quality-level (wide clearance) until a human /
  survey confirms it.
- The tool **plans**; it never substitutes for the legal positive-location step
  (cable plans → earthworks notice → LCDW/TCDW → trial holes). Outputs must say so.

## 6. Repo layout

```
viewer/            containerised CAD viewer (its own deps, Dockerfile, compose, tests)
prototype/         route-optimisation prototype (planner/export/render/report)
docs/              research, architecture, status, discovery questions
data/, out/        converted inputs / generated outputs
examples/          the real source files (DWG + provider PDFs)
```

## 7. Before you say "done"

1. It builds from a clean `docker compose build`.
2. `docker compose run --rm e2e` is green.
3. You (or Playwright) have looked at the actual result.
4. New numbers are sourced or marked `# ASSUMED`.
5. No dead code, no commented-out blocks, deps still pinned.

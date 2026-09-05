# draw-plans — utility-line planning assistant (research + prototype)

Deterministic + LLM + vision system that helps contractors draw underground utility
plans and produces **cheapest / lowest-effort / balanced** route alternatives as a
finished CAD file plus drawings and a written method statement.

Scope, standards and tooling target: **Singapore (SVY21)**, mixed utilities, **AutoCAD DWG**
output. See the questions answered up front in `docs/`.

## Layout
```
docs/research-and-architecture.md   ← the analysis: problem, free-software landscape,
                                       LLM/vision design, full architecture, roadmap
prototype/                          ← runnable end-to-end deterministic core
  config.py     standards, costs, clearances, layers  (SLA=sourced, ASSUMED=placeholder)
  scenario.py   builds the input scene (topo + third-party utilities) → DXF
  planner.py    shapely + networkx: conflict model + 3-objective route optimisation
  export.py     ezdxf → DXF (SLA layers, SVY21); DXF→DWG via ODA/LibreDWG if present
  render.py     matplotlib plan-view drawings of the scene and each alternative
  report.py     method statements + comparison + recommendation (Markdown)
  run.py        orchestrates the whole pipeline
out/                                ← generated deliverables (DXF, PNG, DESIGN_REPORT.md)
examples/TOPO.dwg                   ← the provided example (see note below)
```

## Run
```bash
python -m venv venv && . venv/bin/activate
pip install ezdxf shapely networkx matplotlib
cd prototype && python run.py
```
Outputs appear in `out/`: `combined_alternatives.dxf`, `alt_{cost,effort,balanced}.dxf`,
matching `.png` drawings, `comparison.png`, and `DESIGN_REPORT.md`.

## Deliverables produced
- **Finished CAD** — per-alternative + combined DXF on SLA-style layers in SVY21
  (DWG on submission; converter auto-detected).
- **Drawings of alternatives** — plan views with legend and highlighted live-service
  crossings.
- **Documented explanation** — comparison table, recommendation, and a per-option method
  statement explaining *how to build it and why the route is what it is*.

## Notes / caveats
- `examples/TOPO.dwg` is owned by another user with restrictive permissions; it could not
  be read in this environment. Run `chmod 644 examples/TOPO.dwg` (or `chown`) to let the
  ingestion path parse it. The prototype uses an equivalent synthetic scene meanwhile.
- Cost/clearance numbers marked `# ASSUMED` in `config.py` are realistic placeholders and
  **must** be replaced with PUB/SP/City Energy/IMDA/LTA code-of-practice values before use.
- This is a prototype of the **deterministic core** plus export/drawing/report. The
  vision + LLM ingestion and the Claude-authored narrative are designed in `docs/` and are
  the next build steps.

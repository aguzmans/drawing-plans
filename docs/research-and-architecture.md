# Utility-line planning assistant — research & architecture

**Deterministic core + LLM + vision, for underground utility route design in Singapore.**
Prepared 2026‑09‑05. Region: Singapore (SVY21). Utilities: mixed/general. Output: AutoCAD DWG.

---

## 1. The problem, precisely

A contractor has to install a new underground line (duct/cable/pipe) along or across a
street. What they start with:

- **A CAD base map** — usually a topographic survey (`TOPO.dwg`): kerbs, road edges,
  building lines, levels, survey control points. Clean vector geometry, known coordinate
  system.
- **Several third‑party PDFs** — as‑built / record drawings from the *other* asset owners
  who share the same corridor (PUB water & sewer, SP PowerGrid, City Energy gas,
  IMDA/telco ducts, LTA/PUB drainage). These are heterogeneous: some are vector PDFs
  exported from CAD, many are **scanned raster** plans of varying age, scale and quality,
  each with its own legend, symbology and datum.

What they must produce:

- **A finished CAD file** (DWG for SLA submission) with the new line, chambers and
  crossings drawn on correct layers, in **SVY21** coordinates.
- **A documented method** — how to build it and *why* the route is what it is.
- **Alternatives** — at least *cheapest*, *lowest‑effort/risk*, and *balanced*, each drawn
  and explained.

The design tension the contractor is actually optimising:

| Lever | Cheap / easy | Expensive / hard |
|---|---|---|
| Excavation | machine trencher on open verge | hand‑dig near a live asset |
| Surface | grass verge | footpath → carriageway (reinstatement + traffic mgmt) |
| Crossings | none (route around) | cross a live gas/HV line (expose, support, permits, standby) |
| Method | open‑cut | trenchless (HDD/bore) under obstacles |
| Clearance | keep statutory separation | encroach (not allowed) |

The job is to search that trade space and present a few defensible points on it.

> **Note on the example file.** `examples/TOPO.dwg` (183 KB) is owned by `root` with `600`
> permissions and the whole `examples/` directory is owned by another UID, so it could not
> be read in this environment. `chmod 644 examples/TOPO.dwg` (or `chown`) unblocks it. The
> ingestion design below is what would run against it; the prototype uses an equivalent
> synthetic scene so the pipeline is exercised end‑to‑end regardless.

---

## 2. Why *hybrid* (deterministic + LLM + vision), not one or the other

The three technologies are good at different things, and safety-critical infrastructure
work makes the boundaries sharp:

- **Deterministic geometry & optimisation must own anything that can be wrong in a way
  that hurts.** Clearances, cost, crossing counts, the actual route coordinates — these
  have to be exact, reproducible and auditable. An LLM must never *invent* a line
  position. This is `shapely` + graph search, and it is the part a regulator or a claims
  process can re-run.
- **Vision owns "turn a picture of a plan into geometry."** Detecting where a pipe is
  drawn on a scanned PDF, reading a legend, associating a label with a line. This is
  inherently perceptual and noisy.
- **LLMs own ambiguity and language.** Which legend entry means "abandoned"? Is this note
  a depth or a diameter? What does clause X of the PUB code imply for separation here?
  And — the last mile — writing the method statement and the rationale in prose an
  engineer will accept.

The rule of thumb the architecture follows: **LLM/vision to get structured facts *in* and
readable narrative *out*; deterministic code for every number in between, with a human
signing off at the survey‑quality gates.**

---

## 3. State of the art — free / open-source software, mapped to the pipeline

Everything below is free to use; ⚠ marks tools that are free-of-charge but not open-source,
or that have reliability caveats worth knowing.

### 3.1 CAD read / write / convert
| Tool | Role | Notes |
|---|---|---|
| **ezdxf** (BSD, Python) | read/write **DXF**, query & create entities, layers | The workhorse. v1.4.x. Cannot *write* DWG itself. |
| **ODA File Converter** ⚠ | DWG ⇄ DXF, any version | Free-of-charge, closed-source (Open Design Alliance). ezdxf's `odafc` addon drives it. Most reliable DWG path. |
| **LibreDWG** (`dwg2dxf`/`dxf2dwg`, GPL) | DWG ⇄ DXF | Reads r13–r2018, writes DXF and r13–r2000 DWG. Beta: some R2010+ entities skipped; large assemblies can fail. Good enough for typical single-sheet plans; verify output. |
| **FreeCAD** (LGPL) | DWG/DGN import (bundles LibreDWG), 3D | Useful for MicroStation `.dgn` and headless conversion. |
| **QGIS + DXF** (GPL) | GIS ↔ CAD, styling, layouts | Natural home if an open-source working environment is acceptable. |
| **GDAL/OGR** (MIT) | DXF/DWG(via ODA)/Shapefile/GeoPackage, reprojection | The glue for coordinate transforms and format bridging; `ogr2ogr`. |

**Practical DWG stance for this project:** author in DXF with `ezdxf` (full control over SLA
layers/attributes), then convert DXF→DWG with **ODA File Converter** (preferred) or
**LibreDWG** for the SLA submission. The prototype's `export.try_convert_dwg()` already
calls whichever is on `PATH`.

### 3.2 Reading the third-party PDFs (the vision problem)
| Tool | Role |
|---|---|
| **PyMuPDF (fitz)** / **pdfplumber** (open) | Split *vector* PDFs — pull existing lines/text directly, no ML needed. Always try this first; many "record" PDFs are vector and give near-perfect geometry. |
| **pdf2image / Poppler** (GPL) | Rasterise scanned PDFs to images for CV. |
| **OpenCV** (Apache) | De-skew, line/segment detection (Hough, LSD), morphology, contour extraction, template matching for symbols. |
| **Tesseract** / **PaddleOCR** (open) | OCR of labels, dimensions, legends, title blocks. |
| **YOLO / YOLOv11-obb** (open) | Oriented object/symbol detection (valves, manholes, GD&T-style annotations). Current research pairs YOLOv11-obb for localisation with a small VLM for parsing. |
| **Vision-Language Models** | Read a plan region and return structured JSON (what line, what size, what status). See §3.4. |

The current literature (2024–2026) converges on a **hybrid CV+VLM** pattern: a detector
localises annotations/symbols, a VLM parses each patch to structured text; reported F1 is
high for numeric/textual fields and weaker for free symbology — which is exactly why a
human QL gate stays in the loop.

### 3.3 Georeferencing / registration
Third-party plans rarely share the topo's coordinate frame. To overlay them you register
each to SVY21:
- **QGIS Georeferencer** / **GDAL** (`gdal_translate -gcp`, `gdalwarp`) — GCP-based affine/
  polynomial/TPS warping of raster plans onto known control.
- **OpenCV** `findHomography` / feature matching — automatic alignment when common features
  (kerb lines, building corners, control marks) are detectable.
- **pyproj** (open) — coordinate transforms (EPSG:3414 SVY21 ↔ WGS84 etc.).

### 3.4 LLM / VLM layer (Claude-first)
- **Claude (Opus 4.8 / Sonnet 5)** — strong vision + long context + tool use. Roles here:
  (a) **structured extraction** from plan images/patches → JSON of existing utilities
  (type, size, status, QL, notes); (b) **standards reasoning** — read a code-of-practice
  PDF and emit the clearance/cost tables the deterministic core consumes; (c) **narrative
  generation** — turn the optimiser's structured result into the method statement and the
  "why this route" rationale (the prototype's `report.py` is the deterministic scaffold the
  LLM expands). Use the **Anthropic API** with tool-use for schema-constrained JSON so the
  model returns validated data, never prose the pipeline has to parse.
- **Open alternatives** if on-prem/offline is required: Qwen2.5-VL, InternVL, and the
  fine-tuned Donut/YOLO stacks from the engineering-drawing papers. Trade capability for
  data-residency.
- **Guardrail:** the LLM proposes; the deterministic core disposes. Every extracted line
  gets a confidence + QL and is shown to the engineer before it can constrain a route.

### 3.5 Geometry, routing & optimisation (the deterministic core)
| Tool | Role |
|---|---|
| **Shapely** (BSD) | All 2D geometry: buffers (clearance), intersection (crossings), distance, containment (obstacles). Prototype uses this. |
| **NetworkX** (BSD) | Grid/graph shortest-path for route alternatives. Prototype uses this. Swap for **igraph**/**scikit-image.graph** at scale. |
| **Google OR-Tools** (Apache) | When the problem grows to multi-line, capacitated, or corridor-sharing optimisation (routing + scheduling). |
| **PostGIS + pgRouting** (GPL) | Production-scale spatial store + network routing over real city data. |
| **GRASS GIS** (GPL) | Raster cost-surface / least-cost-path if you prefer a continuous cost field to a graph. |
| **SciPy / NumPy** | Numerics, cost-surface math, Pareto filtering across alternatives. |

### 3.6 Singapore data & standards (grounding)
- **SLA "Standard and Specifications for Utility Survey in Singapore" v1.3 (Oct 2025)** —
  the governing spec. Confirms: horizontal datum **SVY21 (EPSG:3414)**, vertical **SHD**,
  positioning via **SiReNT**, accuracy/quality classes **±100/±300/±500 mm / unknown /
  trenchless**, as-built to **±100 mm** by a Registered Surveyor, deliverables in
  **`.dwg` / `.dgn` / `.shp`** with a fixed **attribute schema**, submitted via the SLA
  **Utility Survey Submission Portal (USSP)**.
- **SLA Digital Underground / "SUR" underground-infrastructure data sharing** — the
  emerging single source for existing-utility data; the long-term replacement for chasing
  third-party PDFs one owner at a time.
- **Per-owner codes of practice** (PUB, SP, City Energy, IMDA, LTA) — the *authoritative*
  source for clearances, cover depths and crossing rules. These populate the config tables;
  the prototype ships representative placeholders clearly marked `# ASSUMED`.

---

## 4. Target architecture

```
        ┌─────────────────────────── INPUTS ───────────────────────────┐
        │  TOPO.dwg (base)          third-party PDFs (vector + scanned) │
        └───────┬───────────────────────────┬──────────────────────────┘
                │ ezdxf / ODA                │ PyMuPDF (vector) │ Poppler→OpenCV (raster)
                ▼                            ▼
        ┌───────────────┐          ┌──────────────────────────────┐
        │ Base geometry │          │ VISION: detect lines/symbols │
        │ (layers,ctrl) │          │ OCR labels/legend            │
        └───────┬───────┘          └───────────────┬──────────────┘
                │                                   │ patches + text
                │                                   ▼
                │                        ┌──────────────────────────┐
                │                        │ LLM (Claude): structured │
                │                        │ extraction → utilities    │
                │                        │ {type,size,status,QL,geom}│
                │                        └───────────────┬──────────┘
                ▼                                        ▼
        ┌──────────────────────────────────────────────────────────┐
        │ GEOREFERENCE & MERGE → single SVY21 world model           │  ← human QL gate
        │ (GDAL/QGIS/OpenCV registration; pyproj transforms)        │
        └───────────────────────────────┬──────────────────────────┘
                                         ▼
        ┌──────────────────────────────────────────────────────────┐
        │ DETERMINISTIC CORE (shapely + networkx)                   │
        │  • clearance buffers (code + QL uncertainty)              │
        │  • cost model ($) and effort/risk model                   │
        │  • hard constraints: obstacles, parallel-encroachment     │
        │  • solve COST / EFFORT / BALANCED (+ Pareto set)          │
        └───────────────────────────────┬──────────────────────────┘
                                         ▼
        ┌──────────────────────┐   ┌──────────────────────┐   ┌───────────────────────┐
        │ CAD OUT: ezdxf→DXF   │   │ DRAWINGS: matplotlib │   │ NARRATIVE: LLM from   │
        │ →DWG (ODA/LibreDWG)  │   │ plan views + legend  │   │ structured metrics    │
        │ SLA layers/attrs     │   │ per alternative      │   │ method + rationale    │
        └──────────────────────┘   └──────────────────────┘   └───────────────────────┘
```

**Which stage is which technology, and why:**

- *Vision + LLM* only at ingestion (perception + ambiguity) and at the very end (prose).
- *Deterministic* for the world model, clearances, costs and the route — the auditable
  spine.
- *Human* at the **QL gate**: nothing an ML step extracted becomes a hard constraint until
  an engineer confirms it, and trial holes upgrade critical assets to QL-A before machine
  work. The optimiser propagates survey uncertainty by *widening the clearance buffer* for
  low-QL assets (implemented: `buffer = clearance + QL_tolerance`), so "we're not sure
  where it is" automatically makes the planner give it a wider berth.

---

## 5. The prototype (built here)

A runnable end-to-end slice of the deterministic core plus the export/drawing/report
stages. See `prototype/` and `../out/`.

**What it does**
1. Builds a realistic Singapore street scene (topo base + 11 existing third-party utilities
   + a chamber obstacle) and writes it to DXF — standing in for `TOPO.dwg` + the PDFs.
2. Re-reads that DXF (`ezdxf`) to prove the CAD read path.
3. Discretises the corridor into a weighted graph; prices every candidate trench segment on
   **two axes** — money (S$) and effort/risk — with hard constraints for obstacles and
   illegal parallel encroachment, and priced perpendicular crossings.
4. Solves three objectives (least cost / least effort / balanced) with Dijkstra.
5. Exports: **DXF per alternative + a combined DXF** on SLA-style layers in SVY21;
   **PNG plan-view drawings**; and a **Markdown method report** with a comparison table,
   a recommendation, and a per-option method statement + rationale.

**What it demonstrates — a real trade-off, and how method choice resolves it:**

| Option | Length | Cost (S$) | Live crossings | Bored | Risk |
|---|---:|---:|---:|---:|---:|
| Least cost (open-cut) | 172 m | 33,555 | 4 (gas ×2, power ×2) | 0 m | 44 |
| Least effort (open-cut) | 194 m | 35,588 | 0 | 0 m | 0 |
| **Balanced (trenchless-assisted)** | 172 m | 33,835 | **0** | 8 m | **0** |

With **open-cut only** there is a genuine trade: the cheapest line runs straight along the
cheap grass verge and hand-crosses four live services; removing those crossings means
detouring — longer and dearer. The **trenchless-assisted** option resolves it: keep the
short alignment and **bore ~8 m under the congested pinch-points**, giving zero live
crossings at almost the least-cost price. That is exactly the "machine on open ground is
cheap; crossing a live line is expensive manual work; boring under it is a priced
alternative" trade the brief describes — and the optimiser chooses per-segment where each
method wins.

**Run it**
```bash
python -m venv venv && . venv/bin/activate
pip install ezdxf shapely networkx matplotlib
cd prototype && python run.py      # outputs land in ../out/
```

**Faithfully labelled limitations (prototype, not product):**
- Scene is synthetic (real ingestion of `TOPO.dwg`/PDFs is designed in §4, not built).
- 2D planner; depth/cover and true 3D clashes are modelled only via the deep flag and
  clearance. Production needs 2.5D (invert levels, cover) and vertical clash checks.
- Costs/clearances are `# ASSUMED` placeholders — must be replaced by PUB/SP/City
  Energy/IMDA/LTA code values.
- Trenchless (HDD) **is** a per-segment method option in the solver (open-cut vs bore,
  chosen where each wins); still 2D and without pit-setup fixed costs or bore-length limits.
- Grid shortest-path gives one route per objective; production should return the **Pareto
  front** and let the engineer pick, and should smooth routes to construction-friendly
  geometry (min bend radius, standard offsets).
- The narrative is a deterministic template; wiring it to the Claude API is the intended
  next step (the structure is already schema-shaped for that).

---

## 6. Roadmap to production
1. **Real ingestion**: `TOPO.dwg` via ezdxf/ODA; PDF vector split (PyMuPDF) → CV/OCR →
   Claude structured extraction with a human QL gate.
2. **Standards as data**: use Claude to convert each owner's code-of-practice into the
   clearance/cost/depth tables; keep the `# ASSUMED`→authoritative swap auditable.
3. **2.5D**: invert levels and cover depth; vertical clash detection.
4. **Method options in the solver**: open-cut vs HDD/bore *(done — prototype chooses per
   segment)*; extend with pit-setup fixed costs, min/max bore lengths and depth checks.
5. **Pareto + explanation**: return the frontier; Claude explains each knee point.
6. **DWG/attribute compliance**: exact SLA layer names + attribute schema; validate against
   USSP requirements; round-trip test through AutoCAD/Civil 3D.
7. **Integrate SLA Digital Underground/SUR** as the existing-utility source as it matures.

---

## 7. Sources
- SLA, *Standard and Specifications for Utility Survey in Singapore*, v1.3 (Oct 2025) & v1.0
  (Aug 2017); SLA USSP; SLA Digital Underground.
- ezdxf documentation (odafc addon); LibreDWG (GNU) `dwg2dxf`/`dxf2dwg`.
- Engineering-drawing VLM literature, 2024–2026 (YOLOv11-obb + Donut/VLM hybrids for
  drawing information extraction).
- GDAL/OGR, QGIS, OpenCV, Shapely, NetworkX, Google OR-Tools, PostGIS/pgRouting project docs.

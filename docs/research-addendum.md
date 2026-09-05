# Research addendum — after the basics

Written 2026-09-05, after real-data ingestion + the dev viewer were working. This
focuses on the decisions that matter for the next phase (fusing the three files
into one SVY21 model) and for turning the prototype into a product. Sources are
linked inline.

---

## 1. Georeferencing the third-party PDFs onto SVY21 — the Phase-1 crux

The topo (`TOPO.dwg`) is already in SVY21. The two provider PDFs are **not to
scale** and carry no coordinates, so the whole of Phase 1 hinges on registering
them to the survey grid. The mature, boring, correct technique is **ground-control-
point (GCP) warping**: pick features whose real-world position is known, solve an
affine / polynomial / thin-plate-spline transform, resample. This is exactly how
scanned maps are georeferenced with **GDAL `gdalwarp`** or the **QGIS Georeferencer**
([QGIS tutorial](https://www.qgistutorials.com/en/docs/3/georeferencing_basics.html),
[GDAL walkthrough](https://kokoalberti.com/articles/georeferencing-and-digitizing-old-maps-with-gdal/),
[ArcGIS overview](https://pro.arcgis.com/en/pro-app/latest/help/data/imagery/overview-of-georeferencing.htm)).

**Our unfair advantage for automatic GCPs.** We already have the SVY21 topo, and it
contains features that *also* appear on the provider PDFs:

- **Utility manholes / chambers** — the topo has `S_MH-WD / -GAS / -SEW / -STARHUB`
  and `S_ELECTRIC-BOX`; the ESS plan draws the same chambers. Chamber centres are
  excellent point GCPs.
- **Road & kerb intersections, building corners** — shared, sharp, unambiguous.

So the pipeline is: extract candidate features from both sources → match them
(by proximity + type, LLM-assisted for the ambiguous ones) → solve a homography
(**OpenCV `findHomography`**) or feed GCPs to GDAL → warp the PDF-derived vectors
into SVY21. Manual GCP picking in QGIS is the reliable fallback and the human check.

**Extraction feeding the GCPs.** Both PDFs are vector, so `PyMuPDF.get_drawings()`
gives every path with its stroke/fill colour, and text with position — classify by
colour + nearby label (the approach the prototype already uses). Note the **`Pdf
Extract` QGIS plugin does almost exactly this stack — PyMuPDF + ezdxf → Shapefile/DXF**
([plugin](https://surveyorstories.github.io/pdfextract/)), which both validates our
tool choices and is worth trialing as a shortcut. Caveat found: true PDF **layer
(OCG) metadata is unreliable to extract** ([PyMuPDF discussion](https://github.com/pymupdf/PyMuPDF/discussions/4091)),
so colour+label classification — not PDF layers — is the right basis.

**Accuracy honesty.** Record plans are, at best, SLA QL-C/QL-D. Registration adds
its own error. So georeferenced utilities must stay tagged **low-QL with wide
clearance buffers**, and the output must still direct the contractor to the legal
positive-location step (below). We register to *plan*, not to *dig blind*.

---

## 2. The regulatory workflow the tool plugs into (Singapore)

This reframes the product: the "Services Plan.pdf" isn't incidental — obtaining it
is a **legal step**, and our tool sits inside a defined process. Under the
Electricity, Gas and Telecom Acts a contractor must:

1. **Obtain cable/gas/telecom plans** from SP PowerGrid (and others) before
   earthworks — that is precisely the provider PDF we were given.
2. Submit a **Notification for Commencement of Earthworks ≥ 7 days** beforehand.
3. Engage a **Licensed Cable Detection Worker (LCDW)** / Telecom CDW (TCDW) to
   positively locate cables on site.
4. Dig **trial holes (min 1 m × 1 m × 1 m)** to physically expose and confirm
   utilities before machine excavation.
5. Follow SP PowerGrid's **Letter of Requirements**; comply with **SS 576** (code of
   practice for earthworks near electricity cables).

Sources: [SP Group LCDW training](https://www.spgroup.com.sg/dam/jcr:6827e999-6502-4b8c-92fd-2611d53a1921/%20WSQ%20Detect%20and%20Locate%20Underground%20Power%20Cables.pdf),
[IMDA earthworks requirements](https://www.imda.gov.sg/-/media/imda/files/regulation-licensing-and-consultations/licensing/licenses/earthworks-requirementsversion10.pdf),
[SS 576 preview](https://www.singaporestandardseshop.sg/Product/GetPdf?fileName=180331112806SS+576-2012_Preview.pdf),
[contractor guide](https://www.cabledetectionsg.com/post/nce-guide-for-earthwork-contractors).

**Implication:** the LLM-authored method statement should be structured around these
exact steps (obtain plans → notify → LCDW/TCDW → trial-hole every crossing → open-cut
or HDD → reinstate → as-built to QL-A → USSP). That makes our output immediately
credible and submission-ready, not a generic write-up. The prototype's method
statement already gestures at this; now it can cite the real obligations.

---

## 3. Strategic timing — Singapore is nationalising this data

SLA's **Digital Underground** programme (with the Singapore-ETH Centre) is building a
national digital twin of subsurface utilities, and the **Utility Survey Submission
Portal (USSP)** is the consolidation point
([GovInsider](https://govinsider.asia/intl-en/article/singapore-centralises-data-sharing-for-underground-infrastructure-with-new-portal),
[Digital Underground](https://sec.ethz.ch/research/digital-underground.html)).
Timeline that matters to us: government agencies submitting since ~April 2026,
**private-sector data voluntary from late 2026, scaling across all utility sectors
by 2027.**

**So the "chase a PDF from each provider" problem is being solved nationally.** The
product strategy that falls out:

- **Now → 2027:** automated ingestion of provider PDFs (what we're building) is the
  bridge and the near-term value.
- **2027+:** design the ingestion layer with a **pluggable source interface** so the
  same conflict/route engine can consume **USSP / Digital Underground** data directly
  when it opens, with **OneMap** as the base map
  ([OneMap](https://www.sla.gov.sg/geospatial/onemap/)). The geometry, optimisation
  and CAD-output layers don't change — only the source adapter does.

---

## 4. Competitive landscape and our wedge

The incumbents are heavy enterprise SUE/GIS platforms:

- **Bentley OpenUtilities / Subsurface Utility Engineering** (on OpenRoads): fuses
  survey/CAD/GIS/DB sources, builds 3D models, runs **utility conflict/clash detection**
  ([Geo Week](https://www.geoweeknews.com/news/bentleys-new-subsurface-utility-engineering-breakthrough-technology-mitigates-risk-of-building-in-utility-congested-underground-environments),
  [Bentley SUE](https://www.inas.ro/en/bentley-civil-design/subsurface-utility-engineering)).
- **Esri ArcGIS Utility Network**: connected network modelling, tracing, rules-based
  editing of underground assets.

They are excellent at *managing modelled asset networks* and *3D clash detection*, but
they assume you already have clean, modelled data, and they are expensive and
specialist. **Our wedge is the opposite end:** take the *messy real inputs a
contractor actually receives* (record PDFs + a topo), automate them into a conflict
model, **optimise a route across cost / effort / HDD trade-offs**, and emit a
**finished CAD plan + a regulation-grounded method statement** — fast and
contractor-priced. We're not competing on enterprise asset management; we're the tool
that produces the submission.

---

## 5. Productising the viewer

The dev viewer (server-side `ezdxf`→SVG) is right for development, but for a product
the strong option is a **fully client-side DWG/DXF viewer**:

- **`mlightcad/cad-viewer`** — browser-only DWG **and** DXF via **libdxfrw compiled to
  WASM** + **three.js**; no backend
  ([repo](https://github.com/mlightcad/cad-viewer),
  [write-up](https://medium.com/@mlightcad/cad-viewer-a-high-performance-browser-only-dwg-dxf-viewer-for-the-future-of-web-cad-fc31dda3ed53)).
  This is notable because it reads **DWG directly in the browser** — potentially side-
  stepping the server-side ODA/LibreDWG step for viewing.
- Lighter DXF-only options: [`three-dxf`](https://github.com/gdsestimating/three-dxf),
  [`three-dxf-viewer`](https://github.com/ieskudero/three-dxf-viewer).

Recap of the one commercial decision (from the status doc): server-side **DWG
conversion** still wants **ODA SDK membership** for a product, or lean on LibreDWG
(GPL, separate process) / a WASM reader for viewing.

---

## 6. HDD vs open-cut — the evidence validates the per-segment optimiser

Industry guidance matches the prototype's core move: **HDD is often cheaper once
reinstatement, traffic management and disruption are counted — especially for
crossings and longer runs — while open-cut wins for short, shallow connections**, and
"**a mix of HDD and trenching is usually the most cost-effective**"
([Heartland](https://heartlandpipelines.co.uk/hdd-vs-open-cut-excavation/),
[For Construction Pros](https://www.forconstructionpros.com/equipment/underground/article/10298427/how-to-decide-when-to-use-a-trencher-or-horizontal-directional-drill)).
That is exactly the per-segment open-cut-vs-bore choice the optimiser makes. To make
it real, replace placeholder rates with quoted SG figures and add **pit-setup fixed
costs** and **min/max bore lengths** (HDD has a high fixed mobilisation, so it favours
longer/consolidated bores — a fixed cost the current per-metre model understates).

---

## 7. What this changes for the build plan

- **Phase 1 (fuse):** implement shared-feature GCP registration (manholes + road
  corners as control), PyMuPDF colour/label extraction, tag everything low-QL with
  wide buffers. Trial `Pdf Extract` as a shortcut. Human GCP check in QGIS.
- **Phase 2 (model):** ingest the real code-of-practice clearances (SS 576 etc.);
  keep costs as data.
- **Phase 4 (narrative):** structure the method statement on the real legal workflow
  (obtain plans → 7-day notice → LCDW/TCDW → trial holes → build → as-built → USSP).
- **Phase 5 (productise):** pluggable data-source adapter (PDF now, **USSP/Digital
  Underground from 2027**); consider a WASM client viewer; resolve DWG licensing.
- **Cost model refinement:** add HDD mobilisation/pit fixed costs and bore-length
  bounds.

---

## Sources
Georeferencing: QGIS Georeferencer tutorial; GDAL old-maps walkthrough; ArcGIS
georeferencing overview. Extraction: PyMuPDF vector graphics (Artifex); `Pdf Extract`
QGIS plugin; PyMuPDF OCG discussion. Singapore: SLA Digital Underground (ETH);
GovInsider USSP; OneMap; SP Group LCDW; IMDA earthworks; SS 576. Competitors: Bentley
SUE (Geo Week / INAS); Esri Utility Network. Viewers: mlightcad cad-viewer; three-dxf;
three-dxf-viewer. HDD: Heartland Pipelines; For Construction Pros. (Links inline above.)

"""
Configuration: Singapore-grounded standards, cost model, clearances, CAD layers.

IMPORTANT — provenance of numbers
---------------------------------
* Coordinate system, deliverable formats and quality levels are taken from the
  Singapore Land Authority (SLA) "Standard and Specifications for Utility Survey
  in Singapore", v1.3 (Oct 2025).  These are marked  # SLA
* Clearances, unit costs and effort/risk weights are REPRESENTATIVE PLACEHOLDERS
  chosen to make the optimiser behave realistically for a demo.  They are marked
  # ASSUMED and MUST be replaced with values from the relevant utility owner's
  code of practice (PUB, SP PowerGrid, City Energy/gas, IMDA/telco, LTA) before
  any real use.

Everything here is pure data so it can later be driven by a YAML/JSON config or
an LLM that reads a code-of-practice PDF and emits these tables.
"""

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Coordinate reference system                                            # SLA
# ---------------------------------------------------------------------------
CRS = "SVY21 / Singapore TM (EPSG:3414)"        # SLA: horizontal datum
HEIGHT_DATUM = "SHD (Singapore Height Datum)"   # SLA: vertical datum
DELIVERABLE_FORMATS = (".dwg", ".dgn", ".shp")  # SLA: accepted submission formats

# A local patch of the SVY21 grid to anchor the synthetic scenario on.
ORIGIN_E = 30000.0   # easting  (m)
ORIGIN_N = 32000.0   # northing (m)

# ---------------------------------------------------------------------------
# Survey Quality Levels (positional confidence of EXISTING utilities)   # SLA
# ---------------------------------------------------------------------------
# SLA horizontal accuracy classes.  We use QL to *inflate* the clearance buffer:
# the less certain we are where a line actually is, the wider we must stay clear.
QUALITY_LEVELS = {
    "QL-A": 0.100,   # +/- 100 mm  (exposed / as-built by registered surveyor)  # SLA
    "QL-B": 0.300,   # +/- 300 mm  (geophysically detected)                     # SLA
    "QL-C": 0.500,   # +/- 500 mm  (from records, correlated to surface)        # SLA
    "QL-D": 1.000,   # unknown accuracy (records only)                          # SLA (unknown)
}

# ---------------------------------------------------------------------------
# Utility types
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class UtilityType:
    key: str
    label: str
    owner: str            # typical Singapore owner
    aci: int              # AutoCAD Color Index for the CAD layer
    clearance_m: float    # ASSUMED min horizontal separation (parallel)
    cross_cost: float     # ASSUMED $ premium to hand-cross this line once
    cross_risk: float     # ASSUMED effort/risk units for one crossing
    deep: bool = False    # gravity/deep asset (sewer, large drain)

# Colours follow the APWA temporary-marking palette, which SG practice mirrors.
# NOTE on the split between cross_cost ($) and cross_risk (effort units):
#   crossing a live main is a MODEST one-off dollar cost (a day of careful hand
#   excavation) but a LARGE risk/effort cost (danger, permits, standby crew).
#   Keeping money low and risk high is what makes "least cost" and
#   "least effort" pull in genuinely different directions.
UTILITIES = {
    "WATER": UtilityType("WATER", "Water main",   "PUB",           5, 0.30, 250,  3.0),   # blue
    "SEWER": UtilityType("SEWER", "Sewer",        "PUB",           3, 0.50, 500,  9.0, deep=True),   # green
    "GAS":   UtilityType("GAS",   "Gas main",     "City Energy",   2, 0.50, 450, 12.0),   # yellow
    "POWER": UtilityType("POWER", "HV/LV power",  "SP PowerGrid",  1, 0.60, 450, 10.0),   # red
    "TELE":  UtilityType("TELE",  "Telecom duct", "IMDA/telcos",  30, 0.30, 150,  2.0),   # orange
    "DRAIN": UtilityType("DRAIN", "Drainage",     "PUB/LTA",       4, 0.30, 300,  4.0, deep=True),   # cyan
}

# ---------------------------------------------------------------------------
# Surface types (drive machine-vs-manual, reinstatement cost, traffic mgmt)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Surface:
    key: str
    label: str
    reinstate_per_m: float   # ASSUMED $ / m to reinstate the surface after trench
    effort_per_m: float      # ASSUMED effort units / m (traffic mgmt, working difficulty)
    machine_ok: bool         # can an excavator/trencher be used here at all

# effort_per_m is deliberately small: for effort/risk, WHAT you cross and how much
# hand-work + road occupation you incur matters far more than raw trench length.
SURFACES = {
    "VERGE":    Surface("VERGE",    "Grass verge",  40, 0.10, True),
    "FOOTPATH": Surface("FOOTPATH", "Footpath",    140, 0.25, True),
    "CARRIAGE": Surface("CARRIAGE", "Carriageway", 260, 2.00, True),   # road: costly reinstatement + traffic mgmt
}

# ---------------------------------------------------------------------------
# Base trenching economics
# ---------------------------------------------------------------------------
BASE_TRENCH_PER_M   = 90.0    # ASSUMED $ / m open-cut trench (excl. surface)
MANUAL_DIG_PER_M    = 200.0   # ASSUMED $ / m extra when hand-digging near a live asset
MANUAL_EFFORT_PER_M = 4.0     # ASSUMED effort units / m of hand-dig
PROX_ENCROACH_PER_M = 60.0    # ASSUMED $ / m for trenching parallel & close to a live asset
PROX_EFFORT_PER_M   = 1.2     # ASSUMED effort units / m for the same

MANHOLE_COST = 3500.0         # ASSUMED $ per chamber (both ends)

# Trenchless / HDD (horizontal directional drilling): the optimiser may choose to
# BORE a segment instead of open-cut. Boring is dearer per metre but crosses UNDER
# live services (no hand-dig, ~no risk) and needs no surface reinstatement.
BORE_PER_M        = 620.0     # ASSUMED $ / m bored (premium method)
BORE_EFFORT_PER_M = 0.6       # ASSUMED effort units / m (rig setup, low risk)

# ---------------------------------------------------------------------------
# Optimisation objectives  (edge_weight = a*money_norm + b*effort_norm)
# ---------------------------------------------------------------------------
# label/weights + whether trenchless (HDD) is permitted for that option.
OBJECTIVES = {
    "COST":     dict(label="Least cost (open-cut)",     a=1.00, b=0.00, aci=6, allow_bore=False),
    "EFFORT":   dict(label="Least effort (open-cut)",   a=0.00, b=1.00, aci=4, allow_bore=False),
    "BALANCED": dict(label="Balanced (trenchless-assisted)", a=0.50, b=0.50, aci=2, allow_bore=True),
}

# ---------------------------------------------------------------------------
# CAD layer table  (name -> ACI colour)
# ---------------------------------------------------------------------------
LAYERS = {
    # base map (from TOPO.dwg)
    "V-TOPO-ROAD":     8,
    "V-TOPO-KERB":     9,
    "V-TOPO-BLDG":     7,
    "V-CTRL":          7,
    # existing third-party utilities (from the PDFs)
    "U-EXIST-WATER":   UTILITIES["WATER"].aci,
    "U-EXIST-SEWER":   UTILITIES["SEWER"].aci,
    "U-EXIST-GAS":     UTILITIES["GAS"].aci,
    "U-EXIST-POWER":   UTILITIES["POWER"].aci,
    "U-EXIST-TELE":    UTILITIES["TELE"].aci,
    "U-EXIST-DRAIN":   UTILITIES["DRAIN"].aci,
    "U-EXIST-CHAMBER": 7,
    # proposed design
    "U-PROP-ROUTE":    6,
    "U-PROP-CROSSING": 1,
    "U-PROP-MANHOLE":  6,
    "U-PROP-TEXT":     7,
}

EXIST_LAYER = {k: f"U-EXIST-{k}" for k in UTILITIES}

GRID_RES = 1.0   # planner grid resolution (m)

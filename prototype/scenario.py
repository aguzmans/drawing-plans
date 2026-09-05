"""
Build a synthetic-but-realistic input scene and write it as a DXF.

This plays the role of the real inputs a contractor gets:
  * a topographic base map (kerbs, road edges, buildings, control points)  -> like TOPO.dwg
  * several EXISTING third-party utilities that would normally be traced out
    of separate as-built PDFs from PUB / SP / City Energy / telcos.

Coordinates are placed on a local patch of the SVY21 grid (see config.ORIGIN_*).
Geometry is intentionally simple (LWPOLYLINEs) so the planner and the DXF export
are easy to follow.

The scene is also returned as a plain dict so the planner can consume it directly
without re-reading the DXF (the DXF path is exercised separately in planner.load).
"""
import ezdxf
from config import (ORIGIN_E, ORIGIN_N, LAYERS, EXIST_LAYER, UTILITIES)

# Corridor geometry, in LOCAL metres (x = along street/east, y = across/north).
LENGTH = 180.0
WIDTH  = 24.0
# cross-section bands (y ranges): verge | footpath | carriageway | footpath | verge
BANDS = [
    ("VERGE",    0.0,  4.0),
    ("FOOTPATH", 4.0,  7.0),
    ("CARRIAGE", 7.0, 17.0),
    ("FOOTPATH", 17.0, 20.0),
    ("VERGE",    20.0, 24.0),
]

# The new line runs along the SOUTH side (cabinet -> target), both in the verge.
START = (5.0, 2.0)
END   = (175.0, 2.0)

def L(x, y):
    """local -> SVY21 world coordinate."""
    return (ORIGIN_E + x, ORIGIN_N + y)


def build_scene():
    """Return a dict describing the scene in LOCAL coordinates."""
    exist = []   # each: dict(type, ql, pts=[(x,y)...], note)

    # --- longitudinal existing mains, kept to the NORTH half of the street -----
    # (The new south-side line never needs to cross these; a good design keeps
    #  well clear of the PUB/SP/gas trunk mains.)
    exist.append(dict(type="SEWER", ql="QL-C", note="DN450 sewer (PUB), deep",
                      pts=[(0, 12.5), (LENGTH, 12.5)]))
    exist.append(dict(type="WATER", ql="QL-B", note="300mm DI water main (PUB)",
                      pts=[(0, 14.5), (LENGTH, 14.5)]))
    exist.append(dict(type="GAS",   ql="QL-C", note="200mm MP gas main (City Energy)",
                      pts=[(0, 16.5), (LENGTH, 16.5)]))
    exist.append(dict(type="POWER", ql="QL-B", note="22kV HV cable (SP PowerGrid)",
                      pts=[(0, 18.5), (LENGTH, 18.5)]))
    exist.append(dict(type="TELE",  ql="QL-D", note="Telecom duct bank (records only)",
                      pts=[(0, 20.0), (LENGTH, 20.0)]))

    # --- SOUTH-SIDE SERVICE CLUSTER (x ~ 66..118) -----------------------------
    # Building service laterals crossing the cheap south verge/footpath.  Any
    # route that stays low (cheap ground) must HAND-CROSS these live services.
    # They only reach up to y~5.5, so a route that lifts onto the footpath
    # (y>=5.5) around the cluster avoids them -- at higher reinstatement cost.
    exist.append(dict(type="POWER", ql="QL-B", note="LV service to shophouse",
                      pts=[(66.0, 0.0), (66.0, 5.5)]))
    exist.append(dict(type="GAS",   ql="QL-C", note="Gas service to shophouse",
                      pts=[(82.0, 0.0), (82.0, 5.5)]))
    exist.append(dict(type="POWER", ql="QL-B", note="LV service to feeder pillar",
                      pts=[(102.0, 0.0), (102.0, 5.5)]))
    exist.append(dict(type="GAS",   ql="QL-C", note="Gas service to shophouse",
                      pts=[(118.0, 0.0), (118.0, 5.5)]))

    # --- benign transverse services in the NORTH (never crossed; for realism) --
    exist.append(dict(type="TELE", ql="QL-D", note="Telecom drop",
                      pts=[(55.0, 12.5), (55.0, 24.0)]))
    exist.append(dict(type="TELE", ql="QL-D", note="Telecom drop",
                      pts=[(140.0, 12.5), (140.0, 24.0)]))

    # --- hard obstacles ---
    obstacles = []
    # existing comms chamber sits ON the south verge inside the cluster -> the
    # low route must squeeze past it, right among the live services.
    obstacles.append(dict(kind="CHAMBER", note="Existing comms chamber",
                          poly=[(90.0, 0.0), (96.0, 0.0), (96.0, 3.2), (90.0, 3.2)]))

    return dict(length=LENGTH, width=WIDTH, bands=BANDS,
                start=START, end=END, exist=exist, obstacles=obstacles)


def write_input_dxf(scene, path):
    """Write the topo base + existing utilities to a DXF (SVY21 world coords)."""
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 6  # metres
    msp = doc.modelspace()
    for name, aci in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=aci)

    # road edges + kerbs (topo base)
    msp.add_lwpolyline([L(0, 6), L(scene["length"], 6)], dxfattribs={"layer": "V-TOPO-KERB"})
    msp.add_lwpolyline([L(0, 18), L(scene["length"], 18)], dxfattribs={"layer": "V-TOPO-KERB"})
    msp.add_lwpolyline([L(0, 3), L(scene["length"], 3)], dxfattribs={"layer": "V-TOPO-ROAD"})
    msp.add_lwpolyline([L(0, 21), L(scene["length"], 21)], dxfattribs={"layer": "V-TOPO-ROAD"})

    # a couple of survey control points
    for i, (x, y) in enumerate([(2, 2), (178, 2), (2, 22), (178, 22)]):
        msp.add_circle(L(x, y), 0.4, dxfattribs={"layer": "V-CTRL"})
        msp.add_text(f"CP{i+1}", height=0.8,
                     dxfattribs={"layer": "V-CTRL"}).set_placement(L(x + 0.6, y))

    # existing utilities, each on its typed layer, with a note
    for u in scene["exist"]:
        lay = EXIST_LAYER[u["type"]]
        msp.add_lwpolyline([L(*p) for p in u["pts"]], dxfattribs={"layer": lay})
        midx = sum(p[0] for p in u["pts"]) / len(u["pts"])
        midy = sum(p[1] for p in u["pts"]) / len(u["pts"])
        msp.add_text(f'{UTILITIES[u["type"]].label} [{u["ql"]}]', height=0.6,
                     dxfattribs={"layer": lay}).set_placement(L(midx, midy + 0.3))

    # obstacles
    for o in scene["obstacles"]:
        lay = "U-EXIST-CHAMBER" if o["kind"] == "CHAMBER" else "U-EXIST-DRAIN"
        pts = [L(*p) for p in o["poly"]]
        msp.add_lwpolyline(pts + [pts[0]], dxfattribs={"layer": lay})

    # start / end markers
    msp.add_circle(L(*scene["start"]), 0.6, dxfattribs={"layer": "U-PROP-MANHOLE"})
    msp.add_text("START (existing cabinet)", height=0.8,
                 dxfattribs={"layer": "U-PROP-TEXT"}).set_placement(L(scene["start"][0] + 1, scene["start"][1]))
    msp.add_circle(L(*scene["end"]), 0.6, dxfattribs={"layer": "U-PROP-MANHOLE"})
    msp.add_text("END (target)", height=0.8,
                 dxfattribs={"layer": "U-PROP-TEXT"}).set_placement(L(scene["end"][0] + 1, scene["end"][1]))

    doc.saveas(path)
    return path


if __name__ == "__main__":
    import os
    sc = build_scene()
    out = os.path.join(os.path.dirname(__file__), "..", "out", "00_input_scene.dxf")
    write_input_dxf(sc, out)
    print("wrote", os.path.abspath(out))
    print(f"existing utilities: {len(sc['exist'])}, obstacles: {len(sc['obstacles'])}")

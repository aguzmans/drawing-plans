"""
Export finished designs to CAD.

* Native output is DXF (R2018) written directly by ezdxf, on SLA-style layers
  in SVY21 world coordinates.
* DWG is the SLA submission format.  ezdxf cannot WRITE dwg itself; the standard
  free path is to convert the DXF with the ODA File Converter (or LibreDWG's
  dwg2dxf/dxf2dwg).  try_convert_dwg() attempts that automatically if a converter
  is on PATH, otherwise it explains the one manual step.  See docs.
"""
import os
import shutil
import subprocess
import ezdxf

from config import ORIGIN_E, ORIGIN_N, LAYERS, EXIST_LAYER, UTILITIES, OBJECTIVES
import scenario


def _L(x, y):
    return (ORIGIN_E + x, ORIGIN_N + y)


def _lay_base(doc, scene):
    """Lay the topo base + existing utilities into an existing doc."""
    msp = doc.modelspace()
    for name, aci in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=aci)
    # road / kerb lines
    msp.add_lwpolyline([_L(0, 7), _L(scene["length"], 7)], dxfattribs={"layer": "V-TOPO-KERB"})
    msp.add_lwpolyline([_L(0, 17), _L(scene["length"], 17)], dxfattribs={"layer": "V-TOPO-KERB"})
    msp.add_lwpolyline([_L(0, 4), _L(scene["length"], 4)], dxfattribs={"layer": "V-TOPO-ROAD"})
    msp.add_lwpolyline([_L(0, 20), _L(scene["length"], 20)], dxfattribs={"layer": "V-TOPO-ROAD"})
    # existing utilities
    for u in scene["exist"]:
        lay = EXIST_LAYER[u["type"]]
        msp.add_lwpolyline([_L(*p) for p in u["pts"]], dxfattribs={"layer": lay})
    for o in scene["obstacles"]:
        lay = "U-EXIST-CHAMBER" if o["kind"] == "CHAMBER" else "U-EXIST-DRAIN"
        pts = [_L(*p) for p in o["poly"]]
        msp.add_lwpolyline(pts + [pts[0]], dxfattribs={"layer": lay})
    return msp


def _add_route(msp, route, layer, aci, label_suffix=""):
    pts = [_L(*p) for p in route["points"]]
    pl = msp.add_lwpolyline(pts, dxfattribs={"layer": layer, "color": aci})
    pl.dxf.const_width = 0.4
    # crossing markers
    for ckey, (x, y) in route["cross_points"]:
        c = _L(x, y)
        msp.add_circle(c, 0.7, dxfattribs={"layer": "U-PROP-CROSSING"})
        msp.add_text(f"X:{ckey}", height=0.6,
                     dxfattribs={"layer": "U-PROP-CROSSING"}).set_placement((c[0] + 0.8, c[1]))
    # manholes at both ends
    for end in (route["points"][0], route["points"][-1]):
        msp.add_circle(_L(*end), 0.9, dxfattribs={"layer": "U-PROP-MANHOLE", "color": aci})
    # label near the start
    sx, sy = route["points"][0]
    msp.add_text(f'{route["label"]}{label_suffix}  ${route["money"]:.0f} / {route["n_crossings"]} crossings',
                 height=1.0, dxfattribs={"layer": "U-PROP-TEXT", "color": aci}
                 ).set_placement(_L(sx, sy - 1.5))


def write_alternative_dxf(scene, route, path):
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 6
    msp = _lay_base(doc, scene)
    _add_route(msp, route, "U-PROP-ROUTE", route["aci"])
    doc.saveas(path)
    return path


def write_combined_dxf(scene, routes, path):
    """All three alternatives overlaid, each on its own coloured route layer."""
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 6
    # per-objective route layers
    for key, o in OBJECTIVES.items():
        lname = f"U-PROP-ROUTE-{key}"
        if lname not in doc.layers:
            doc.layers.add(lname, color=o["aci"])
    msp = _lay_base(doc, scene)
    for key, route in routes.items():
        _add_route(msp, route, f"U-PROP-ROUTE-{key}", route["aci"])
    doc.saveas(path)
    return path


def try_convert_dwg(dxf_path):
    """Best-effort DXF->DWG using a free converter if present. Returns dwg path or None."""
    dwg_path = os.path.splitext(dxf_path)[0] + ".dwg"
    # LibreDWG
    if shutil.which("dxf2dwg"):
        try:
            subprocess.run(["dxf2dwg", dxf_path, "-o", dwg_path], check=True,
                           capture_output=True)
            if os.path.exists(dwg_path):
                return dwg_path
        except Exception:
            pass
    # ezdxf odafc addon (needs ODA File Converter installed)
    try:
        from ezdxf.addons import odafc
        doc = ezdxf.readfile(dxf_path)
        odafc.export_dwg(doc, dwg_path, version="R2018")
        if os.path.exists(dwg_path):
            return dwg_path
    except Exception:
        pass
    return None

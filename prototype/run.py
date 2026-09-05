"""
End-to-end pipeline:

  inputs (topo + third-party utilities)  ->  scene
     -> deterministic optimiser (3 objectives)
     -> DXF (per option + combined)  [+ DWG if a converter is present]
     -> plan-view drawings (PNG)
     -> method statements + comparison (Markdown)

Run:  python run.py
"""
import os
import scenario
import planner
import export
import render
import report

HERE = os.path.dirname(__file__)
OUT = os.path.abspath(os.path.join(HERE, "..", "out"))
os.makedirs(OUT, exist_ok=True)


def main():
    print("== 1. Build/ingest scene ==")
    scene = scenario.build_scene()
    input_dxf = os.path.join(OUT, "00_input_scene.dxf")
    scenario.write_input_dxf(scene, input_dxf)
    print(f"   existing utilities: {len(scene['exist'])}, obstacles: {len(scene['obstacles'])}")

    # demonstrate the CAD READ path on the DXF we just wrote
    inv = planner.parse_dxf_summary(input_dxf)
    n_ent = sum(sum(t.values()) for t in inv.values())
    print(f"   re-read {input_dxf} -> {len(inv)} layers, {n_ent} entities")

    print("== 2. Optimise routes ==")
    p = planner.Planner(scene)
    g = p.build_graph()
    print(f"   graph {g.number_of_nodes()} nodes / {g.number_of_edges()} edges")
    routes = {}
    for key in ("COST", "EFFORT", "BALANCED"):
        routes[key] = p.solve(key, allow_bore=planner.C.OBJECTIVES[key]["allow_bore"])
        r = routes[key]
        print(f"   {key:9s} {r['length']:.0f} m  S${r['money']:,.0f}  "
              f"crossings={r['n_crossings']}  bore={r['bore_len']:.0f} m  risk={r['risk']:.0f}")

    print("== 3. Export CAD ==")
    render.render_scene(scene, os.path.join(OUT, "00_existing_conditions.png"))
    for key in routes:
        alt_dxf = os.path.join(OUT, f"alt_{key.lower()}.dxf")
        export.write_alternative_dxf(scene, routes[key], alt_dxf)
        render.render_route(scene, routes[key], os.path.join(OUT, f"alt_{key.lower()}.png"))
        print(f"   wrote {os.path.basename(alt_dxf)} + png")
    combined = os.path.join(OUT, "combined_alternatives.dxf")
    export.write_combined_dxf(scene, routes, combined)
    render.render_comparison(scene, routes, os.path.join(OUT, "comparison.png"))
    print(f"   wrote {os.path.basename(combined)} + comparison.png")

    # try DWG (SLA submission format)
    dwg = export.try_convert_dwg(combined)
    if dwg:
        print(f"   DWG written: {os.path.basename(dwg)}")
    else:
        print("   DWG: no free converter (ODA/LibreDWG) on PATH -> DXF is the "
              "deliverable; convert to .dwg for SLA submission (see docs).")

    print("== 4. Written deliverables ==")
    rep = os.path.join(OUT, "DESIGN_REPORT.md")
    report.write_full_report(scene, routes, rep)
    print(f"   wrote {os.path.basename(rep)}")

    print("\nAll outputs in:", OUT)
    for f in sorted(os.listdir(OUT)):
        print("   -", f)


if __name__ == "__main__":
    main()

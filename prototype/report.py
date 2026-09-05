"""
Generate the written deliverables: a comparison and a per-alternative method
statement explaining HOW to build it and WHY the route is what it is.

The prose here is produced from a deterministic template driven by the planner's
structured output.  In the full system this is the step handed to an LLM
(Claude): same structured facts in, but richer, standard-aware narrative out.
The template is intentionally faithful to the numbers so the LLM has a correct
scaffold to expand and can never invent geometry.
"""
from config import UTILITIES, OBJECTIVES, MANHOLE_COST, CRS, HEIGHT_DATUM


def _providers(crossings):
    return sorted({UTILITIES[k].owner for k in crossings})


def comparison_table(routes):
    hdr = ("| Option | Route length | Est. cost (S$) | Live crossings | Hand-dig | "
           "Bored | Risk score |\n"
           "|---|---:|---:|---:|---:|---:|---:|\n")
    rows = []
    for key in ("COST", "BALANCED", "EFFORT"):
        r = routes[key]
        rows.append(f"| **{r['label']}** | {r['length']:.0f} m | {r['money']:,.0f} | "
                    f"{r['n_crossings']} | {r['manual_len']:.0f} m | "
                    f"{r.get('bore_len', 0):.0f} m | {r['risk']:.0f} |")
    return hdr + "\n".join(rows) + "\n"


def recommendation(routes):
    cost, eff, bal = routes["COST"], routes["EFFORT"], routes["BALANCED"]
    return (
        f"With **open-cut only**, there is a real trade-off: the least-cost line "
        f"(S$ {cost['money']:,.0f}) hand-crosses {cost['n_crossings']} live "
        f"service(s) ({', '.join(_providers(cost['crossings'])) or 'none'}), while "
        f"eliminating those crossings by detouring costs more and takes a longer "
        f"line (S$ {eff['money']:,.0f}, {eff['length']:.0f} m).\n\n"
        f"The **trenchless-assisted** line resolves that trade-off: by boring "
        f"~{bal['bore_len']:.0f} m under the congested spots it keeps the short "
        f"alignment ({bal['length']:.0f} m), takes **{bal['n_crossings']} live "
        f"crossings** and the lowest risk, at S$ {bal['money']:,.0f}.\n\n"
        f"**Recommendation:** adopt the **trenchless-assisted** line. A short bore at "
        f"each pinch-point removes every open hand-crossing of a third-party asset - "
        f"the main safety and programme risk - for a cost between the two open-cut "
        f"extremes. (Confirm HDD is feasible for the ground/cover; otherwise fall back "
        f"to the least-effort open-cut line.)"
    )


def method_statement(scene, route):
    r = route
    lines = []
    lines.append(f"## Method statement — {r['label']} option\n")
    lines.append(f"*Coordinate system: {CRS}; levels to {HEIGHT_DATUM}.*\n")
    lines.append("### Key figures")
    lines.append(f"- Trench length: **{r['length']:.0f} m**")
    lines.append(f"- Estimated cost: **S$ {r['money']:,.0f}** "
                 f"(incl. {2} chambers @ S$ {MANHOLE_COST:,.0f})")
    lines.append(f"- Machine-excavatable: **{r['machine_len']:.0f} m**; "
                 f"careful hand-dig: **{r['manual_len']:.0f} m**")
    lines.append(f"- Carriageway opened: **{r['carriage_len']:.0f} m** "
                 f"(traffic management {'required' if r['carriage_len'] > 0 else 'not required'})")
    lines.append(f"- Live-service crossings: **{r['n_crossings']}**")
    lines.append("")

    lines.append("### Sequence of works")
    step = 1
    lines.append(f"{step}. Set out the line from control points; confirm SVY21 offsets. "
                 f"Construct start/end chambers."); step += 1
    lines.append(f"{step}. Trial-hole (SLA QL-A) every recorded utility within 2 m of the "
                 f"line before any machine work."); step += 1
    if r["machine_len"] > 0:
        lines.append(f"{step}. Machine-excavate the ~{r['machine_len']:.0f} m of open "
                     f"verge/footpath where no live service is within clearance."); step += 1
    if r.get("bore_len", 0) > 0:
        lines.append(f"{step}. Bore (HDD) ~{r['bore_len']:.0f} m at the congested pinch-"
                     f"point(s): sink entry/exit pits clear of live services and drill "
                     f"**under** them - no open hand-crossing required."); step += 1
    if r["n_crossings"] > 0:
        provs = ", ".join(_providers(r["crossings"]))
        lines.append(f"{step}. At each of the **{r['n_crossings']}** marked crossings, "
                     f"notify the asset owner(s) ({provs}), expose the service by hand, "
                     f"support it, then dig through beneath/around it. "
                     f"(~{r['manual_len']:.0f} m total hand-dig.)"); step += 1
        detail = ", ".join(f"{n}× {UTILITIES[k].label} ({UTILITIES[k].owner})"
                           for k, n in sorted(r["crossings"].items()))
        lines.append(f"   - Crossings: {detail}")
    elif r.get("bore_len", 0) == 0:
        lines.append(f"{step}. Route was optimised to **avoid all live-service crossings** "
                     f"- no hand-crossing of third-party assets is required."); step += 1
    lines.append(f"{step}. Lay duct/pipe, backfill in layers, reinstate surfaces, "
                 f"as-built survey to QL-A and submit to SLA USSP."); step += 1
    lines.append("")

    lines.append("### Why this route")
    lines.append(_route_rationale(r))
    lines.append("")
    return "\n".join(lines)


def _route_rationale(r):
    if r["objective"] == "COST":
        return ("Chosen to minimise total dollar cost. It keeps to the cheap-to-reinstate "
                "grass verge for essentially its whole length and takes the shortest line, "
                "accepting that this drives it straight through the south-side service "
                f"cluster — hence {r['n_crossings']} hand-crossings and the higher risk score. "
                "Cheapest to price, but the crossings carry programme and safety risk that "
                "cost alone does not capture.")
    if r["objective"] == "EFFORT":
        return ("Chosen to minimise effort/risk. Wherever a live service crosses the cheap "
                "verge, the line lifts onto the footpath to pass **over the clear ground "
                "above the service**, so it never has to expose and hand-dig a third-party "
                "asset. That costs extra length and higher-grade reinstatement, but the "
                "result is zero live crossings and the lowest risk score — the safest, "
                "most schedule-certain build.")
    return ("A weighted blend of cost and effort, with trenchless (HDD) permitted. Instead "
            "of detouring around the service cluster or hand-crossing it, the optimiser "
            "keeps the short, cheap alignment and simply **bores under** the congested "
            f"pinch-point (~{r['bore_len']:.0f} m). That removes every open live-service "
            "crossing at a cost between the two open-cut extremes - the best all-round "
            "choice where ground conditions allow directional drilling.")


def write_full_report(scene, routes, path):
    parts = []
    parts.append("# Proposed utility line — design options & method\n")
    parts.append("Automatically generated by the deterministic planner. In the full "
                 "system the narrative below is authored by an LLM from these same "
                 "structured facts; geometry and figures are fixed by the optimiser.\n")
    parts.append("## Option comparison\n")
    parts.append(comparison_table(routes))
    parts.append("\n## Recommendation\n")
    parts.append(recommendation(routes))
    parts.append("\n\n---\n")
    for key in ("COST", "BALANCED", "EFFORT"):
        parts.append(method_statement(scene, routes[key]))
        parts.append("\n---\n")
    with open(path, "w") as f:
        f.write("\n".join(parts))
    return path

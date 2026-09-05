"""
Render plan-view drawings (PNG) of the scene and each route alternative.

These are the human-readable "drawings of alternatives" deliverable.  They are
produced deterministically from the same geometry that goes into the DXF, so the
picture and the CAD file can never disagree.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
from matplotlib.lines import Line2D

from config import UTILITIES, SURFACES

# ACI-ish -> matplotlib colours
ACI = {1: "red", 2: "gold", 3: "green", 4: "cyan", 5: "blue", 6: "magenta",
       7: "black", 8: "dimgray", 9: "silver", 30: "darkorange"}
BAND_FILL = {"VERGE": "#e8f3e0", "FOOTPATH": "#ececec", "CARRIAGE": "#d8d8d8"}

# Distinct route styling (kept clear of every utility colour above)
ROUTE_COLORS = {"COST": "#c800c8", "EFFORT": "#00a99d", "BALANCED": "#6a1fd0"}
ROUTE_STYLE = {"COST": "solid", "EFFORT": (0, (1, 1)), "BALANCED": (0, (6, 3))}


def _rcolor(route):
    return ROUTE_COLORS.get(route["objective"], "magenta")


def _draw_base(ax, scene):
    L, W = scene["length"], scene["width"]
    for key, lo, hi in scene["bands"]:
        ax.add_patch(Rectangle((0, lo), L, hi - lo, facecolor=BAND_FILL[key],
                               edgecolor="none", zorder=0))
    # kerbs
    for y in (7, 17):
        ax.plot([0, L], [y, y], color="dimgray", lw=1.2, zorder=1)
    # existing utilities
    for u in scene["exist"]:
        col = ACI.get(UTILITIES[u["type"]].aci, "black")
        xs = [p[0] for p in u["pts"]]
        ys = [p[1] for p in u["pts"]]
        ax.plot(xs, ys, color=col, lw=1.6, zorder=2)
    # obstacles
    for o in scene["obstacles"]:
        xs = [p[0] for p in o["poly"]]
        ys = [p[1] for p in o["poly"]]
        fc = "#b0b0b0" if o["kind"] == "CHAMBER" else "#8fbfe0"
        ax.fill(xs, ys, facecolor=fc, edgecolor="k", lw=0.8, hatch="//", zorder=2)
    # start / end
    sx, sy = scene["start"]; ex, ey = scene["end"]
    ax.plot(sx, sy, "ks", ms=9, zorder=5); ax.plot(ex, ey, "k*", ms=15, zorder=5)
    ax.annotate("START", (sx, sy), textcoords="offset points", xytext=(4, 6), fontsize=8)
    ax.annotate("END", (ex, ey), textcoords="offset points", xytext=(-10, 6), fontsize=8)
    ax.set_xlim(-5, L + 5); ax.set_ylim(-2, W + 2)
    ax.set_aspect("equal"); ax.set_xlabel("Easting offset (m)"); ax.set_ylabel("Northing offset (m)")


def _util_legend(extra=None):
    items = [Line2D([0], [0], color=ACI.get(u.aci, "black"), lw=2, label=f"{u.label}")
             for u in UTILITIES.values()]
    items += [Patch(facecolor="#b0b0b0", hatch="//", edgecolor="k", label="Chamber"),
              Patch(facecolor="#8fbfe0", hatch="//", edgecolor="k", label="Canal/drain")]
    if extra:
        items += extra
    return items


def render_scene(scene, path, title="Existing conditions (topo + third-party utilities)"):
    fig, ax = plt.subplots(figsize=(14, 3.6))
    _draw_base(ax, scene)
    ax.set_title(title, fontsize=11)
    ax.legend(handles=_util_legend(), loc="upper center", ncol=8,
              bbox_to_anchor=(0.5, -0.28), fontsize=8, frameon=False)
    fig.tight_layout(); fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path


def render_route(scene, route, path):
    fig, ax = plt.subplots(figsize=(14, 3.6))
    _draw_base(ax, scene)
    xs = [p[0] for p in route["points"]]; ys = [p[1] for p in route["points"]]
    col = _rcolor(route)
    ax.plot(xs, ys, color=col, lw=2.8, zorder=4, label="Proposed line")
    # bored segments (trenchless) drawn as a thick pale overlay
    for (p0, p1) in route.get("bore_segments", []):
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color="black", lw=6, alpha=0.35, zorder=3)
    # crossing markers
    for ckey, (x, y) in route["cross_points"]:
        ax.plot(x, y, "o", mfc="none", mec="red", mew=2, ms=13, zorder=6)
    title = (f'{route["label"]}:  {route["length"]:.0f} m   S$ {route["money"]:,.0f}   '
             f'crossings={route["n_crossings"]}   risk={route["risk"]:.0f}   '
             f'hand-dig={route["manual_len"]:.0f} m   bored={route.get("bore_len", 0):.0f} m')
    ax.set_title(title, fontsize=11)
    extra = [Line2D([0], [0], color=col, lw=3, label="Proposed line"),
             Line2D([0], [0], color="black", lw=6, alpha=0.35, label="Bored (trenchless)"),
             Line2D([0], [0], marker="o", mfc="none", mec="red", mew=2, ls="",
                    ms=10, label="Live-service crossing (hand-dig)")]
    ax.legend(handles=_util_legend(extra), loc="upper center", ncol=8,
              bbox_to_anchor=(0.5, -0.28), fontsize=8, frameon=False)
    fig.tight_layout(); fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path


def render_comparison(scene, routes, path):
    fig, ax = plt.subplots(figsize=(14, 3.8))
    _draw_base(ax, scene)
    extra = []
    for key in ("COST", "BALANCED", "EFFORT"):
        route = routes[key]
        xs = [p[0] for p in route["points"]]; ys = [p[1] for p in route["points"]]
        col = _rcolor(route)
        ax.plot(xs, ys, color=col, lw=2.6, ls=ROUTE_STYLE.get(key, "solid"), zorder=4)
        extra.append(Line2D([0], [0], color=col, lw=3, ls=ROUTE_STYLE.get(key, "solid"),
                            label=f'{route["label"]} (${route["money"]:,.0f}, {route["n_crossings"]}x)'))
    ax.set_title("Alternatives overlaid", fontsize=11)
    ax.legend(handles=_util_legend(extra), loc="upper center", ncol=6,
              bbox_to_anchor=(0.5, -0.28), fontsize=8, frameon=False)
    fig.tight_layout(); fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path

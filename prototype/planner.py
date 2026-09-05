"""
Deterministic core: turn the scene into a weighted graph and solve for three
route alternatives (least cost / least effort / balanced).

Model (see docs for the reasoning):
  * The plannable corridor is discretised into a grid graph (8-connected).
  * Every candidate trench segment (graph edge) is priced on TWO axes:
        money  ($)      -> excavation + surface reinstatement + crossings + manual dig
        effort (units)  -> risk/difficulty: hand-dig near live assets, crossings,
                           traffic management on the carriageway
  * HARD constraints remove edges entirely:
        - inside an obstacle (chamber, canal)
        - running PARALLEL to a live asset within its clearance buffer
          (buffer = code clearance + survey-quality-level uncertainty)
  * PERPENDICULAR crossings are allowed but priced (manual excavation + risk).
  * Each objective is a weighted blend of the two normalised axes; we solve it
    with Dijkstra and then report the RAW money/effort/crossings of the winner.
"""
from __future__ import annotations
import math
import networkx as nx
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

import config as C


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------
def _surface_at(y):
    for key, lo, hi in _BANDS:
        if lo <= y < hi:
            return C.SURFACES[key]
    return C.SURFACES["CARRIAGE"]


_BANDS = None  # set in build_graph from scene

_SIN_PARALLEL = 0.42   # sin(25 deg): below this the trench runs ~parallel to the asset


def _is_parallel(seg, gline):
    """True if seg runs roughly ALONG gline (vs. crossing it at an angle)."""
    (ax, ay), (bx, by) = seg.coords[0], seg.coords[-1]
    (cx, cy), (dx, dy) = gline.coords[0], gline.coords[-1]
    ux, uy = bx - ax, by - ay
    vx, vy = dx - cx, dy - cy
    nu = math.hypot(ux, uy) or 1e-9
    nv = math.hypot(vx, vy) or 1e-9
    sin_ang = abs(ux * vy - uy * vx) / (nu * nv)   # |cross| / (|u||v|)
    return sin_ang < _SIN_PARALLEL


class Planner:
    def __init__(self, scene):
        self.scene = scene
        global _BANDS
        _BANDS = scene["bands"]
        # existing utilities as shapely lines + attributes
        self.util_lines = []      # list[(LineString, UtilityType, buffer_m)]
        for u in scene["exist"]:
            ut = C.UTILITIES[u["type"]]
            ql_unc = C.QUALITY_LEVELS[u["ql"]]
            buf = ut.clearance_m + ql_unc
            self.util_lines.append((LineString(u["pts"]), ut, buf))
        self._util_geoms = [g for g, _, _ in self.util_lines]
        self._tree = STRtree(self._util_geoms) if self._util_geoms else None
        # obstacle polygons (hard)
        self.obstacles = [Polygon(o["poly"]) for o in scene["obstacles"]]
        self._obs_tree = STRtree(self.obstacles) if self.obstacles else None

    # -- per-edge pricing ----------------------------------------------------
    def price_edge(self, a, b):
        """Return dict(money, effort, crosses, manual_len, carriage_len) or None if forbidden."""
        seg = LineString([a, b])
        length = seg.length
        mid = seg.interpolate(0.5, normalized=True)

        # hard: intersect an obstacle
        if self._obs_tree is not None:
            for idx in self._obs_tree.query(seg):
                if self.obstacles[idx].intersects(seg):
                    return None

        surf = _surface_at(mid.y)
        money = length * (C.BASE_TRENCH_PER_M + surf.reinstate_per_m)
        effort = length * surf.effort_per_m
        crosses = []
        manual = False

        if self._tree is not None:
            for idx in self._tree.query(seg.buffer(1.2)):
                gline, ut, buf = self.util_lines[idx]
                da = gline.distance(Point(a))
                db = gline.distance(Point(b))
                # Count a crossing exactly once: attribute it to the edge on which
                # the intersection lies in the half-open parameter range [0, 1).
                # This avoids the double count when a grid node sits on the line.
                crossing = False
                if seg.intersects(gline):
                    inter = seg.intersection(gline)
                    ipts = []
                    gt = inter.geom_type
                    if gt == "Point":
                        ipts = [inter]
                    elif gt == "MultiPoint":
                        ipts = list(inter.geoms)
                    else:  # collinear overlap -> treat as a single crossing
                        ipts = [Point(inter.coords[0])]
                    for ip in ipts:
                        t = seg.project(ip) / (length or 1e-9)
                        if -1e-9 <= t < 1.0 - 1e-9:
                            crossing = True
                if crossing:
                    crosses.append(ut.key)
                    money += ut.cross_cost
                    effort += ut.cross_risk
                    manual = True
                elif da < buf and db < buf and _is_parallel(seg, gline):
                    # both ends inside the clearance corridor AND running along it
                    # => illegal parallel encroachment: HARD violation
                    return None
                elif min(da, db) < buf:
                    # near a live asset but heading across it (or skirting):
                    # allowed, but it's careful hand-work
                    money += C.PROX_ENCROACH_PER_M * length
                    effort += C.PROX_EFFORT_PER_M * length
                    manual = True

        if manual:
            money += C.MANUAL_DIG_PER_M * length
            effort += C.MANUAL_EFFORT_PER_M * length

        return dict(money=money, effort=effort, crosses=crosses,
                    manual_len=length if manual else 0.0,
                    carriage_len=length if surf.key == "CARRIAGE" else 0.0)

    def price_bore(self, a, b):
        """Price the same segment as a trenchless BORE, or None if impossible.
        Boring passes UNDER live utilities (no crossing/manual/reinstatement) but
        cannot go through a physical chamber."""
        seg = LineString([a, b])
        if self._obs_tree is not None:
            for idx in self._obs_tree.query(seg):
                o = self.obstacles[idx]
                # a chamber is a solid structure; a canal can be bored under
                if self.scene["obstacles"][idx]["kind"] == "CHAMBER" and o.intersects(seg):
                    return None
        length = seg.length
        return dict(money=length * C.BORE_PER_M, effort=length * C.BORE_EFFORT_PER_M)

    # -- graph ---------------------------------------------------------------
    def build_graph(self):
        res = C.GRID_RES
        nx_g = nx.Graph()
        length, width = self.scene["length"], self.scene["width"]
        nX = int(round(length / res)) + 1
        nY = int(round(width / res)) + 1

        def node_xy(i, j):
            return (i * res, j * res)

        # 8-connectivity offsets
        offs = [(1, 0), (0, 1), (1, 1), (1, -1)]
        max_money = max_effort = 1e-9
        for i in range(nX):
            for j in range(nY):
                a = node_xy(i, j)
                for di, dj in offs:
                    ni, nj = i + di, j + dj
                    if not (0 <= ni < nX and 0 <= nj < nY):
                        continue
                    b = node_xy(ni, nj)
                    p = self.price_edge(a, b)
                    bore = self.price_bore(a, b)
                    if p is None and bore is None:
                        continue
                    if p is None:
                        # only boring is possible here (e.g. under the canal)
                        p = dict(money=float("inf"), effort=float("inf"), crosses=[],
                                 manual_len=0.0, carriage_len=0.0)
                    p["money_bore"] = bore["money"] if bore else float("inf")
                    p["effort_bore"] = bore["effort"] if bore else float("inf")
                    nx_g.add_edge((i, j), (ni, nj), **p)
                    for m in (p["money"], p["money_bore"]):
                        if m != float("inf"):
                            max_money = max(max_money, m)
                    for e in (p["effort"], p["effort_bore"]):
                        if e != float("inf"):
                            max_effort = max(max_effort, e)
        self.g = nx_g
        self.max_money = max_money
        self.max_effort = max_effort
        self.nX, self.nY, self.res = nX, nY, res
        return nx_g

    def _nearest_node(self, x, y):
        i = min(self.nX - 1, max(0, int(round(x / self.res))))
        j = min(self.nY - 1, max(0, int(round(y / self.res))))
        # nudge to a node that actually has edges
        if (i, j) in self.g:
            return (i, j)
        best, bd = None, 1e18
        for n in self.g.nodes:
            d = (n[0] - i) ** 2 + (n[1] - j) ** 2
            if d < bd:
                bd, best = d, n
        return best

    # -- solve ---------------------------------------------------------------
    def solve(self, objective_key, allow_bore=True):
        obj = C.OBJECTIVES[objective_key]
        a, b = obj["a"], obj["b"]
        self._allow_bore = allow_bore

        def blended(money, effort):
            return a * (money / self.max_money) + b * (effort / self.max_effort)

        def w(u, v, d):
            oc = blended(d["money"], d["effort"])
            bore = blended(d["money_bore"], d["effort_bore"]) if allow_bore else float("inf")
            return min(oc, bore) + 1e-6  # tiny epsilon keeps weights positive

        self._blended = blended  # reused by _summarise to recover the method

        s = self._nearest_node(*self.scene["start"])
        t = self._nearest_node(*self.scene["end"])
        path = nx.shortest_path(self.g, s, t, weight=w)
        return self._summarise(path, objective_key)

    def _summarise(self, path, objective_key):
        res = self.res
        pts = [(i * res, j * res) for (i, j) in path]
        # simplify collinear points for a cleaner polyline
        simp = [pts[0]]
        for k in range(1, len(pts) - 1):
            ax, ay = simp[-1]
            bx, by = pts[k]
            cx, cy = pts[k + 1]
            # keep point if direction changes
            if (bx - ax) * (cy - by) != (cy - by) * 0 + (by - ay) * (cx - bx):
                simp.append(pts[k])
        simp.append(pts[-1])

        money = effort = length = manual = carriage = bore_len = 0.0
        crossings = {}
        cross_points = []
        bore_segments = []
        for u, v in zip(path[:-1], path[1:]):
            d = self.g.edges[u, v]
            seglen = math.dist((u[0]*res, u[1]*res), (v[0]*res, v[1]*res))
            length += seglen
            # recover which method this objective picked on this edge
            use_bore = self._allow_bore and (
                self._blended(d["money_bore"], d["effort_bore"])
                < self._blended(d["money"], d["effort"]))
            if use_bore:
                money += d["money_bore"]; effort += d["effort_bore"]
                bore_len += seglen
                bore_segments.append(((u[0]*res, u[1]*res), (v[0]*res, v[1]*res)))
            else:
                money += d["money"]; effort += d["effort"]
                manual += d["manual_len"]; carriage += d["carriage_len"]
                for c in d["crosses"]:
                    crossings[c] = crossings.get(c, 0) + 1
                    mx = (u[0]*res + v[0]*res)/2
                    my = (u[1]*res + v[1]*res)/2
                    cross_points.append((c, (mx, my)))
        # dedupe consecutive crossing points of the same type close together
        money += 2 * C.MANHOLE_COST  # chambers at both ends
        risk = sum(C.UTILITIES[k].cross_risk * n for k, n in crossings.items())
        return dict(
            objective=objective_key,
            label=C.OBJECTIVES[objective_key]["label"],
            aci=C.OBJECTIVES[objective_key]["aci"],
            points=simp,
            money=round(money, 0),
            effort=round(effort, 1),
            length=round(length, 1),
            manual_len=round(manual, 1),
            machine_len=round(length - manual - bore_len, 1),
            carriage_len=round(carriage, 1),
            bore_len=round(bore_len, 1),
            bore_segments=bore_segments,
            crossings=crossings,
            n_crossings=sum(crossings.values()),
            risk=round(risk, 1),
            cross_points=cross_points,
        )


def parse_dxf_summary(path):
    """Read a DXF and inventory its layers/entities — proves the CAD read path.
    The same function works on TOPO.dwg once converted DWG->DXF (see docs)."""
    import ezdxf
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    by_layer = {}
    for e in msp:
        lay = e.dxf.layer
        by_layer.setdefault(lay, {}).setdefault(e.dxftype(), 0)
        by_layer[lay][e.dxftype()] += 1
    return by_layer

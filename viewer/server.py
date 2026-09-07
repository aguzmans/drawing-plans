#!/usr/bin/env python3
"""
Simple local web viewer for the CAD plans (development tool).

  python server.py                       # then open http://localhost:8000
  python server.py --port 9000 --plans /path/to/dxf/folder

How it works
------------
Every .dxf in the plans folder is rendered server-side by the same faithful ezdxf
engine used elsewhere in this project. The selected layers are rendered TOGETHER
(so blocks and colours resolve correctly), and an invisible full-extent anchor
keeps the SVG viewBox identical no matter which layers are on -- so toggling
layers never shifts the drawing. The browser adds pan / zoom, a dark/light
background, and a live SVY21 coordinate read-out under the cursor.

Neutral pen colours (ACI 7 white / pure black) are emitted as `currentColor` so
they stay visible on either background. Only dependency beyond the stdlib: ezdxf.
"""
import argparse, http.server, json, os, re, threading, urllib.parse

import ezdxf
from ezdxf import bbox, colors as ezcolors
from ezdxf.addons.drawing import RenderContext, Frontend, svg, layout, config

HERE = os.path.dirname(os.path.abspath(__file__))
PLANS_DIR = os.path.join(HERE, "plans")

_VB_RE = re.compile(r'viewBox="([^"]+)"')
_XMLDECL_RE = re.compile(r"^<\?xml[^>]*\?>\s*")
_CFG = config.Configuration()
_PAGE = layout.Page(0, 0, layout.Units.mm, margins=layout.Margins.all(2))

_docs = {}          # path -> (mtime, doc, msp, extents, layers_meta)
_cache = {}         # (path, mtime, only_key) -> (svg, viewBox)
_lock = threading.Lock()


def _aci_hex(aci):
    try:
        r, g, b = ezcolors.aci2rgb(aci if aci not in (0, 256) else 7)
    except Exception:
        r = g = b = 200
    if (r, g, b) == (255, 255, 255):
        return "#dfe6ec"          # neutral pen -> light grey swatch
    return f"#{r:02x}{g:02x}{b:02x}"


def _load(path):
    mtime = os.stat(path).st_mtime_ns
    cached = _docs.get(path)
    if cached and cached[0] == mtime:
        return cached
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    counts, colors = {}, {}
    for e in msp:
        lay = e.dxf.layer
        counts[lay] = counts.get(lay, 0) + 1
    try:
        ext = bbox.extents(msp, fast=True)
        (minx, miny, _), (maxx, maxy, _) = ext.extmin, ext.extmax
    except Exception:
        minx, miny, maxx, maxy = 0, 0, 1, 1
    if "__ANCHOR__" not in doc.layers:
        doc.layers.add("__ANCHOR__")
    a = msp.add_lwpolyline([(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)],
                           close=True, dxfattribs={"layer": "__ANCHOR__"})
    a.transparency = 1.0
    layers_meta = [
        {"name": n, "count": counts[n],
         "color": _aci_hex(doc.layers.get(n).dxf.color if n in doc.layers else 7)}
        for n in sorted(counts) if n != "__ANCHOR__"
    ]
    rec = (mtime, doc, msp, [minx, miny, maxx, maxy], layers_meta)
    _docs[path] = rec
    return rec


def render(path, only=None):
    """Render `path` with the given layers (None = all) to an SVG string."""
    mtime, doc, msp, ext, layers_meta = _load(path)
    only_key = "ALL" if only is None else ",".join(sorted(only))
    ck = (path, mtime, only_key)
    with _lock:
        if ck in _cache:
            return _cache[ck]
        for l in doc.layers:
            n = l.dxf.name
            if n == "__ANCHOR__" or only is None or n in only:
                l.on()
            else:
                l.off()
        be = svg.SVGBackend()
        Frontend(RenderContext(doc), be, config=_CFG).draw_layout(msp, finalize=True)
        s = be.get_string(_PAGE)
        m = _VB_RE.search(s)
        vb = m.group(1) if m else "0 0 1000 1000"
        s = _XMLDECL_RE.sub("", s)
        # neutral pen -> currentColor so white/black adapt to the page background
        s = s.replace("#ffffff", "currentColor").replace("#000000", "currentColor")
        # Line width is handled in the browser: the page CSS sets a small,
        # constant screen-pixel stroke via `vector-effect:non-scaling-stroke`,
        # so hairline survey lines stay crisp (~1.2px) at any zoom.
        out = (s, vb)
        _cache[ck] = out
        return out


INDEX_HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CAD Plan Viewer</title>
<style>
  :root{--bar:#1b2026;--panel:#232a31;--ink:#e7edf2;--muted:#8b97a3;--line:#333d47;
        --accent:#39c0c9;--dark:#0c1116;--light:#eef1f2;
        --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
        --sans:"Helvetica Neue",Arial,sans-serif;}
  *{box-sizing:border-box} html,body{height:100%}
  body{margin:0;font-family:var(--sans);color:var(--ink);background:var(--dark);
       display:flex;flex-direction:column;overflow:hidden}
  header{background:var(--bar);border-bottom:1px solid var(--line);display:flex;
         align-items:center;gap:14px;padding:8px 14px;flex:none}
  header h1{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);
            margin:0;font-family:var(--mono);font-weight:600}
  label.f{font-family:var(--mono);font-size:11px;color:var(--muted)}
  select,button{background:var(--panel);color:var(--ink);border:1px solid var(--line);
        border-radius:4px;padding:5px 9px;font-family:var(--mono);font-size:12px;cursor:pointer}
  button:hover,select:hover{border-color:var(--accent)}
  button:focus-visible,select:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
  .spacer{flex:1}
  .readout{font-family:var(--mono);font-size:12px;color:var(--muted);min-width:230px;text-align:right}
  #busy{font-family:var(--mono);font-size:11px;color:var(--accent);opacity:0;transition:opacity .15s}
  #busy.on{opacity:1}
  main{flex:1;display:flex;min-height:0}
  aside{width:250px;flex:none;background:var(--bar);border-right:1px solid var(--line);
        display:flex;flex-direction:column;min-height:0}
  .aside-h{padding:9px 12px;border-bottom:1px solid var(--line);display:flex;align-items:center;
           gap:8px;font-family:var(--mono);font-size:11px;text-transform:uppercase;
           letter-spacing:.1em;color:var(--muted)}
  .aside-h button{padding:2px 7px;font-size:10px}
  .layers{overflow:auto;padding:4px 0}
  .ly{display:flex;align-items:center;gap:8px;padding:4px 12px;font-size:12px;
      font-family:var(--mono);cursor:pointer;user-select:none}
  .ly:hover{background:#2b333b}
  .ly input{accent-color:var(--accent);margin:0}
  .sw{width:11px;height:11px;border-radius:2px;border:1px solid #0006;flex:none}
  .ly .nm{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .ly .ct{color:var(--muted);font-size:11px}
  #stage{flex:1;position:relative;overflow:hidden;background:var(--dark);cursor:grab}
  #stage.grabbing{cursor:grabbing}
  #frame{position:absolute;left:0;top:0;transform-origin:0 0;will-change:transform;color:#e8e8e8}
  #frame svg{display:block;width:1200px;height:auto}
  /* constant ~1.2px lines at any zoom (non-scaling-stroke makes stroke-width mean screen px) */
  #frame svg [class]{vector-effect:non-scaling-stroke;stroke-width:1.2px}
  body.light #stage{background:var(--light)} body.light #frame{color:#1c2126}
  .hint{position:absolute;left:12px;bottom:10px;font-family:var(--mono);font-size:11px;
        color:var(--muted);background:#0007;padding:4px 8px;border-radius:4px;pointer-events:none}
</style></head><body>
<header>
  <h1>CAD&nbsp;Viewer</h1>
  <label class="f">plan <select id="file"></select></label>
  <button id="fit" title="Fit to view (F)">Fit</button>
  <button id="bg" title="Toggle background">Dark/Light</button>
  <span id="busy">rendering&hellip;</span>
  <div class="spacer"></div>
  <div class="readout" id="readout">E&nbsp;&mdash;&emsp;N&nbsp;&mdash;</div>
</header>
<main>
  <aside>
    <div class="aside-h"><span>Layers</span><div class="spacer"></div>
      <button id="all">all</button><button id="none">none</button></div>
    <div class="layers" id="layers"></div>
  </aside>
  <div id="stage"><div id="frame"></div>
    <div class="hint">drag&nbsp;to&nbsp;pan&nbsp;&middot;&nbsp;scroll&nbsp;to&nbsp;zoom&nbsp;&middot;&nbsp;F&nbsp;to&nbsp;fit</div></div>
</main>
<script>
const $=s=>document.querySelector(s);
const stage=$("#stage"),frame=$("#frame"),readout=$("#readout"),busy=$("#busy");
let view={x:0,y:0,s:1},file=null,meta=null,vb=null,seq=0,tmr=null;

function apply(){frame.style.transform=`translate(${view.x}px,${view.y}px) scale(${view.s})`;}
function fit(){const r=stage.getBoundingClientRect();const svg=frame.querySelector("svg");if(!svg)return;
  const bw=svg.clientWidth||1200,bh=svg.clientHeight||800;
  const s=Math.min(r.width/bw,r.height/bh)*0.94;view.s=s;view.x=(r.width-bw*s)/2;view.y=(r.height-bh*s)/2;apply();}

async function loadFiles(){
  const files=await (await fetch("api/files")).json();
  const sel=$("#file");sel.innerHTML="";
  files.forEach(f=>{const o=document.createElement("option");o.value=f;o.textContent=f;sel.appendChild(o);});
  if(files.length) selectFile(files[0]);
}
async function selectFile(f){
  file=f; meta=await (await fetch("api/plan?f="+encodeURIComponent(f))).json();
  vb=meta.viewBox.split(/\s+/).map(Number);
  const box=$("#layers");box.innerHTML="";
  meta.layers.forEach(l=>{
    const row=document.createElement("label");row.className="ly";
    row.innerHTML=`<input type="checkbox" checked data-l="${l.name}">`+
      `<span class="sw" style="background:${l.color}"></span>`+
      `<span class="nm" title="${l.name}">${l.name}</span><span class="ct">${l.count}</span>`;
    row.querySelector("input").addEventListener("change",scheduleRender);
    box.appendChild(row);
  });
  frame.innerHTML=meta.svg; requestAnimationFrame(fit);
}
function scheduleRender(){clearTimeout(tmr);tmr=setTimeout(doRender,180);}
async function doRender(){
  const checked=[...document.querySelectorAll('#layers input:checked')].map(i=>i.dataset.l);
  const total=document.querySelectorAll('#layers input').length;
  const my=++seq; busy.classList.add("on");
  const q= checked.length===total ? "api/plan?f="+encodeURIComponent(file)
        : "api/svg?f="+encodeURIComponent(file)+"&only="+encodeURIComponent(checked.join(","));
  try{
    const d=await (await fetch(q)).json();
    if(my!==seq) return;               // a newer request superseded this one
    frame.innerHTML=d.svg; apply();     // keep current pan/zoom
  }finally{ if(my===seq) busy.classList.remove("on"); }
}
// pan
let drag=null;
stage.addEventListener("mousedown",e=>{drag={x:e.clientX-view.x,y:e.clientY-view.y};stage.classList.add("grabbing");});
window.addEventListener("mouseup",()=>{drag=null;stage.classList.remove("grabbing");});
window.addEventListener("mousemove",e=>{
  if(drag){view.x=e.clientX-drag.x;view.y=e.clientY-drag.y;apply();}
  if(meta&&vb){const r=stage.getBoundingClientRect();
    const sx=(e.clientX-r.left-view.x)/view.s,sy=(e.clientY-r.top-view.y)/view.s;
    const svg=frame.querySelector("svg");
    if(svg){const u=sx/svg.clientWidth*vb[2],v=sy/svg.clientHeight*vb[3];
      const [minx,miny,maxx,maxy]=meta.extents;
      const E=minx+u/vb[2]*(maxx-minx),N=maxy-v/vb[3]*(maxy-miny);
      readout.innerHTML=`E&nbsp;${E.toFixed(2)}&emsp;N&nbsp;${N.toFixed(2)}`;}}
});
stage.addEventListener("wheel",e=>{e.preventDefault();
  const r=stage.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
  const k=Math.exp(-e.deltaY*0.0015);
  view.x=mx-(mx-view.x)*k;view.y=my-(my-view.y)*k;view.s*=k;apply();},{passive:false});
$("#file").addEventListener("change",e=>selectFile(e.target.value));
$("#fit").addEventListener("click",fit);
$("#bg").addEventListener("click",()=>document.body.classList.toggle("light"));
$("#all").addEventListener("click",()=>{document.querySelectorAll('#layers input').forEach(i=>i.checked=true);scheduleRender();});
$("#none").addEventListener("click",()=>{document.querySelectorAll('#layers input').forEach(i=>i.checked=false);scheduleRender();});
window.addEventListener("keydown",e=>{if(e.key==="f"||e.key==="F")fit();});
window.addEventListener("resize",fit);
loadFiles();
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, INDEX_HTML.encode(), "text/html; charset=utf-8")
            if u.path == "/api/files":
                fs = sorted(f for f in os.listdir(PLANS_DIR) if f.lower().endswith(".dxf"))
                return self._send(200, json.dumps(fs).encode(), "application/json")
            if u.path in ("/api/plan", "/api/svg"):
                f = os.path.basename(q.get("f", [""])[0])
                p = os.path.join(PLANS_DIR, f)
                if not (f.lower().endswith(".dxf") and os.path.isfile(p)):
                    return self._send(404, b'{"error":"not found"}', "application/json")
                only = None
                if u.path == "/api/svg":
                    raw = q.get("only", [""])[0]
                    only = set(x for x in raw.split(",") if x)
                s, vb = render(p, only)
                _, _, _, ext, layers = _load(p)
                payload = {"svg": s, "viewBox": vb, "extents": ext}
                if u.path == "/api/plan":
                    payload["layers"] = layers
                return self._send(200, json.dumps(payload).encode(), "application/json")
            self._send(404, b"not found", "text/plain")
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}).encode(), "application/json")

    def log_message(self, *a):
        pass


def main():
    global PLANS_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--plans", default=PLANS_DIR)
    a = ap.parse_args()
    PLANS_DIR = os.path.abspath(a.plans)
    print(f"CAD viewer: http://localhost:{a.port}   plans: {PLANS_DIR}")
    http.server.ThreadingHTTPServer(("0.0.0.0", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

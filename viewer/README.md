# CAD Plan Viewer (dev tool)

A tiny local web viewer for the project's DXF plans. Faithful `ezdxf` rendering,
pan/zoom, per-layer toggles, dark/light background, and a live SVY21 coordinate
read-out. No external JS/CSS/font dependencies; only Python + `ezdxf`.

## Run with Docker (recommended)
```bash
cd viewer
docker build -t cad-viewer:local .
docker run -d --name cad-viewer -p 8000:8000 cad-viewer:local
# open http://localhost:8000    (stop with: docker rm -f cad-viewer)
```
To view your own DXFs live without rebuilding, mount a folder over the baked-in
`plans/` (drop files in, refresh the browser):
```bash
docker run -d --name cad-viewer -p 8000:8000 \
  -v "$(pwd)/plans:/app/plans" cad-viewer:local
```
Change the host port with `-p 9000:8000`.

## Run without Docker
```bash
pip install ezdxf pillow
python server.py                       # serves http://localhost:8000
python server.py --port 9000 --plans /path/to/dxf/folder
```
Then open the URL in a browser.

## Use
- **plan** dropdown — pick any `.dxf` in the plans folder (drop new files in and
  refresh; the list and file cache update by modification time).
- **drag** to pan, **scroll** to zoom toward the cursor, **F** or **Fit** to frame.
- **Layers** panel — toggle layers on/off (colour swatch + entity count per layer).
  `all` / `none` shortcuts at the top.
- **Dark/Light** — flip the background; the neutral (white/black) pen adapts so it
  stays visible either way.
- top-right **E / N** — SVY21 easting/northing under the cursor.

## How it renders faithfully
Selected layers are rendered *together* server-side by the same `ezdxf` drawing
engine used across the project, so blocks and colours resolve exactly as in CAD.
An invisible full-extent anchor keeps the SVG `viewBox` identical regardless of
which layers are visible, so toggling never shifts or rescales the drawing.
Renders are cached per (file, layer-set).

## Notes
- Input is DXF. For DWG, convert first (this project uses the ODA File Converter
  Docker image; see the main docs) and drop the resulting `.dxf` in `plans/`.
- `plans/` currently holds the recovered `TOPO.dxf` plus the prototype's design
  DXFs (`combined_alternatives.dxf`, `alt_*.dxf`, `00_input_scene.dxf`).

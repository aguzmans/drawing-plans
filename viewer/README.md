# CAD Plan Viewer (dev tool)

A tiny local web viewer for the project's DXF plans. Faithful `ezdxf` rendering,
pan/zoom, per-layer toggles, dark/light background, and a live SVY21 coordinate
read-out. No external JS/CSS/font dependencies; only Python + `ezdxf`.

## Run (Docker Compose — canonical)
```bash
cd viewer
docker compose up -d viewer      # build + run at http://localhost:8000
docker compose down              # stop
```
`plans/` is mounted into the container, so drop `.dxf` files in and refresh the
browser — no rebuild needed. Change the host port by editing `ports:` in
`docker-compose.yml`.

## Test (Playwright E2E)
```bash
docker compose run --rm e2e      # runs the browser tests against the viewer
```
The `e2e` service builds `tests/`, waits for the viewer to be healthy, and runs the
Playwright suite in `tests/e2e/`. It must be green before any UI change is "done"
(see ../CLAUDE.md).

## Run without Docker (dev only)
```bash
pip install -r requirements.txt        # pinned: ezdxf, pillow
python server.py                       # http://localhost:8000
python server.py --port 9000 --plans /path/to/dxf/folder
```

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

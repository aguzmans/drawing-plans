"""
End-to-end tests for the CAD viewer, driven through a real Chromium via Playwright.

These assert the behaviour a user actually sees in a browser (not just that the
server returns bytes) — including a regression guard for the stroke-width bug that
once rendered every line ~9000px wide.
"""
import re
import pytest


def _open_topo(page, base_url):
    """Load the app and switch to TOPO.dxf; return once its 31 layers are listed."""
    page.goto(base_url + "/", wait_until="networkidle")
    page.wait_for_selector("#frame svg", timeout=20000)
    page.select_option("#file", "TOPO.dxf")
    page.wait_for_function(
        "() => document.querySelectorAll('#layers .ly').length === 31",
        timeout=30000,
    )
    page.wait_for_function(
        "() => document.querySelectorAll('#frame svg path').length > 1000",
        timeout=30000,
    )


def _paths(page):
    return page.eval_on_selector_all("#frame svg path", "els => els.length")


# --- basic wiring ----------------------------------------------------------

def test_page_loads(page, base_url):
    page.goto(base_url + "/", wait_until="networkidle")
    assert "CAD" in page.title()
    assert page.locator("#file").is_visible()
    assert page.locator("#layers").is_visible()


def test_api_lists_plans(page, base_url):
    r = page.request.get(base_url + "/api/files")
    assert r.ok
    files = r.json()
    assert "TOPO.dxf" in files
    assert "combined_alternatives.dxf" in files


def test_api_plan_shape(page, base_url):
    r = page.request.get(base_url + "/api/plan?f=TOPO.dxf")
    assert r.ok
    d = r.json()
    assert set(d) >= {"svg", "viewBox", "extents", "layers"}
    assert len(d["layers"]) == 31
    assert len(d["extents"]) == 4
    assert "<svg" in d["svg"]


# --- rendering -------------------------------------------------------------

def test_topo_renders_linework(page, base_url):
    _open_topo(page, base_url)
    assert _paths(page) > 1000


def test_strokes_are_not_a_blob(page, base_url):
    """Regression: strokes must be a few screen px, not thousands (the blob bug)."""
    _open_topo(page, base_url)
    info = page.evaluate(
        """() => {
            const p = document.querySelector('#frame svg [class]');
            const cs = getComputedStyle(p);
            return {sw: cs.strokeWidth, ve: cs.vectorEffect};
        }"""
    )
    assert info["ve"] == "non-scaling-stroke"
    m = re.match(r"([\d.]+)px", info["sw"])
    assert m, f"unexpected stroke-width: {info['sw']}"
    assert float(m.group(1)) < 5.0, f"stroke too fat (blob regression): {info['sw']}"


# --- interactions ----------------------------------------------------------

def test_layer_toggle_changes_render(page, base_url):
    _open_topo(page, base_url)
    page.click("#none")
    page.wait_for_function(
        "() => document.querySelectorAll('#frame svg path').length <= 2",
        timeout=30000,
    )
    page.check('#layers input[data-l="S_MH-WD"]')      # 50 water manholes
    page.wait_for_function(
        "() => document.querySelectorAll('#frame svg path').length > 5",
        timeout=30000,
    )


def test_dark_light_toggle(page, base_url):
    page.goto(base_url + "/", wait_until="networkidle")
    assert page.evaluate("() => document.body.classList.contains('light')") is False
    page.click("#bg")
    assert page.evaluate("() => document.body.classList.contains('light')") is True
    page.click("#bg")
    assert page.evaluate("() => document.body.classList.contains('light')") is False


def test_coordinate_readout(page, base_url):
    _open_topo(page, base_url)
    box = page.locator("#stage").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_function(
        "() => /E\\s*[\\d.]+/.test(document.querySelector('#readout').textContent)",
        timeout=10000,
    )

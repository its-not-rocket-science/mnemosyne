"""Static structural accessibility checks for frontend/index.html.

No browser, no Playwright, no axe — just HTML parsing via stdlib.
Verifies the minimum ARIA contract that would be invisible to unit
tests but caught immediately by any AT user.
"""
from __future__ import annotations

import pathlib
from html.parser import HTMLParser


# ── Parser ────────────────────────────────────────────────────────────────────

class _Collector(HTMLParser):
    """Walk the HTML tree and collect elements by selector-like criteria."""

    def __init__(self) -> None:
        super().__init__()
        self.elements: list[dict] = []   # {tag, attrs} for every opening tag

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append({"tag": tag, "attrs": dict(attrs)})

    # ── Query helpers ──────────────────────────────────────────────────────────

    def by_id(self, id_: str) -> dict | None:
        for el in self.elements:
            if el["attrs"].get("id") == id_:
                return el
        return None

    def by_role(self, role: str) -> list[dict]:
        return [el for el in self.elements if el["attrs"].get("role") == role]

    def by_tag(self, tag: str) -> list[dict]:
        return [el for el in self.elements if el["tag"] == tag]

    def ids(self) -> set[str]:
        return {el["attrs"]["id"] for el in self.elements if "id" in el["attrs"]}


def _load() -> _Collector:
    html_path = pathlib.Path(__file__).parents[2] / "frontend" / "index.html"
    collector = _Collector()
    collector.feed(html_path.read_text(encoding="utf-8"))
    return collector


# ── Fixtures ──────────────────────────────────────────────────────────────────

import pytest


@pytest.fixture(scope="module")
def page() -> _Collector:
    return _load()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSkipLink:
    def test_skip_link_exists(self, page):
        links = [el for el in page.by_tag("a") if el["attrs"].get("class") == "skip-link"]
        assert links, "No .skip-link <a> element found"

    def test_skip_link_target_exists(self, page):
        links = [el for el in page.by_tag("a") if el["attrs"].get("class") == "skip-link"]
        assert links
        href = links[0]["attrs"].get("href", "")
        # href="#main" → id "main"
        target_id = href.lstrip("#")
        assert target_id, "Skip link href is empty"
        assert page.by_id(target_id), f"Skip link target #{target_id} not found in page"

    def test_main_is_focusable(self, page):
        main = page.by_id("main")
        assert main is not None, "No <main id='main'> found"
        assert main["attrs"].get("tabindex") == "-1", (
            "<main id='main'> should have tabindex='-1' for skip link to work"
        )


class TestDialogs:
    def test_all_dialogs_have_aria_labelledby(self, page):
        dialogs = page.by_tag("dialog")
        page_ids = page.ids()
        for dlg in dialogs:
            dlg_id = dlg["attrs"].get("id", "<no id>")
            labelledby = dlg["attrs"].get("aria-labelledby", "")
            assert labelledby, f"<dialog id='{dlg_id}'> missing aria-labelledby"
            assert labelledby in page_ids, (
                f"<dialog id='{dlg_id}'> aria-labelledby='{labelledby}' "
                f"points to a non-existent id"
            )

    def test_dialog_labels_are_headings(self, page):
        dialogs = page.by_tag("dialog")
        page_ids = page.ids()
        heading_ids = {
            el["attrs"]["id"]
            for el in page.elements
            if el["tag"] in ("h1", "h2", "h3") and "id" in el["attrs"]
        }
        for dlg in dialogs:
            labelledby = dlg["attrs"].get("aria-labelledby", "")
            if labelledby and labelledby in page_ids:
                assert labelledby in heading_ids, (
                    f"<dialog> aria-labelledby='{labelledby}' "
                    f"should point to a heading element"
                )


class TestForms:
    """Every visible form input should have a <label for=…> pointing to it."""

    def test_inputs_have_labels(self, page):
        label_fors = {
            el["attrs"]["for"]
            for el in page.by_tag("label")
            if "for" in el["attrs"]
        }
        inputs = [
            el for el in page.by_tag("input")
            if el["attrs"].get("type") not in ("hidden", "file")
            and "id" in el["attrs"]
            # file input is wrapped in a <label> — skip sr-only file input
            and "sr-only" not in el["attrs"].get("class", "")
        ]
        for inp in inputs:
            inp_id = inp["attrs"]["id"]
            assert inp_id in label_fors, (
                f"<input id='{inp_id}'> has no <label for='{inp_id}'>"
            )

    def test_textareas_have_labels(self, page):
        label_fors = {
            el["attrs"]["for"]
            for el in page.by_tag("label")
            if "for" in el["attrs"]
        }
        for ta in page.by_tag("textarea"):
            if "id" not in ta["attrs"]:
                continue
            ta_id = ta["attrs"]["id"]
            assert ta_id in label_fors, (
                f"<textarea id='{ta_id}'> has no <label for='{ta_id}'>"
            )


class TestTablists:
    """role=tablist containers must satisfy the ARIA tab pattern."""

    def test_tablists_have_tabs(self, page):
        tablists = page.by_role("tablist")
        tabs     = page.by_role("tab")
        assert tablists, "No role=tablist found"
        assert len(tabs) >= 2, "Expected at least 2 role=tab elements"

    def test_tabs_have_aria_controls(self, page):
        page_ids = page.ids()
        for tab in page.by_role("tab"):
            tab_id  = tab["attrs"].get("id", "<no id>")
            controls = tab["attrs"].get("aria-controls", "")
            assert controls, f"role=tab id='{tab_id}' missing aria-controls"
            assert controls in page_ids, (
                f"role=tab id='{tab_id}' aria-controls='{controls}' "
                f"points to a non-existent id"
            )

    def test_tabs_have_aria_selected(self, page):
        for tab in page.by_role("tab"):
            tab_id = tab["attrs"].get("id", "<no id>")
            selected = tab["attrs"].get("aria-selected")
            assert selected in ("true", "false"), (
                f"role=tab id='{tab_id}' must have aria-selected='true' or 'false', "
                f"got {selected!r}"
            )

    def test_tab_controls_point_to_tabpanels(self, page):
        tabpanel_ids = {el["attrs"].get("id") for el in page.by_role("tabpanel")}
        for tab in page.by_role("tab"):
            tab_id  = tab["attrs"].get("id", "<no id>")
            controls = tab["attrs"].get("aria-controls", "")
            if controls:
                assert controls in tabpanel_ids, (
                    f"role=tab id='{tab_id}' aria-controls='{controls}' "
                    f"must point to a role=tabpanel element"
                )

    def test_exactly_one_tab_selected_per_tablist(self, page):
        """Each tablist should start with exactly one selected tab."""
        # We only have two tablists (#auth-tablist and .about-dialog__tabs);
        # check the auth one which is always in the DOM.
        auth_tablist_id = "auth-tablist"
        auth_tab_ids = {"tab-signin", "tab-register"}
        selected = [
            el for el in page.by_role("tab")
            if el["attrs"].get("id") in auth_tab_ids
            and el["attrs"].get("aria-selected") == "true"
        ]
        assert len(selected) == 1, (
            f"Auth tablist should have exactly 1 selected tab at load time, "
            f"found {len(selected)}"
        )

    def test_about_tabs_have_roving_tabindex(self, page):
        """About-dialog tabs must implement roving tabindex (APG pattern)."""
        about_tab_ids = {"about-tab-principle", "about-tab-why"}
        about_tabs = [
            el for el in page.by_role("tab")
            if el["attrs"].get("id") in about_tab_ids
        ]
        assert len(about_tabs) == 2, "Expected 2 about-dialog tabs"

        tabindex_values = {el["attrs"].get("id"): el["attrs"].get("tabindex") for el in about_tabs}
        values = set(tabindex_values.values())
        assert "0" in values,  "No about-dialog tab has tabindex='0' (roving tabindex broken)"
        assert "-1" in values, "No about-dialog tab has tabindex='-1' (roving tabindex broken)"

    def test_auth_tabs_have_roving_tabindex(self, page):
        auth_tab_ids = {"tab-signin", "tab-register"}
        auth_tabs = [
            el for el in page.by_role("tab")
            if el["attrs"].get("id") in auth_tab_ids
        ]
        assert len(auth_tabs) == 2, "Expected 2 auth tabs"
        tabindex_values = {el["attrs"].get("id"): el["attrs"].get("tabindex") for el in auth_tabs}
        values = set(tabindex_values.values())
        assert "0" in values,  "No auth tab has tabindex='0'"
        assert "-1" in values, "No auth tab has tabindex='-1'"


class TestLiveRegions:
    def test_a11y_live_region_exists(self, page):
        live = page.by_id("a11y-live")
        assert live is not None, "Missing #a11y-live live region"
        assert live["attrs"].get("role") == "status"
        assert live["attrs"].get("aria-live") == "polite"
        assert live["attrs"].get("aria-atomic") == "true"

    def test_startup_banner_is_alert(self, page):
        banner = page.by_id("startup-banner")
        assert banner is not None, "Missing #startup-banner"
        assert banner["attrs"].get("role") == "alert", (
            "#startup-banner should be role=alert for immediate announcement"
        )

    def test_parse_status_region(self, page):
        status = page.by_id("status")
        assert status is not None, "Missing #status live region"
        assert status["attrs"].get("role") == "status"

    def test_auth_status_region(self, page):
        auth_status = page.by_id("auth-status")
        assert auth_status is not None, "Missing #auth-status live region"
        assert auth_status["attrs"].get("role") == "status"


class TestLandmarks:
    def test_main_landmark_exists(self, page):
        mains = page.by_tag("main")
        assert mains, "No <main> element found"

    def test_detail_aside_has_label(self, page):
        asides = page.by_tag("aside")
        assert asides, "No <aside> found for detail panel"
        labelled = [a for a in asides if a["attrs"].get("aria-label")]
        assert labelled, "<aside> detail panel missing aria-label"

    def test_footer_exists(self, page):
        footers = page.by_tag("footer")
        assert footers, "No <footer> element found"

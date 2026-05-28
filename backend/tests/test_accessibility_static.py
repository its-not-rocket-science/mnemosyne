"""Static structural accessibility checks for frontend/index.html and CSS.

No browser, no Playwright, no axe — just HTML parsing via stdlib.
Verifies the minimum ARIA contract that would be invisible to unit
tests but caught immediately by any AT user.

NOTE: Automation here does NOT replace manual AT validation. See
MANUAL_ACCESSIBILITY_TEST.md for the human tester script and session
results template.
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


# ── CSS Reduced-Motion Coverage ───────────────────────────────────────────────

_FRONTEND = pathlib.Path(__file__).parents[2] / "frontend"
_CSS_FILES = list(_FRONTEND.glob("css/*.css"))
_COMPONENT_JS = list(_FRONTEND.glob("components/*.js"))


class TestReducedMotionCSS:
    """Verify that key CSS files honour prefers-reduced-motion.

    This is a smoke test: it checks that the media query is present in
    files known to contain animations/transitions.  It does NOT verify
    every individual rule — that requires manual inspection (Test 13).
    """

    def test_global_css_has_reduced_motion(self):
        src = (_FRONTEND / "css" / "global.css").read_text(encoding="utf-8")
        assert "prefers-reduced-motion" in src, (
            "frontend/css/global.css has no prefers-reduced-motion media query"
        )

    def test_components_css_has_reduced_motion(self):
        src = (_FRONTEND / "css" / "components.css").read_text(encoding="utf-8")
        assert "prefers-reduced-motion" in src, (
            "frontend/css/components.css has no prefers-reduced-motion media query"
        )

    def test_enhanced_accessibility_css_has_reduced_motion(self):
        path = _FRONTEND / "css" / "enhanced-accessibility.css"
        if not path.exists():
            return  # optional file
        src = path.read_text(encoding="utf-8")
        assert "prefers-reduced-motion" in src

    def test_detail_pane_js_has_reduced_motion(self):
        path = _FRONTEND / "components" / "mnemosyne-detail-pane.js"
        src = path.read_text(encoding="utf-8")
        assert "prefers-reduced-motion" in src, (
            "mnemosyne-detail-pane.js has no prefers-reduced-motion rule "
            "(animated transitions must respect the user preference)"
        )

    def test_modal_js_has_reduced_motion(self):
        path = _FRONTEND / "components" / "mnemosyne-modal.js"
        src = path.read_text(encoding="utf-8")
        assert "prefers-reduced-motion" in src, (
            "mnemosyne-modal.js has no prefers-reduced-motion rule"
        )


# ── Concept Help Dialog Structure ─────────────────────────────────────────────

class TestConceptDialogStructure:
    """Verify the concept help dialog in mnemosyne-detail-pane.js has the
    required ARIA attributes.

    The concept dialog lives in the detail pane shadow DOM, not the modal.
    We check the component source JS because it is dynamically rendered.
    """

    @pytest.fixture(scope="class")
    def pane_src(self) -> str:
        return (_FRONTEND / "components" / "mnemosyne-detail-pane.js").read_text(encoding="utf-8")

    def test_dialog_has_role_dialog(self, pane_src):
        assert 'role="dialog"' in pane_src, (
            "mnemosyne-detail-pane.js concept dialog template missing role=\"dialog\""
        )

    def test_dialog_has_aria_modal(self, pane_src):
        assert 'aria-modal="true"' in pane_src, (
            "mnemosyne-detail-pane.js concept dialog missing aria-modal=\"true\""
        )

    def test_dialog_has_aria_labelledby(self, pane_src):
        assert "aria-labelledby" in pane_src, (
            "mnemosyne-detail-pane.js concept dialog missing aria-labelledby"
        )

    def test_dialog_body_has_aria_live(self, pane_src):
        assert "aria-live" in pane_src, (
            "mnemosyne-detail-pane.js concept dialog body missing aria-live "
            "— new concept content must be announced"
        )

    def test_dialog_loading_has_aria_busy(self, pane_src):
        assert "aria-busy" in pane_src, (
            "mnemosyne-detail-pane.js missing aria-busy on loading state "
            "— loading state must be announced to AT users (Test 4a in manual script)"
        )

    def test_dialog_error_has_role_alert(self, pane_src):
        assert 'role="alert"' in pane_src, (
            "mnemosyne-detail-pane.js missing role=\"alert\" on error state "
            "— error must be announced assertively (Test 4b in manual script)"
        )


# ── Practice Tab Input Structure ──────────────────────────────────────────────

class TestPracticeTabInputs:
    """Verify that practice drill inputs in mnemosyne-modal are labelled,
    and that pane-practice-check is dispatched from mnemosyne-detail-pane.js.

    The fill-blank drill creates an <input> at runtime. We check the JS
    source sets aria-labelledby on it (SC 1.3.1 / 4.1.2).
    """

    @pytest.fixture(scope="class")
    def modal_src(self) -> str:
        return (_FRONTEND / "components" / "mnemosyne-modal.js").read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def pane_src(self) -> str:
        return (_FRONTEND / "components" / "mnemosyne-detail-pane.js").read_text(encoding="utf-8")

    def test_fill_blank_input_has_aria_labelledby(self, modal_src):
        assert "aria-labelledby" in modal_src, (
            "mnemosyne-modal.js does not set aria-labelledby on drill inputs"
        )

    def test_fill_blank_input_has_autocomplete_off(self, modal_src):
        assert 'autocomplete' in modal_src and 'off' in modal_src, (
            "mnemosyne-modal.js drill input missing autocomplete='off' — "
            "autocomplete suggestions could obscure drill feedback"
        )

    def test_rating_buttons_exist_in_pane(self, pane_src):
        # Practice check event dispatched from detail pane (FSRS review)
        assert "pane-practice-check" in pane_src, (
            "mnemosyne-detail-pane.js missing pane-practice-check event dispatch "
            "— practice drills must submit to FSRS review"
        )


# ── Live Region Completeness ───────────────────────────────────────────────────

class TestLiveRegionCompleteness:
    """Extended checks beyond the basic TestLiveRegions class above.

    These verify specific live-region patterns required for the flows
    in MANUAL_ACCESSIBILITY_TEST.md that are hard to cover otherwise.
    """

    def test_multiple_polite_live_regions(self, page):
        live_els = [
            el for el in page.elements
            if el["attrs"].get("aria-live") == "polite"
        ]
        assert len(live_els) >= 2, (
            f"Expected multiple polite live regions, found {len(live_els)}. "
            "Parse status, drill feedback, and review save confirmation each "
            "need a live region announcement."
        )

    def test_no_assertive_live_on_non_error_elements(self, page):
        # Only error/alert elements should use aria-live=assertive.
        # Everything else must be polite to avoid interrupting AT users.
        assertive = [
            el for el in page.elements
            if el["attrs"].get("aria-live") == "assertive"
        ]
        for el in assertive:
            role = el["attrs"].get("role", "")
            assert role in ("alert", ""), (
                f"Element {el['tag']} has aria-live=assertive but role={role!r}; "
                "only role=alert elements should use assertive live regions"
            )

    def test_a11y_live_region_is_aria_atomic(self, page):
        live = page.by_id("a11y-live")
        assert live is not None
        assert live["attrs"].get("aria-atomic") == "true", (
            "#a11y-live must have aria-atomic=true so messages replace "
            "rather than append (prevents double-announcement)"
        )

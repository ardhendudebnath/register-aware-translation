"""
The markup contract: the page has to be usable without a mouse or a screen.

Accessibility regressions are silent. Nothing throws when a live region loses
its role, an input loses its label or a heading level is skipped — the page
looks identical and simply stops working for somebody. So the properties are
asserted here rather than trusted to survive the next panel someone adds.

These are static checks on the template. They cannot see what JavaScript
builds at runtime (the chips, the pad, the transcript), which is checked in the
browser instead.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import pytest

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "index.html"
SERVICE_WORKER = Path(__file__).resolve().parents[1] / "static" / "sw.js"

#: Controls that must carry a name the user can hear.
NAMED_CONTROLS = {"input", "select", "textarea", "button"}


class Page(HTMLParser):
    """Just enough parsing to ask structural questions."""

    def __init__(self, html: str):
        super().__init__()
        self.elements: list[tuple[str, dict, tuple[str, ...]]] = []
        self.labelled_by: set[str] = set()      # ids a <label for=...> points at
        self.headings: list[str] = []
        self._stack: list[str] = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = {k: (v or "") for k, v in attrs}
        self.elements.append((tag, attributes, tuple(self._stack)))
        if tag == "label" and attributes.get("for"):
            self.labelled_by.add(attributes["for"])
        if tag in {"h1", "h2", "h3", "h4"}:
            self.headings.append(tag)
        if tag not in {"br", "hr", "img", "input", "link", "meta", "source"}:
            self._stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self._stack:
            while self._stack and self._stack.pop() != tag:
                pass

    def find(self, **attrs):
        """Elements whose attributes match all the given pairs."""
        return [
            (tag, a, stack) for tag, a, stack in self.elements
            if all(a.get(k) == v for k, v in attrs.items())
        ]

    def by_id(self, element_id: str):
        found = self.find(id=element_id)
        return found[0] if found else None


@pytest.fixture(scope="module")
def page() -> Page:
    return Page(TEMPLATE.read_text(encoding="utf-8"))


# ------------------------------------------------------------------- naming


def test_every_control_can_be_named_out_loud(page):
    """
    A control with no accessible name is announced as "edit text, blank" —
    which tells somebody there is a box and nothing about what it is for.
    """
    for tag, attrs, stack in page.elements:
        if tag not in NAMED_CONTROLS or attrs.get("type") == "hidden":
            continue
        named = (
            attrs.get("aria-label")
            or attrs.get("aria-labelledby")
            or attrs.get("id") in page.labelled_by
            or "label" in stack         # wrapped in its own <label>
            or tag == "button"          # buttons are named by their text
        )
        assert named, f"<{tag} id={attrs.get('id')!r}> has no accessible name"


def test_buttons_that_are_only_a_symbol_carry_a_label(page):
    """⇄ reads as nothing. Anything whose text is punctuation needs a label."""
    for tag, attrs, _ in page.elements:
        if tag != "button":
            continue
        if attrs.get("class", "").startswith("swap") or attrs.get("id") == "swapLangs":
            assert attrs.get("aria-label"), "the swap button needs a spoken name"


# ------------------------------------------------------------- live regions


@pytest.mark.parametrize("element_id, attribute, value", [
    # Connection state is the one thing that explains why nothing is happening.
    ("status", "role", "status"),
    # A rudeness warning that is only visible is no warning at all.
    ("warning", "role", "alert"),
    # The answer itself: announced when it settles.
    ("outputText", "aria-live", "polite"),
    # New turns in a conversation arrive without the reader asking.
    ("transcript", "aria-live", "polite"),
])
def test_things_that_change_on_their_own_are_announced(page, element_id, attribute, value):
    found = page.by_id(element_id)
    assert found, f"#{element_id} is missing"
    assert found[1].get(attribute) == value, (
        f"#{element_id} changes by itself but is not announced"
    )


# ---------------------------------------------------------------- structure


def test_there_is_one_h1_and_the_panels_are_h2(page):
    assert page.headings.count("h1") == 1
    assert "h3" not in page.headings or page.headings.index("h2") < page.headings.index("h3")


def test_the_page_declares_its_language(page):
    html = page.find(lang="en")
    assert html and html[0][0] == "html", "<html lang> is how a reader picks a voice"


def test_the_footer_is_a_landmark_of_its_own(page):
    """A <footer> inside <main> is not the page's contentinfo landmark."""
    footers = [stack for tag, _, stack in page.elements if tag == "footer"]
    assert footers, "no footer"
    for stack in footers:
        assert "main" not in stack


def test_the_skip_link_exists_and_points_somewhere_real(page):
    links = [a for tag, a, _ in page.elements if tag == "a" and "skip" in a.get("class", "")]
    assert links, "63 focusable controls and no way past the first few"
    target = links[0].get("href", "")
    assert target.startswith("#")
    assert page.by_id(target[1:]), f"the skip link points at {target}, which does not exist"


def test_nothing_jumps_the_tab_order(page):
    """A positive tabindex reorders the page for keyboard users and nobody else."""
    for tag, attrs, _ in page.elements:
        value = attrs.get("tabindex")
        if value and value.lstrip("-").isdigit():
            assert int(value) <= 0, f"<{tag}> sets tabindex={value}"


# ----------------------------------------------------------- service worker


def test_the_live_socket_is_never_served_from_a_cache():
    """
    Speculative translation runs over socket.io. The worker used to cache every
    same-origin GET, which meant a cache full of long-poll frames carrying
    session ids — and handing one of those back to a live connection breaks the
    stream it belongs to.
    """
    source = SERVICE_WORKER.read_text(encoding="utf-8")
    assert '"/socket.io/"' in source, "the worker no longer excludes the socket"
    assert "isShell" in source, "the worker caches by rule, not by 'it was a GET'"

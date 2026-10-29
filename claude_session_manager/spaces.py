"""Terminal-workspace navigation: the "spaces" / "agents" sidebar panel and
the per-space tab strip.

A space is a project folder with open tabs; the tab strip only shows the
current space's tabs. The window owns the pages and pushes snapshots in via
update(); these widgets only render and emit what the user picked.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, GObject, Gtk  # noqa: E402

from .agentstate import rollup
from .i18n import _

_ELLIPSIZE_END = 3  # Pango.EllipsizeMode.END


def git_branch(path: str | None) -> str:
    """Current branch of the git checkout containing path ('' if none).
    Reads .git/HEAD directly (worktrees: follows the gitdir file)."""
    if not path:
        return ""
    for folder in (Path(path), *Path(path).parents):
        git = folder / ".git"
        try:
            if git.is_file():  # worktree / submodule: "gitdir: <path>"
                git = (folder / git.read_text().strip().removeprefix("gitdir: ")).resolve()
            if git.is_dir():
                head = (git / "HEAD").read_text().strip()
                return head.removeprefix("ref: refs/heads/") if head.startswith("ref:") else head[:7]
        except OSError:
            return ""
    return ""


@dataclass
class TabInfo:
    page: Adw.TabPage
    title: str
    space: str  # project folder
    agent: str  # e.g. "claude", "cursor", "replay"
    status: str  # agent state: "working" | "blocked" | "done" | "idle"
    emoji: str = ""  # the tab's emoji, also the start of its title


def space_name(space: str) -> str:
    return GLib.path_get_basename(space) or space


def _dot(status: str) -> Gtk.Widget:
    dot = Gtk.Box(valign=Gtk.Align.CENTER)
    dot.add_css_class("status-dot")
    if status:
        dot.add_css_class(status)
    return dot


def section_shown(state, key: str) -> bool:
    """Whether a sidebar section is switched on in the preferences."""
    return bool(state.get_setting(f"sidebar_show_{key}"))


class SectionHeader(Gtk.Box):
    """A sidebar section title; clicking the arrow + title folds the section.
    The folded state is saved, and on_toggle() lets the owner re-show its
    widgets (visibility also depends on things only the owner knows)."""

    def __init__(self, key: str, text: str, state, on_toggle: Callable[[], None],
                 suffix: Gtk.Widget | None = None) -> None:
        super().__init__(spacing=6)
        self.add_css_class("section-title")
        self._key = key
        self._state = state
        self._on_toggle = on_toggle

        toggle = Gtk.Box(spacing=4, hexpand=True)
        toggle.set_cursor_from_name("pointer")
        self._arrow = Gtk.Image()
        self._arrow.add_css_class("dim-label")
        toggle.append(self._arrow)
        label = Gtk.Label(label=text, xalign=0.0, hexpand=True)
        label.add_css_class("dim-label")
        toggle.append(label)
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: self._toggle())
        toggle.add_controller(click)
        self.append(toggle)
        if suffix is not None:
            self.append(suffix)
        self._sync_arrow()

    @property
    def collapsed(self) -> bool:
        return self._key in (self._state.get_setting("sidebar_collapsed") or [])

    def _toggle(self) -> None:
        collapsed = set(self._state.get_setting("sidebar_collapsed") or []) ^ {self._key}
        self._state.set_setting("sidebar_collapsed", sorted(collapsed))
        self._sync_arrow()
        self._on_toggle()

    def _sync_arrow(self) -> None:
        self._arrow.set_from_icon_name("pan-end-symbolic" if self.collapsed else "pan-down-symbolic")


class SpacesPanel(Gtk.Box):
    """Top of the sidebar: the open spaces, then every running agent."""

    __gsignals__ = {
        "select-space": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "select-page": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self, state) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("spaces-panel")
        self._state = state
        self._has_tabs = False

        new_btn = Gtk.Button(icon_name="list-add-symbolic")
        new_btn.add_css_class("flat")
        new_btn.set_tooltip_text(_("New space: start an agent in a folder"))
        new_btn.set_action_name("win.new-space")
        self._spaces_header = SectionHeader("spaces", _("spaces"), state, self.apply_sections, new_btn)
        self.append(self._spaces_header)

        self._spaces = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._spaces.add_css_class("navigation-sidebar")
        self._spaces.connect("row-activated", lambda _l, row: self.emit("select-space", row.key))
        self.append(self._spaces)

        self._agents_header = SectionHeader("agents", _("agents"), state, self.apply_sections)
        self.append(self._agents_header)
        self._agents = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._agents.add_css_class("navigation-sidebar")
        self._agents.connect("row-activated", lambda _l, row: self.emit("select-page", row.key))
        self.append(self._agents)
        self.apply_sections()

    def apply_sections(self) -> None:
        """Show / fold the sections per the preferences and title clicks."""
        show_spaces = section_shown(self._state, "spaces")
        show_agents = section_shown(self._state, "agents")
        self._spaces_header.set_visible(show_spaces)
        self._spaces.set_visible(show_spaces and not self._spaces_header.collapsed)
        self._agents_header.set_visible(show_agents and self._has_tabs)
        self._agents.set_visible(show_agents and self._has_tabs and not self._agents_header.collapsed)
        self.set_visible(show_spaces or (show_agents and self._has_tabs))

    def update(self, tabs: list[TabInfo], current: TabInfo | None) -> None:
        self._spaces.remove_all()
        self._agents.remove_all()
        spaces: dict[str, list[TabInfo]] = {}
        for tab in tabs:
            spaces.setdefault(tab.space, []).append(tab)

        if not spaces:
            hint = Gtk.Label(label=_("no open spaces"), xalign=0.0)
            hint.add_css_class("dim-label")
            hint.set_margin_start(12)
            hint.set_margin_bottom(6)
            self._spaces.append(hint)
            hint.get_parent().set_activatable(False)
        for space, members in spaces.items():
            # a blocked agent makes its space blocked, a working one active…
            status = rollup([t.status for t in members])
            branch = git_branch(space)
            row = self._row(space_name(space), branch, status, current is not None and current.space == space)
            row.key = space
            row.set_tooltip_text(space)
            self._spaces.append(row)

        self._has_tabs = bool(tabs)
        self.apply_sections()
        for tab in tabs:
            name = space_name(tab.space)  # herdr-style "space · tab"
            title = name if tab.title == name else f"{name} · {tab.title}"
            row = self._row(title, tab.agent, tab.status,
                            current is not None and current.page is tab.page)
            row.key = tab.page
            self._agents.append(row)

    @staticmethod
    def _row(title: str, subtitle: str, status: str, is_current: bool) -> Gtk.ListBoxRow:
        top = Gtk.Box(spacing=8)
        top.append(_dot(status))
        label = Gtk.Label(label=title, xalign=0.0, hexpand=True)
        label.set_ellipsize(_ELLIPSIZE_END)
        top.append(label)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(top)
        if subtitle:
            sub = Gtk.Label(label=subtitle, xalign=0.0)
            sub.set_ellipsize(_ELLIPSIZE_END)
            sub.add_css_class("dim-label")
            sub.set_margin_start(16)  # align under the title, past the dot
            box.append(sub)
        row = Gtk.ListBoxRow(child=box)
        if is_current:
            row.add_css_class("current")
        return row


class TabStrip(Gtk.Box):
    """Flat tab row for the current space, with a trailing "+"."""

    __gsignals__ = {
        "select": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "close": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "menu": (GObject.SignalFlags.RUN_FIRST, None, (object, object)),  # page, widget
        "emoji": (GObject.SignalFlags.RUN_FIRST, None, (object,)),  # emoji clicked
    }

    def __init__(self) -> None:
        super().__init__(spacing=2)
        self.add_css_class("tab-strip")
        self._tabs = Gtk.Box(spacing=2)
        scrolled = Gtk.ScrolledWindow(child=self._tabs, hexpand=True)
        scrolled.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        scrolled.set_propagate_natural_height(True)
        self.append(scrolled)
        add = Gtk.Button(label="+")
        add.add_css_class("flat")
        add.set_tooltip_text(_("New agent in this space"))
        add.set_action_name("win.new-in-space")
        self._tabs_add = add
        self._buttons: dict[Adw.TabPage, Gtk.Widget] = {}

    def update(self, tabs: list[TabInfo], current: TabInfo | None) -> None:
        while (child := self._tabs.get_first_child()) is not None:
            self._tabs.remove(child)
        self._buttons = {}
        for tab in tabs:
            button = self._tab(tab, current is not None and current.page is tab.page)
            self._buttons[tab.page] = button
            self._tabs.append(button)
        self._tabs.append(self._tabs_add)

    def _on_emoji_pressed(self, gesture: Gtk.GestureClick, _n, _x, _y, page) -> None:
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)  # not a tab click
        self.emit("select", page)
        self.emit("emoji", page)

    def tab_bounds(self, page: Adw.TabPage) -> Gdk.Rectangle | None:
        """Where a page's tab sits, in strip coordinates (to anchor popovers)."""
        button = self._buttons.get(page)
        ok, rect = button.compute_bounds(self) if button is not None else (False, None)
        if not ok:
            return None
        bounds = Gdk.Rectangle()
        bounds.x, bounds.y = int(rect.get_x()), int(rect.get_y())
        bounds.width, bounds.height = int(rect.get_width()), int(rect.get_height())
        return bounds

    def _tab(self, tab: TabInfo, selected: bool) -> Gtk.Widget:
        box = Gtk.Box(spacing=6)
        if tab.status != "idle":
            box.append(_dot(tab.status))
        title = tab.title
        if tab.emoji and title.startswith(tab.emoji):
            # the emoji is its own click target: it opens the picker
            emoji = Gtk.Label(label=tab.emoji)
            emoji.add_css_class("tab-emoji")
            emoji.set_tooltip_text(_("Change emoji"))
            emoji.set_cursor_from_name("pointer")
            click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
            click.connect("pressed", self._on_emoji_pressed, tab.page)
            emoji.add_controller(click)
            box.append(emoji)
            title = title[len(tab.emoji):].lstrip()
        box.append(Gtk.Label(label=title, max_width_chars=28, ellipsize=_ELLIPSIZE_END))
        button = Gtk.Button(child=box)
        button.add_css_class("flat")
        button.add_css_class("strip-tab")
        if selected:
            button.add_css_class("selected")
        button.set_tooltip_text(tab.page.get_tooltip())
        button.connect("clicked", lambda *_: self.emit("select", tab.page))

        middle = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        middle.connect("pressed", lambda *_: self.emit("close", tab.page))
        button.add_controller(middle)
        right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right.connect("pressed", lambda *_: self.emit("menu", tab.page, button))
        button.add_controller(right)
        return button

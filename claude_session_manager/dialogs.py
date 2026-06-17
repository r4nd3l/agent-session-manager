"""Reusable dialogs, kept out of the main window."""

from __future__ import annotations

import threading
from collections.abc import Callable

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

from .formatting import format_size, format_timestamp, format_tokens
from .i18n import _
from .providers import get_provider
from .sessions import (
    Session,
    SessionDetails,
    configured_mcp_servers,
    read_mcp_config,
)


def rename_dialog(parent: Gtk.Widget, body: str, current: str, on_save: Callable[[str], None]) -> None:
    toplevel = parent.get_toplevel() if not isinstance(parent, Gtk.Window) else parent
    dialog = Gtk.MessageDialog(
        transient_for=toplevel,
        modal=True,
        message_type=Gtk.MessageType.QUESTION,
        text=_("Rename session"),
    )
    dialog.format_secondary_text(body)
    dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Save"), Gtk.ResponseType.OK)
    entry = Gtk.Entry(text=current)
    entry.set_placeholder_text(_("Custom name"))
    entry.set_activates_default(True)
    dialog.get_content_area().pack_start(entry, False, False, 8)
    dialog.set_default_response(Gtk.ResponseType.OK)
    dialog.show_all()
    response = dialog.run()
    if response == Gtk.ResponseType.OK:
        on_save(entry.get_text())
    dialog.destroy()


def emoji_dialog(parent: Gtk.Widget, current: str, on_save: Callable[[str], None]) -> None:
    toplevel = parent.get_toplevel() if not isinstance(parent, Gtk.Window) else parent
    dialog = Gtk.MessageDialog(
        transient_for=toplevel,
        modal=True,
        message_type=Gtk.MessageType.QUESTION,
        text=_("Set tab emoji"),
    )
    dialog.format_secondary_text(_("Shown before the tab title. Leave empty to remove."))
    dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Save"), Gtk.ResponseType.OK)
    entry = Gtk.Entry(text=current)
    entry.set_placeholder_text(_("e.g. \U0001f680"))
    entry.set_activates_default(True)
    dialog.get_content_area().pack_start(entry, False, False, 8)
    dialog.set_default_response(Gtk.ResponseType.OK)
    dialog.show_all()
    response = dialog.run()
    if response == Gtk.ResponseType.OK:
        on_save(entry.get_text())
    dialog.destroy()


def confirm_dialog(
    parent: Gtk.Widget,
    heading: str,
    body: str,
    confirm_label: str,
    on_confirm: Callable[[], None],
) -> None:
    toplevel = parent.get_toplevel() if not isinstance(parent, Gtk.Window) else parent
    dialog = Gtk.MessageDialog(
        transient_for=toplevel,
        modal=True,
        message_type=Gtk.MessageType.WARNING,
        text=heading,
    )
    dialog.format_secondary_text(body)
    dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
    btn = dialog.add_button(confirm_label, Gtk.ResponseType.OK)
    btn.get_style_context().add_class("destructive-action")
    dialog.set_default_response(Gtk.ResponseType.CANCEL)
    dialog.show_all()
    response = dialog.run()
    dialog.destroy()
    if response == Gtk.ResponseType.OK:
        on_confirm()


def error_dialog(parent: Gtk.Widget, heading: str, body: str) -> None:
    toplevel = parent.get_toplevel() if not isinstance(parent, Gtk.Window) else parent
    dialog = Gtk.MessageDialog(
        transient_for=toplevel,
        modal=True,
        message_type=Gtk.MessageType.ERROR,
        text=heading,
        buttons=Gtk.ButtonsType.OK,
    )
    dialog.format_secondary_text(body)
    dialog.show_all()
    dialog.run()
    dialog.destroy()


# -- helper: a simple property row for detail dialogs --------------------------


def _make_prop_row(title: str, value: str, wrap: bool = False) -> Gtk.ListBoxRow:
    row = Gtk.ListBoxRow()
    row.set_selectable(False)
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    box.set_margin_top(6)
    box.set_margin_bottom(6)
    box.set_margin_start(12)
    box.set_margin_end(12)

    lbl_title = Gtk.Label(label=title, xalign=0.0)
    lbl_title.get_style_context().add_class("dim-label")
    lbl_title.set_size_request(140, -1)
    box.pack_start(lbl_title, False, False, 0)

    lbl_value = Gtk.Label(label=value, xalign=0.0)
    lbl_value.set_hexpand(True)
    lbl_value.set_selectable(True)
    if wrap:
        lbl_value.set_line_wrap(True)
        lbl_value.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    else:
        lbl_value.set_ellipsize(Pango.EllipsizeMode.END)
    box.pack_start(lbl_value, True, True, 0)

    row.add(box)
    return row


def _make_section_label(text: str) -> Gtk.Label:
    label = Gtk.Label(label=f"<b>{GLib.markup_escape_text(text)}</b>", xalign=0.0)
    label.set_use_markup(True)
    label.set_margin_top(12)
    label.set_margin_bottom(4)
    label.set_margin_start(12)
    return label


# -- MCP servers browser -------------------------------------------------------


def mcp_browser_dialog(parent: Gtk.Widget) -> None:
    toplevel = parent.get_toplevel() if not isinstance(parent, Gtk.Window) else parent
    config = read_mcp_config()

    dialog = Gtk.Dialog(
        title=_("MCP Servers"),
        transient_for=toplevel,
        modal=True,
    )
    dialog.set_default_size(540, 600)
    dialog.add_button(_("Close"), Gtk.ResponseType.CLOSE)

    content = dialog.get_content_area()
    content.set_spacing(6)

    subtitle = Gtk.Label(label=_("Read-only"), xalign=0.0)
    subtitle.get_style_context().add_class("dim-label")
    subtitle.set_margin_start(12)
    subtitle.set_margin_top(6)
    content.pack_start(subtitle, False, False, 0)

    if config.is_empty:
        empty_label = Gtk.Label(label=_("No MCP servers configured"))
        empty_label.set_margin_top(20)
        content.pack_start(empty_label, False, False, 0)
    else:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        if config.global_servers:
            vbox.pack_start(_make_section_label(_("Global — Available to every project")), False, False, 0)
            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.NONE)
            for server in config.global_servers:
                listbox.add(_make_prop_row(server.name, server.summary or "—"))
            vbox.pack_start(listbox, False, False, 0)

        for path, servers in config.project_servers:
            vbox.pack_start(_make_section_label(GLib.path_get_basename(path)), False, False, 0)
            desc = Gtk.Label(label=path, xalign=0.0)
            desc.get_style_context().add_class("dim-label")
            desc.set_margin_start(12)
            vbox.pack_start(desc, False, False, 0)
            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.NONE)
            for server in servers:
                listbox.add(_make_prop_row(server.name, server.summary or "—"))
            vbox.pack_start(listbox, False, False, 0)

        scrolled.add(vbox)
        content.pack_start(scrolled, True, True, 0)

    dialog.show_all()
    dialog.run()
    dialog.destroy()


# -- session details ----------------------------------------------------------


def details_dialog(parent: Gtk.Widget, session: Session, title: str) -> None:
    toplevel = parent.get_toplevel() if not isinstance(parent, Gtk.Window) else parent
    provider = get_provider(session.provider)

    dialog = Gtk.Dialog(
        title=_("Session details"),
        transient_for=toplevel,
        modal=True,
    )
    dialog.set_default_size(480, 560)
    dialog.add_button(_("Close"), Gtk.ResponseType.CLOSE)

    content = dialog.get_content_area()
    content.set_spacing(4)

    header_label = Gtk.Label(label=f"<b>{GLib.markup_escape_text(title)}</b>", xalign=0.0)
    header_label.set_use_markup(True)
    header_label.set_margin_start(12)
    header_label.set_margin_top(8)
    content.pack_start(header_label, False, False, 0)

    sub_label = Gtk.Label(label=session.project_name, xalign=0.0)
    sub_label.get_style_context().add_class("dim-label")
    sub_label.set_margin_start(12)
    content.pack_start(sub_label, False, False, 0)

    spinner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    spinner_box.set_margin_top(20)
    spinner_box.set_halign(Gtk.Align.CENTER)
    spinner = Gtk.Spinner()
    spinner.start()
    spinner_box.pack_start(spinner, False, False, 0)
    spinner_box.pack_start(Gtk.Label(label=_("Reading transcript…")), False, False, 0)
    content.pack_start(spinner_box, False, False, 0)

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scrolled.set_vexpand(True)
    detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    scrolled.add(detail_box)
    content.pack_start(scrolled, True, True, 0)

    dialog.show_all()
    dialog_alive = True

    def mark_dialog_destroyed(_dialog) -> None:
        nonlocal dialog_alive
        dialog_alive = False

    dialog.connect("destroy", mark_dialog_destroyed)

    def populate(details: SessionDetails, mcp_servers: list[str]) -> bool:
        if not dialog_alive:
            return GLib.SOURCE_REMOVE
        spinner_box.hide()

        info_list = Gtk.ListBox()
        info_list.set_selection_mode(Gtk.SelectionMode.NONE)

        def add(row_title: str, value: str) -> None:
            info_list.add(_make_prop_row(row_title, value))

        add(_("Agent"), provider.name)
        add(_("Session ID"), session.session_id)
        add(_("Directory"), session.cwd or _("unknown"))
        if details.first_timestamp:
            add(_("Created"), format_timestamp(details.first_timestamp))
        if details.last_timestamp:
            add(_("Last activity"), format_timestamp(details.last_timestamp))
        add(_("Messages"), f"{details.user_messages} user · {details.assistant_messages} assistant")
        if details.tool_calls:
            add(_("Tool calls"), str(details.tool_calls))
        if details.models:
            add(_("Models"), ", ".join(details.models))
        if details.input_tokens or details.output_tokens or details.cache_read_tokens:
            add(
                _("Tokens"),
                f"{format_tokens(details.input_tokens)} in · "
                f"{format_tokens(details.output_tokens)} out · "
                f"{format_tokens(details.cache_read_tokens)} cache-read",
            )
        add(_("Transcript size"), format_size(details.file_size))
        detail_box.pack_start(info_list, False, False, 0)

        if mcp_servers or details.mcp_tools:
            detail_box.pack_start(_make_section_label(_("MCP")), False, False, 0)
            mcp_list = Gtk.ListBox()
            mcp_list.set_selection_mode(Gtk.SelectionMode.NONE)
            mcp_list.add(_make_prop_row(_("Available to this project"), ", ".join(mcp_servers) or "—"))
            used = " · ".join(
                f"{server}: {count}"
                for server, count in sorted(details.mcp_tools.items(), key=lambda kv: -kv[1])
            )
            mcp_list.add(_make_prop_row(_("Tools used in this session"), used or "—"))
            detail_box.pack_start(mcp_list, False, False, 0)

        if details.messages:
            detail_box.pack_start(_make_section_label(_("Recent activity")), False, False, 0)
            recent_list = Gtk.ListBox()
            recent_list.set_selection_mode(Gtk.SelectionMode.NONE)
            for role, text in details.messages:
                recent_list.add(_make_prop_row(
                    _("You") if role == "user" else provider.name,
                    text,
                    wrap=True,
                ))
            detail_box.pack_start(recent_list, False, False, 0)

        detail_box.show_all()
        return GLib.SOURCE_REMOVE

    def work() -> None:
        details = provider.parse_details(session.jsonl_path)
        mcp_servers = configured_mcp_servers(session.cwd) if session.provider == "claude" else []
        GLib.idle_add(populate, details, mcp_servers)

    threading.Thread(target=work, daemon=True).start()
    dialog.run()
    dialog_alive = False
    dialog.destroy()

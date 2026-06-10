"""Reusable dialogs, kept out of the main window."""

from __future__ import annotations

import threading
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from .formatting import format_size, format_timestamp, format_tokens
from .sessions import (
    Session,
    SessionDetails,
    configured_mcp_servers,
    parse_details,
    read_mcp_config,
)


def rename_dialog(parent: Gtk.Widget, body: str, current: str, on_save: Callable[[str], None]) -> None:
    dialog = Adw.AlertDialog(heading="Rename session", body=body)
    entry = Gtk.Entry(text=current, placeholder_text="Custom name")
    entry.set_activates_default(True)
    dialog.set_extra_child(entry)
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("save", "Save")
    dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("save")
    dialog.connect(
        "response",
        lambda _d, response: on_save(entry.get_text()) if response == "save" else None,
    )
    dialog.present(parent)


def emoji_dialog(parent: Gtk.Widget, current: str, on_save: Callable[[str], None]) -> None:
    dialog = Adw.AlertDialog(
        heading="Set tab emoji",
        body="Shown before the tab title. Leave empty to remove.",
    )
    entry = Gtk.Entry(text=current, placeholder_text="e.g. 🚀")
    entry.set_property("show-emoji-icon", True)  # click the 🙂 icon to pick one
    entry.set_property("enable-emoji-completion", True)
    entry.set_activates_default(True)
    dialog.set_extra_child(entry)
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("save", "Save")
    dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("save")
    dialog.connect(
        "response",
        lambda _d, response: on_save(entry.get_text()) if response == "save" else None,
    )
    dialog.present(parent)


def confirm_dialog(
    parent: Gtk.Widget,
    heading: str,
    body: str,
    confirm_label: str,
    on_confirm: Callable[[], None],
) -> None:
    dialog = Adw.AlertDialog(heading=heading, body=body)
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("confirm", confirm_label)
    dialog.set_response_appearance("confirm", Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_default_response("cancel")
    dialog.connect(
        "response",
        lambda _d, response: on_confirm() if response == "confirm" else None,
    )
    dialog.present(parent)


def error_dialog(parent: Gtk.Widget, heading: str, body: str) -> None:
    dialog = Adw.AlertDialog(heading=heading, body=body)
    dialog.add_response("ok", "OK")
    dialog.present(parent)


# -- MCP servers browser -------------------------------------------------------


def mcp_browser_dialog(parent: Gtk.Widget) -> None:
    config = read_mcp_config()
    page = Adw.PreferencesPage()

    def server_row(name: str, summary: str) -> Adw.ActionRow:
        row = Adw.ActionRow(title=name, subtitle=summary or "—")
        row.set_property("subtitle-lines", 0)
        row.add_css_class("property")
        return row

    if config.is_empty:
        empty = Adw.PreferencesGroup()
        empty.add(Adw.ActionRow(title="No MCP servers configured"))
        page.add(empty)
    else:
        if config.global_servers:
            group = Adw.PreferencesGroup(
                title="Global", description="Available to every project"
            )
            for server in config.global_servers:
                group.add(server_row(server.name, server.summary))
            page.add(group)
        for path, servers in config.project_servers:
            group = Adw.PreferencesGroup(title=GLib.path_get_basename(path), description=path)
            for server in servers:
                group.add(server_row(server.name, server.summary))
            page.add(group)

    header = Adw.HeaderBar()
    header.set_title_widget(Adw.WindowTitle(title="MCP Servers", subtitle="Read-only"))
    view = Adw.ToolbarView()
    view.add_top_bar(header)
    view.set_content(page)

    dialog = Adw.Dialog(title="MCP Servers")
    dialog.set_content_width(540)
    dialog.set_content_height(600)
    dialog.set_child(view)
    dialog.present(parent)


# -- session details ----------------------------------------------------------


def details_dialog(parent: Gtk.Widget, session: Session, title: str) -> None:
    group = Adw.PreferencesGroup()
    spinner_row = Adw.ActionRow(title="Reading transcript…")
    spinner = Gtk.Spinner(spinning=True, valign=Gtk.Align.CENTER)
    spinner_row.add_suffix(spinner)
    group.add(spinner_row)

    page = Adw.PreferencesPage()
    page.add(group)

    header = Adw.HeaderBar()
    header.set_title_widget(Adw.WindowTitle(title=title, subtitle=session.project_name))
    view = Adw.ToolbarView()
    view.add_top_bar(header)
    view.set_content(page)

    dialog = Adw.Dialog(title="Session details")
    dialog.set_content_width(480)
    dialog.set_content_height(560)
    dialog.set_child(view)
    dialog.present(parent)

    def populate(details: SessionDetails, mcp_servers: list[str]) -> bool:
        page.remove(group)
        info = Adw.PreferencesGroup()

        def add(row_title: str, value: str) -> None:
            row = Adw.ActionRow(title=row_title, subtitle=value)
            row.add_css_class("property")
            info.add(row)

        add("Session ID", session.session_id)
        add("Directory", session.cwd or "unknown")
        add("Created", format_timestamp(details.first_timestamp))
        add("Last activity", format_timestamp(details.last_timestamp))
        add("Messages", f"{details.user_messages} user · {details.assistant_messages} assistant")
        add("Tool calls", str(details.tool_calls))
        add("Models", ", ".join(details.models) or "—")
        add(
            "Tokens",
            f"{format_tokens(details.input_tokens)} in · "
            f"{format_tokens(details.output_tokens)} out · "
            f"{format_tokens(details.cache_read_tokens)} cache-read",
        )
        add("Transcript size", format_size(details.file_size))
        page.add(info)

        if mcp_servers or details.mcp_tools:
            mcp = Adw.PreferencesGroup(title="MCP")

            def mcp_row(row_title: str, value: str) -> None:
                row = Adw.ActionRow(title=row_title, subtitle=value)
                row.set_property("subtitle-lines", 0)
                row.add_css_class("property")
                mcp.add(row)

            mcp_row("Available to this project", ", ".join(mcp_servers) or "—")
            used = " · ".join(
                f"{server}: {count}"
                for server, count in sorted(details.mcp_tools.items(), key=lambda kv: -kv[1])
            )
            mcp_row("Tools used in this session", used or "—")
            page.add(mcp)

        if details.messages:
            recent = Adw.PreferencesGroup(title="Recent activity")
            for role, text in details.messages:
                row = Adw.ActionRow(
                    title="You" if role == "user" else "Claude",
                    subtitle=text,
                )
                row.set_property("subtitle-lines", 0)  # wrap, no truncation
                row.add_css_class("property")
                recent.add(row)
            page.add(recent)
        return GLib.SOURCE_REMOVE

    def work() -> None:
        details = parse_details(session.jsonl_path)
        mcp_servers = configured_mcp_servers(session.cwd)
        GLib.idle_add(populate, details, mcp_servers)

    threading.Thread(target=work, daemon=True).start()

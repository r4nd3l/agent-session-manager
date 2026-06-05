"""Reusable dialogs, kept out of the main window."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from .sessions import Session, SessionDetails, parse_details


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


# -- session details ----------------------------------------------------------


def _format_tokens(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


def _format_size(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size} B"


def _format_timestamp(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        return (
            datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
        )
    except ValueError:
        return ts


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

    def populate(details: SessionDetails) -> bool:
        page.remove(group)
        info = Adw.PreferencesGroup()

        def add(row_title: str, value: str) -> None:
            row = Adw.ActionRow(title=row_title, subtitle=value)
            row.add_css_class("property")
            info.add(row)

        add("Session ID", session.session_id)
        add("Directory", session.cwd or "unknown")
        add("Created", _format_timestamp(details.first_timestamp))
        add("Last activity", _format_timestamp(details.last_timestamp))
        add("Messages", f"{details.user_messages} user · {details.assistant_messages} assistant")
        add("Tool calls", str(details.tool_calls))
        add("Models", ", ".join(details.models) or "—")
        add(
            "Tokens",
            f"{_format_tokens(details.input_tokens)} in · "
            f"{_format_tokens(details.output_tokens)} out · "
            f"{_format_tokens(details.cache_read_tokens)} cache-read",
        )
        add("Transcript size", _format_size(details.file_size))
        page.add(info)
        return GLib.SOURCE_REMOVE

    def work() -> None:
        details = parse_details(session.jsonl_path)
        GLib.idle_add(populate, details)

    threading.Thread(target=work, daemon=True).start()

from claude_session_manager.agentstate import detect_state, rollup

CLAUDE_PERMISSION = """
 Bash command
   rm -rf build
 Do you want to proceed?
 ❯ 1. Yes
   2. Yes, and don't ask again for rm commands
   3. No, and tell Claude what to do differently (esc)
"""

CLAUDE_QUESTION = """
 Which theme should be the default?
 ❯ 1. Catppuccin
   2. Gruvbox
 Enter to select · ↑/↓ to navigate · Esc to cancel
"""

CLAUDE_WORKING = """
> refactor the sidebar
✻ Crunching… (12s · ↑ 1.2k tokens · esc to interrupt)
"""

CLAUDE_IDLE = """
● Done. The sidebar is refactored.
────────────────────────
>
  ? for shortcuts
"""


def test_claude_states():
    assert detect_state("claude", "✳ Claude Code", CLAUDE_PERMISSION) == "blocked"
    assert detect_state("claude", "✳ Claude Code", CLAUDE_QUESTION) == "blocked"
    assert detect_state("claude", "✳ Claude Code", CLAUDE_WORKING) == "working"
    assert detect_state("claude", "⠂ Refactoring", CLAUDE_IDLE) == "working"  # title spinner
    assert detect_state("claude", "◐ Refactoring", CLAUDE_IDLE) == "working"  # 2.1.228+ spinner
    assert detect_state("claude", "✳ Claude Code", CLAUDE_IDLE) == "idle"
    model_picker = "Select model\n❯ 1. Opus\nEnter to set as default · Esc to cancel\nEnter to select"
    assert detect_state("claude", "✳ Claude Code", model_picker) == "idle"


def test_cursor_states():
    approval = "Waiting for approval\n  Run this command?\n  Run (once) (y)   Skip (esc or n)"
    assert detect_state("cursor", "", approval) == "blocked"
    assert detect_state("cursor", "", "⠋ Generating\n  ctrl+c to stop") == "working"
    assert detect_state("cursor", "", "→ Add a follow-up") == "idle"


def test_unknown_agent_and_rollup():
    assert detect_state("replay", "", CLAUDE_PERMISSION) == "idle"
    assert rollup(["idle", "done", "working"]) == "working"
    assert rollup(["working", "blocked"]) == "blocked"
    assert rollup(["idle", "done"]) == "done"
    assert rollup([]) == "idle"

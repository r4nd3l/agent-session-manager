from claude_session_manager.spaces import git_branch


def test_git_branch_reads_head_from_any_subfolder(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/feat/x\n")
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    assert git_branch(str(tmp_path / "src" / "pkg")) == "feat/x"


def test_git_branch_detached_worktree_and_none(tmp_path):
    real = tmp_path / "real-gitdir"
    real.mkdir()
    (real / "HEAD").write_text("0123456789abcdef\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {real}\n")
    assert git_branch(str(wt)) == "0123456"
    assert git_branch(None) == ""

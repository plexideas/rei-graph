from io import StringIO

from rich.console import Console

from dgk_cli.progress import ScanProgress


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=80)
    return console, buf


# ── normal-mode finish() ─────────────────────────────────────────────────────

def test_finish_contains_elapsed_nodes_rels_files():
    """finish() summary line contains elapsed time, node count, rel count, file count."""
    console, buf = _make_console()
    sp = ScanProgress(total=3, verbose=False, console=console)
    sp.start()
    sp.advance("a.ts", 10, 5)
    sp.advance("b.ts", 20, 8)
    sp.advance("c.ts", 15, 7)
    sp.finish(elapsed=4.2, total_nodes=45, total_rels=20)
    output = buf.getvalue()
    assert "4.2s" in output
    assert "45 nodes" in output
    assert "20 rels" in output
    assert "3 files" in output


# ── verbose-mode advance() ────────────────────────────────────────────────────

def test_verbose_advance_prints_detail_line():
    """In verbose mode, advance() prints a per-file detail line."""
    console, buf = _make_console()
    sp = ScanProgress(total=2, verbose=True, console=console)
    sp.start()
    sp.advance("src/auth.ts", 5, 3)
    output = buf.getvalue()
    assert "src/auth.ts" in output
    assert "5" in output
    assert "3" in output


def test_non_verbose_advance_prints_nothing():
    """In non-verbose mode, advance() does not print a detail line."""
    console, buf = _make_console()
    sp = ScanProgress(total=2, verbose=False, console=console)
    sp.start()
    sp.advance("src/auth.ts", 5, 3)
    output = buf.getvalue()
    # no per-file detail should appear (progress bar is transient, clears on stop)
    assert "src/auth.ts" not in output


# ── warning collection and finish() ──────────────────────────────────────────

def test_finish_with_warnings_prints_count_and_messages():
    """finish() prints warning count line and individual warning messages."""
    console, buf = _make_console()
    sp = ScanProgress(total=2, verbose=False, console=console)
    sp.start()
    sp.advance("a.ts", 5, 2)
    sp.add_warning("failed to parse b.ts — syntax error")
    sp.advance("b.ts", 0, 0)
    sp.finish(elapsed=1.0, total_nodes=5, total_rels=2)
    output = buf.getvalue()
    assert "1 warning" in output.lower() or "1 file" in output.lower()
    assert "failed to parse b.ts" in output


def test_finish_no_warnings_omits_warning_section():
    """finish() does not print any warning text when there are no warnings."""
    console, buf = _make_console()
    sp = ScanProgress(total=1, verbose=False, console=console)
    sp.start()
    sp.advance("a.ts", 5, 2)
    sp.finish(elapsed=0.5, total_nodes=5, total_rels=2)
    output = buf.getvalue()
    assert "warning" not in output.lower()
    assert "Warning" not in output


# ── single-file spinner mode ──────────────────────────────────────────────────

def test_single_file_finish_contains_summary():
    """ScanProgress(total=1): finish() summary contains elapsed, nodes, rels, files."""
    console, buf = _make_console()
    sp = ScanProgress(total=1, verbose=False, console=console)
    sp.start()
    sp.advance("src/app.ts", 8, 4)
    sp.finish(elapsed=0.3, total_nodes=8, total_rels=4)
    output = buf.getvalue()
    assert "0.3s" in output
    assert "8 nodes" in output
    assert "4 rels" in output
    assert "1 file" in output


# ── non-TTY output ────────────────────────────────────────────────────────────

def test_non_tty_output_has_no_ansi_escape_sequences():
    """With force_terminal=False, finish() output contains no ANSI escape sequences."""
    import re
    console, buf = _make_console()  # already uses force_terminal=False
    sp = ScanProgress(total=3, verbose=False, console=console)
    sp.start()
    sp.advance("a.ts", 5, 2)
    sp.advance("b.ts", 3, 1)
    sp.advance("c.ts", 2, 0)
    sp.finish(elapsed=1.0, total_nodes=10, total_rels=3)
    output = buf.getvalue()
    # No ANSI escape sequences (ESC [ ... m)
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    assert not ansi_escape.search(output), f"ANSI sequences found: {repr(output)}"

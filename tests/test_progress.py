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

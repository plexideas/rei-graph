from __future__ import annotations

from rich.console import Console
from rich.live import Live
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn
from rich.spinner import Spinner


class ScanProgress:
    """Rich-powered progress reporting for rei scan.

    All Rich-specific code lives here; callers use only stdlib types.
    Injectable console enables unit-test output capture.
    """

    def __init__(
        self,
        total: int,
        verbose: bool = False,
        console: Console | None = None,
    ) -> None:
        self._total = total
        self._verbose = verbose
        self._console = console or Console()
        self._warnings: list[str] = []
        self._file_count = 0
        self._progress: Progress | None = None
        self._task_id: int | None = None
        self._live: Live | None = None

    def start(self) -> None:
        """Begin the progress bar (multi-file) or spinner (single-file)."""
        if self._total > 1:
            self._progress = Progress(
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                BarColumn(),
                MofNCompleteColumn(),
                TextColumn("files"),
                console=self._console,
                transient=True,
            )
            self._progress.start()
            self._task_id = self._progress.add_task("scanning", total=self._total)
        else:
            self._live = Live(
                Spinner("dots", text="Scanning..."),
                console=self._console,
                transient=True,
            )
            self._live.start()

    def advance(self, file: str, nodes: int, rels: int) -> None:
        """Increment the progress bar by one file; print detail line in verbose mode."""
        self._file_count += 1
        if self._progress is not None and self._task_id is not None:
            self._progress.advance(self._task_id)
        if self._verbose:
            self._console.print(f"  {file}: {nodes} nodes, {rels} rels")

    def add_warning(self, msg: str) -> None:
        """Collect a warning to be shown after the summary line."""
        self._warnings.append(msg)

    def stop(self) -> None:
        """Stop progress display without printing a summary (for early exit / error paths)."""
        if self._progress is not None:
            self._progress.stop()
        if self._live is not None:
            self._live.stop()

    def finish(self, elapsed: float, total_nodes: int, total_rels: int) -> None:
        """Stop the bar/spinner and print the enriched summary, then any warnings."""
        self.stop()
        self._console.print(
            f"Done in {elapsed:.1f}s: {total_nodes} nodes, {total_rels} rels "
            f"from {self._file_count} files"
        )
        if self._warnings:
            self._console.print(f"{len(self._warnings)} warning(s):")
            for warning in self._warnings:
                self._console.print(f"  {warning}")

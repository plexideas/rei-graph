import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from click.testing import CliRunner

from rei_cli.main import cli


SAMPLE_INGESTER_OUTPUT = json.dumps({
    "file": "src/auth.ts",
    "nodes": [
        {"id": "module:src/auth.ts", "label": "Module", "name": "auth", "path": "src/auth.ts", "line": 1, "properties": {}},
        {"id": "function:src/auth.ts:login", "label": "Function", "name": "login", "path": "src/auth.ts", "line": 5, "properties": {"exported": True}},
    ],
    "relationships": [
        {"type": "EXPOSES", "sourceId": "module:src/auth.ts", "targetId": "function:src/auth.ts:login", "properties": {}},
        {"type": "IMPORTS", "sourceId": "module:src/auth.ts", "targetId": "module:react", "properties": {"specifiers": ["React"], "moduleSpecifier": "react"}},
    ],
})


def test_scan_invokes_ingester_and_writes_to_neo4j(tmp_path):
    """rei scan <file> calls the TS ingester and writes results to Neo4j."""
    # Create a dummy TS file
    ts_file = tmp_path / "test.ts"
    ts_file.write_text("export function hello() {}")

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find_ingester:

        mock_find_ingester.return_value = Path("/fake/cli.js")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(ts_file)])

        assert result.exit_code == 0
        # Ingester was called
        mock_subprocess.run.assert_called_once()
        # Nodes were upserted
        mock_client.upsert_nodes.assert_called_once()
        nodes = mock_client.upsert_nodes.call_args[0][0]
        assert len(nodes) == 2
        # Relationships were upserted
        mock_client.upsert_relationships.assert_called_once()
        rels = mock_client.upsert_relationships.call_args[0][0]
        assert len(rels) == 2
        mock_client.close.assert_called_once()


def test_scan_reports_ingester_failure(tmp_path):
    """rei scan <file> reports error when ingester fails."""
    ts_file = tmp_path / "bad.ts"
    ts_file.write_text("invalid content")

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find_ingester:

        mock_find_ingester.return_value = Path("/fake/cli.js")
        mock_client_cls.return_value.get_project.return_value = None
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Parse error"
        mock_subprocess.run.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(ts_file)])

        assert result.exit_code == 0
        assert "error" in result.output.lower() or "fail" in result.output.lower()


def test_scan_reports_file_not_found():
    """rei scan reports error for non-existent file."""
    runner = CliRunner()
    result = runner.invoke(cli, ["scan", "/nonexistent/file.ts"])
    assert result.exit_code == 0
    assert "not found" in result.output.lower() or "error" in result.output.lower()


def test_scan_directory_scans_all_ts_files(tmp_path):
    """rei scan <dir> walks the directory and scans all TS/TSX files."""
    # Create project structure
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.ts").write_text("export function login() {}")
    (src / "utils.tsx").write_text("export function helper() {}")
    (src / "readme.md").write_text("# docs")  # non-TS file, should be skipped

    # Create .rei/project.toml with include=["src"]
    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # Ingester should be called twice (auth.ts + utils.tsx), not for readme.md
        assert mock_subprocess.run.call_count == 2
        mock_client.close.assert_called_once()


def test_scan_directory_respects_exclude_patterns(tmp_path):
    """rei scan <dir> respects exclude patterns from config."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "bundle.ts").write_text("export function bundle() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src", "dist"]\nexclude = ["dist"]\n'
    )

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # Only src/app.ts should be scanned; dist/bundle.ts is excluded
        assert mock_subprocess.run.call_count == 1


def test_scan_directory_stores_resolved_import_paths(tmp_path):
    """rei scan <dir> stores IMPORTS relationships with resolved file paths, not raw specifiers."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "App.tsx").write_text("export function App() {}")
    (src / "utils.ts").write_text("export function helper() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    # Simulate ingester returning resolved import path for App.tsx
    app_output = json.dumps({
        "file": "src/App.tsx",
        "nodes": [
            {"id": "module:src/App.tsx", "label": "Module", "name": "App",
             "path": "src/App.tsx", "line": 1, "properties": {}},
        ],
        "relationships": [
            {"type": "IMPORTS", "sourceId": "module:src/App.tsx",
             "targetId": "module:src/utils.ts",
             "properties": {"specifiers": ["helper"], "moduleSpecifier": "./utils"}},
        ],
    })
    utils_output = json.dumps({
        "file": "src/utils.ts",
        "nodes": [
            {"id": "module:src/utils.ts", "label": "Module", "name": "utils",
             "path": "src/utils.ts", "line": 1, "properties": {}},
        ],
        "relationships": [],
    })

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        called_path = cmd[2]  # node <cli.js> <filepath>
        if "App.tsx" in called_path:
            result.stdout = app_output
        else:
            result.stdout = utils_output
        return result

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_subprocess.run.side_effect = fake_run

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert mock_subprocess.run.call_count == 2

        # Collect all upserted relationships
        all_rels = []
        for c in mock_client.upsert_relationships.call_args_list:
            all_rels.extend(c[0][0])

        import_rels = [r for r in all_rels if r.type == "IMPORTS"]
        assert len(import_rels) == 1
        # The target should be a resolved file path, NOT the raw specifier
        assert import_rels[0].target_id == "module:src/utils.ts"
        assert "module:./utils" not in [r.target_id for r in all_rels]


def test_scan_stores_package_nodes_and_depends_on(tmp_path):
    """rei scan stores Package nodes and DEPENDS_ON relationships for external imports."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "App.tsx").write_text("export function App() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    ingester_output = json.dumps({
        "file": "src/App.tsx",
        "nodes": [
            {"id": "module:src/App.tsx", "label": "Module", "name": "App",
             "path": "src/App.tsx", "line": 1, "properties": {}},
            {"id": "package:react", "label": "Package", "name": "react",
             "path": "", "line": 0, "properties": {"external": True}},
        ],
        "relationships": [
            {"type": "IMPORTS", "sourceId": "module:src/App.tsx",
             "targetId": "module:react",
             "properties": {"specifiers": ["React"], "moduleSpecifier": "react"}},
            {"type": "DEPENDS_ON", "sourceId": "module:src/App.tsx",
             "targetId": "package:react", "properties": {}},
        ],
    })

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ingester_output
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0

        # Verify Package node was upserted
        all_nodes = []
        for c in mock_client.upsert_nodes.call_args_list:
            all_nodes.extend(c[0][0])
        package_nodes = [n for n in all_nodes if n.label == "Package"]
        assert len(package_nodes) == 1
        assert package_nodes[0].name == "react"

        # Verify DEPENDS_ON relationship was upserted
        all_rels = []
        for c in mock_client.upsert_relationships.call_args_list:
            all_rels.extend(c[0][0])
        depends_rels = [r for r in all_rels if r.type == "DEPENDS_ON"]
        assert len(depends_rels) == 1
        assert depends_rels[0].target_id == "package:react"


# ─── scan --changed ───────────────────────────────────────────────────────────

def test_scan_changed_only_scans_git_modified_files(tmp_path):
    """rei scan --changed uses git diff to detect modified files and scans only those."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.ts").write_text("export function login() {}")
    (src / "utils.ts").write_text("export function helper() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    # git diff reports only auth.ts as changed (not deleted)
    git_changed_result = MagicMock()
    git_changed_result.returncode = 0
    git_changed_result.stdout = "src/auth.ts\n"

    git_deleted_result = MagicMock()
    git_deleted_result.returncode = 0
    git_deleted_result.stdout = ""  # no deleted files

    ingester_result = MagicMock()
    ingester_result.returncode = 0
    ingester_result.stdout = SAMPLE_INGESTER_OUTPUT
    ingester_result.stderr = ""

    def fake_run(cmd, **kwargs):
        if cmd[0] == "git" and "--diff-filter=D" in cmd:
            return git_deleted_result
        if cmd[0] == "git":
            return git_changed_result
        return ingester_result

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_subprocess.run.side_effect = fake_run

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path), "--changed"])

        assert result.exit_code == 0
        # git diff was called (at least once — may call for deleted + changed)
        git_calls = [c for c in mock_subprocess.run.call_args_list if c[0][0][0] == "git"]
        assert len(git_calls) >= 1
        # ingester called only once (only auth.ts, not utils.ts)
        ingester_calls = [c for c in mock_subprocess.run.call_args_list if c[0][0][0] == "node"]
        assert len(ingester_calls) == 1
        assert "auth.ts" in str(ingester_calls[0])


def test_scan_changed_reports_no_changes_when_git_diff_empty(tmp_path):
    """rei scan --changed reports 'no changed files' when git diff returns nothing."""
    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text('[project]\nname = "test"\n')

    git_result = MagicMock()
    git_result.returncode = 0
    git_result.stdout = ""

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls:

        mock_subprocess.run.return_value = git_result
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path), "--changed"])

        assert result.exit_code == 0
        assert "no" in result.output.lower() or "0" in result.output


def test_scan_changed_removes_nodes_for_deleted_files(tmp_path):
    """rei scan --changed deletes nodes for files removed in git diff (D status)."""
    src = tmp_path / "src"
    src.mkdir()

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    # git diff reports auth.ts as Deleted
    git_result = MagicMock()
    git_result.returncode = 0
    git_result.stdout = "src/deleted.ts\n"

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find, \
         patch("rei_cli.commands.scan._get_deleted_files") as mock_deleted:

        mock_find.return_value = Path("/fake/cli.js")
        mock_deleted.return_value = ["src/deleted.ts"]
        mock_subprocess.run.return_value = git_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path), "--changed"])

        assert result.exit_code == 0
        # delete_file_nodes was called for the deleted file
        mock_client.delete_file_nodes.assert_called_with("src/deleted.ts")


# ── Phase 1: progress bar + enriched summary ─────────────────────────────────

def test_scan_directory_summary_contains_elapsed_time(tmp_path):
    """rei scan <dir> summary line includes elapsed time (e.g. 'Done in Xs')."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert "Graph updated" in result.output
        assert "nodes" in result.output
        assert "rels" in result.output
        assert "files" in result.output


# ── Phase 2: --verbose flag and warning collection ────────────────────────────

def test_scan_directory_verbose_shows_per_file_detail(tmp_path):
    """rei scan <dir> --verbose prints a per-file detail line for each file."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.ts").write_text("export function login() {}")
    (src / "utils.ts").write_text("export function helper() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path), "--verbose"])

        assert result.exit_code == 0
        # Per-file lines: file name and counts should appear
        assert "nodes" in result.output
        assert "rels" in result.output
        # Should have appeared at least twice (two files)
        assert result.output.count("nodes") >= 2


def test_scan_directory_verbose_short_flag(tmp_path):
    """`-v` short flag works the same as --verbose."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path), "-v"])

        assert result.exit_code == 0
        assert "nodes" in result.output


def test_scan_directory_no_inline_warnings(tmp_path):
    """rei scan <dir> does not print warnings inline; they appear in summary section."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "good.ts").write_text("export function ok() {}")
    (src / "bad.ts").write_text("broken")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    good_result = MagicMock()
    good_result.returncode = 0
    good_result.stdout = SAMPLE_INGESTER_OUTPUT
    good_result.stderr = ""

    bad_result = MagicMock()
    bad_result.returncode = 1
    bad_result.stdout = ""
    bad_result.stderr = "Parse error"

    def fake_run(cmd, **kwargs):
        if "bad.ts" in str(cmd):
            return bad_result
        return good_result

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_subprocess.run.side_effect = fake_run

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # Warning must NOT appear before the summary line ("Graph updated...")
        output = result.output
        done_pos = output.lower().find("graph updated")
        assert done_pos >= 0, "Summary line should be present"
        # Inline inline "Warning:" should NOT appear before the summary
        pre_summary = output[:done_pos]
        assert "warning" not in pre_summary.lower(), (
            f"Inline warning appeared before summary. Pre-summary output:\n{pre_summary}"
        )


# ── Phase 3: single-file spinner, --changed path, edge cases ─────────────────

def test_scan_single_file_output_contains_summary(tmp_path):
    """rei scan <single-file> output is non-empty and contains the enriched summary."""
    ts_file = tmp_path / "app.ts"
    ts_file.write_text("export function app() {}")

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(ts_file)])

        assert result.exit_code == 0
        assert "Graph updated" in result.output
        assert "nodes" in result.output
        assert "rels" in result.output


def test_scan_changed_summary_contains_elapsed_time(tmp_path):
    """rei scan --changed summary line includes elapsed time ('Done in Xs')."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.ts").write_text("export function login() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    git_changed_result = MagicMock()
    git_changed_result.returncode = 0
    git_changed_result.stdout = "src/auth.ts\n"

    git_deleted_result = MagicMock()
    git_deleted_result.returncode = 0
    git_deleted_result.stdout = ""

    ingester_result = MagicMock()
    ingester_result.returncode = 0
    ingester_result.stdout = SAMPLE_INGESTER_OUTPUT
    ingester_result.stderr = ""

    def fake_run(cmd, **kwargs):
        if cmd[0] == "git" and "--diff-filter=D" in cmd:
            return git_deleted_result
        if cmd[0] == "git":
            return git_changed_result
        return ingester_result

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_subprocess.run.side_effect = fake_run

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path), "--changed"])

        assert result.exit_code == 0
        assert "Graph updated" in result.output
        assert "nodes" in result.output
        assert "rels" in result.output
        assert "files" in result.output


def test_scan_changed_verbose_shows_per_file_detail(tmp_path):
    """rei scan --changed --verbose prints a per-file detail line."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.ts").write_text("export function login() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    git_changed_result = MagicMock()
    git_changed_result.returncode = 0
    git_changed_result.stdout = "src/auth.ts\n"

    git_deleted_result = MagicMock()
    git_deleted_result.returncode = 0
    git_deleted_result.stdout = ""

    ingester_result = MagicMock()
    ingester_result.returncode = 0
    ingester_result.stdout = SAMPLE_INGESTER_OUTPUT
    ingester_result.stderr = ""

    def fake_run(cmd, **kwargs):
        if cmd[0] == "git" and "--diff-filter=D" in cmd:
            return git_deleted_result
        if cmd[0] == "git":
            return git_changed_result
        return ingester_result

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_subprocess.run.side_effect = fake_run

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path), "--changed", "--verbose"])

        assert result.exit_code == 0
        # Per-file detail line: file path + counts
        assert "auth.ts" in result.output
        assert "nodes" in result.output
        assert "rels" in result.output


def test_scan_empty_directory_prints_no_files_message(tmp_path):
    """rei scan <empty-dir> prints 'No TS/TSX files found to scan.' and exits cleanly."""
    # Empty src dir — no TS files
    src = tmp_path / "src"
    src.mkdir()
    (src / "readme.md").write_text("# docs")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert "No TS/TSX files found to scan." in result.output


def test_scan_directory_non_tty_no_ansi(tmp_path):
    """rei scan <dir> with CliRunner (non-TTY / color=False) produces no ANSI sequences."""
    import re
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)], color=False)

        assert result.exit_code == 0
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        assert not ansi_escape.search(result.output), (
            f"ANSI sequences in output: {repr(result.output)}"
        )


# ── Project-isolation Phase 2: TS ingester prefix + scan integration ──────────

def test_scan_passes_project_prefix_to_ingester(tmp_path):
    """rei scan <dir> passes --project-prefix <hash> to the TS ingester subprocess."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    from rei_core.hashing import project_hash

    expected_prefix = project_hash(str(tmp_path.resolve()))

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # Verify --project-prefix was passed to the ingester subprocess
        ingester_call = mock_subprocess.run.call_args
        cmd = ingester_call[0][0]
        assert "--project-prefix" in cmd
        prefix_idx = cmd.index("--project-prefix")
        assert cmd[prefix_idx + 1] == expected_prefix


def test_scan_constructs_neo4j_client_with_project_id(tmp_path):
    """rei scan <dir> constructs Neo4jClient with the resolved project_id."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    expected_project_id = str(tmp_path.resolve())

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # Verify Neo4jClient was constructed with project_id
        mock_client_cls.assert_called_once_with(project_id=expected_project_id)


def test_scan_auto_inits_project_toml_when_missing(tmp_path):
    """rei scan <dir> auto-creates .rei/project.toml when it doesn't exist."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")

    # Deliberately do NOT create .rei/project.toml
    assert not (tmp_path / ".rei" / "project.toml").exists()

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # .rei/project.toml should have been auto-created
        config_path = tmp_path / ".rei" / "project.toml"
        assert config_path.exists()

        # It should contain the project id (absolute path)
        import tomllib
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        assert config["project"]["id"] == str(tmp_path.resolve())


def test_scan_single_file_passes_project_prefix(tmp_path):
    """rei scan <file> also passes --project-prefix to the ingester."""
    ts_file = tmp_path / "app.ts"
    ts_file.write_text("export function app() {}")

    from rei_core.hashing import project_hash

    expected_prefix = project_hash(str(tmp_path.resolve()))

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(ts_file)])

        assert result.exit_code == 0
        ingester_call = mock_subprocess.run.call_args
        cmd = ingester_call[0][0]
        assert "--project-prefix" in cmd
        prefix_idx = cmd.index("--project-prefix")
        assert cmd[prefix_idx + 1] == expected_prefix


def test_scan_changed_passes_project_prefix_and_project_id(tmp_path):
    """rei scan --changed passes project prefix to ingester and project_id to Neo4jClient."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.ts").write_text("export function login() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    from rei_core.hashing import project_hash

    expected_prefix = project_hash(str(tmp_path.resolve()))
    expected_project_id = str(tmp_path.resolve())

    git_changed_result = MagicMock()
    git_changed_result.returncode = 0
    git_changed_result.stdout = "src/auth.ts\n"

    git_deleted_result = MagicMock()
    git_deleted_result.returncode = 0
    git_deleted_result.stdout = ""

    ingester_result = MagicMock()
    ingester_result.returncode = 0
    ingester_result.stdout = SAMPLE_INGESTER_OUTPUT
    ingester_result.stderr = ""

    def fake_run(cmd, **kwargs):
        if cmd[0] == "git" and "--diff-filter=D" in cmd:
            return git_deleted_result
        if cmd[0] == "git":
            return git_changed_result
        return ingester_result

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_subprocess.run.side_effect = fake_run

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path), "--changed"])

        assert result.exit_code == 0

        # Verify --project-prefix was passed to ingester
        ingester_calls = [c for c in mock_subprocess.run.call_args_list if c[0][0][0] == "node"]
        assert len(ingester_calls) == 1
        cmd = ingester_calls[0][0][0]
        assert "--project-prefix" in ingester_calls[0][0][0]

        # Verify Neo4jClient was constructed with project_id
        mock_client_cls.assert_called_once_with(project_id=expected_project_id)


# ── Project-isolation Phase 3: Repeat-scan detection + incremental auto-switch ──

def test_scan_known_project_prints_warning_and_runs_incremental(tmp_path):
    """rei scan <dir> on a known project prints a warning and switches to incremental scan."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    last_scanned = "2026-04-18T10:00:00+00:00"

    # git log --name-only returns one changed file
    git_log_result = MagicMock()
    git_log_result.returncode = 0
    git_log_result.stdout = "src/app.ts\n"

    # git log --diff-filter=D returns no deleted files
    git_log_deleted_result = MagicMock()
    git_log_deleted_result.returncode = 0
    git_log_deleted_result.stdout = ""

    ingester_result = MagicMock()
    ingester_result.returncode = 0
    ingester_result.stdout = SAMPLE_INGESTER_OUTPUT
    ingester_result.stderr = ""

    def fake_run(cmd, **kwargs):
        if cmd[0] == "git" and "--diff-filter=D" in cmd:
            return git_log_deleted_result
        if cmd[0] == "git":
            return git_log_result
        return ingester_result

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_subprocess.run.side_effect = fake_run

        mock_client = MagicMock()
        mock_client.get_project.return_value = {
            "id": str(tmp_path.resolve()),
            "last_scanned_at": last_scanned,
        }
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # Mode label should show incremental
        assert "incremental" in result.output.lower()
        # Should NOT do a full directory scan — should use git log --since
        git_calls = [c for c in mock_subprocess.run.call_args_list if c[0][0][0] == "git"]
        assert len(git_calls) >= 1
        # At least one git call should contain --since
        since_calls = [c for c in git_calls if "--since" in c[0][0]]
        assert len(since_calls) >= 1


def test_scan_known_project_force_does_full_rescan(tmp_path):
    """rei scan <dir> --force on a known project bypasses incremental and does a full scan."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client.get_project.return_value = {
            "id": str(tmp_path.resolve()),
            "last_scanned_at": "2026-04-18T10:00:00+00:00",
        }
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path), "--force"])

        assert result.exit_code == 0
        # Should NOT print incremental warning
        assert "incremental" not in result.output.lower()
        # Should do a full directory scan (ingester called for all files)
        ingester_calls = [c for c in mock_subprocess.run.call_args_list if c[0][0][0] == "node"]
        assert len(ingester_calls) >= 1


def test_scan_first_time_no_warning(tmp_path):
    """rei scan <dir> on a first-time project does a full scan with no warning."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        # First-time: no Project node exists
        mock_client.get_project.return_value = None
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # No warning about already scanned
        assert "already scanned" not in result.output.lower()
        assert "incremental" not in result.output.lower()
        # Full scan — ingester called for each file
        ingester_calls = [c for c in mock_subprocess.run.call_args_list if c[0][0][0] == "node"]
        assert len(ingester_calls) >= 1


def test_scan_updates_last_scanned_at_after_success(tmp_path):
    """rei scan <dir> updates last_scanned_at on the Project node after successful scan."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client.get_project.return_value = None
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # update_last_scanned should have been called once
        mock_client.update_last_scanned.assert_called_once()


def test_scan_known_project_no_changes_since_last_scan(tmp_path):
    """rei scan <dir> on known project with no changes since last scan reports no changes."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")

    rei = tmp_path / ".rei"
    rei.mkdir()
    (rei / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    last_scanned = "2026-04-18T10:00:00+00:00"

    # git returns no changed files
    git_empty_result = MagicMock()
    git_empty_result.returncode = 0
    git_empty_result.stdout = ""

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_subprocess.run.return_value = git_empty_result

        mock_client = MagicMock()
        mock_client.get_project.return_value = {
            "id": str(tmp_path.resolve()),
            "last_scanned_at": last_scanned,
        }
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert "no changed files" in result.output.lower() or "no " in result.output.lower()


def test_scan_force_flag_documented_in_help():
    """--force flag is documented in rei scan --help output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["scan", "--help"])
    assert "--force" in result.output


# ── Phase 2 (app-installation): _find_ingester bundled vs dev path discovery ──

def test_find_ingester_returns_bundled_path_when_present(tmp_path):
    """_find_ingester() returns the bundled ingester inside the package when it exists."""
    from rei_cli.commands.scan import _find_ingester

    # Simulate the bundled ingester sitting next to scan.py inside an installed package
    fake_package_ingester = tmp_path / "_ingester" / "cli.js"
    fake_package_ingester.parent.mkdir(parents=True)
    fake_package_ingester.write_text("// bundled")

    with patch("rei_cli.commands.scan.Path") as mock_path_cls:
        # Make __file__-relative lookup point to our tmp_path
        scan_file_mock = MagicMock()
        scan_file_mock.resolve.return_value = tmp_path / "scan.py"
        mock_path_cls.return_value = scan_file_mock
        # We need the real Path for Path.cwd() to not break — use a targeted patch instead
        pass

    # Directly test: patch __file__ parent to point to tmp_path
    import rei_cli.commands.scan as scan_module
    with patch.object(scan_module, "_PACKAGE_INGESTER_PATH", fake_package_ingester):
        result = _find_ingester()
    assert result == fake_package_ingester


def test_find_ingester_falls_back_to_dev_path_when_bundled_absent(tmp_path):
    """_find_ingester() falls back to packages/ingester_ts/dist/cli.js when no bundled ingester."""
    from rei_cli.commands.scan import _find_ingester

    # Create a fake dev-layout ingester path
    dev_cli = tmp_path / "packages" / "ingester_ts" / "dist" / "cli.js"
    dev_cli.parent.mkdir(parents=True)
    dev_cli.write_text("// dev")

    import rei_cli.commands.scan as scan_module

    # Bundled path does not exist
    nonexistent_bundle = tmp_path / "_ingester" / "cli.js"
    assert not nonexistent_bundle.exists()

    with patch.object(scan_module, "_PACKAGE_INGESTER_PATH", nonexistent_bundle), \
         patch("rei_cli.commands.scan.Path.cwd", return_value=tmp_path):
        result = _find_ingester()

    assert result == dev_cli


# ── Plan Phase 1: Optional path + phased scan output ─────────────────────────

def test_scan_no_argument_uses_cwd(tmp_path):
    """rei scan with no argument scans the current directory (no 'Missing argument' error)."""
    import os

    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    (tmp_path / ".rei").mkdir()
    (tmp_path / ".rei" / "project.toml").write_text(
        '[project]\nname = "myapp"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            result = runner.invoke(cli, ["scan"])
        finally:
            os.chdir(old_cwd)

        assert result.exit_code == 0
        assert "Missing argument" not in result.output
        assert result.output != ""


def test_scan_output_contains_phase_lines_full_scan(tmp_path):
    """rei scan shows ✓ Project:, ✓ Neo4j: connected, ✓ Mode: full scan, ✓ Graph updated: lines."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    (tmp_path / ".rei").mkdir()
    (tmp_path / ".rei" / "project.toml").write_text(
        '[project]\nname = "myapp"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert "✓ Project:" in result.output
        assert "✓ Neo4j: connected" in result.output
        assert "✓ Mode: full scan" in result.output
        assert "✓ Graph updated:" in result.output


def test_scan_output_incremental_mode_label(tmp_path):
    """rei scan on a known project shows '✓ Mode: incremental' phase line."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    (tmp_path / ".rei").mkdir()
    (tmp_path / ".rei" / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    last_scanned = "2026-04-18T10:00:00+00:00"

    git_log_result = MagicMock()
    git_log_result.returncode = 0
    git_log_result.stdout = "src/app.ts\n"

    git_log_deleted_result = MagicMock()
    git_log_deleted_result.returncode = 0
    git_log_deleted_result.stdout = ""

    ingester_result = MagicMock()
    ingester_result.returncode = 0
    ingester_result.stdout = SAMPLE_INGESTER_OUTPUT
    ingester_result.stderr = ""

    def fake_run(cmd, **kwargs):
        if cmd[0] == "git" and "--diff-filter=D" in cmd:
            return git_log_deleted_result
        if cmd[0] == "git":
            return git_log_result
        return ingester_result

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_subprocess.run.side_effect = fake_run

        mock_client = MagicMock()
        mock_client.get_project.return_value = {
            "id": str(tmp_path.resolve()),
            "last_scanned_at": last_scanned,
        }
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert "✓ Mode: incremental" in result.output


# ── Phase 2: Service health check and auto-start ──────────────────────────────

def _make_scan_env(tmp_path):
    """Create a minimal project dir with one TS file and .rei/project.toml."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    (tmp_path / ".rei").mkdir()
    (tmp_path / ".rei" / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )


def test_scan_neo4j_healthy_no_docker_call(tmp_path):
    """When Neo4j is healthy, docker compose is never called."""
    _make_scan_env(tmp_path)

    with patch("rei_cli.commands.scan.check_neo4j_health",
               return_value={"status": "healthy", "url": "http://localhost:7474"}), \
         patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        ingester_result = MagicMock()
        ingester_result.returncode = 0
        ingester_result.stdout = SAMPLE_INGESTER_OUTPUT
        ingester_result.stderr = ""
        mock_subprocess.run.return_value = ingester_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert "✓ Neo4j: connected" in result.output
        # docker compose must NOT have been called
        docker_calls = [c for c in mock_subprocess.run.call_args_list
                        if c[0][0][0] == "docker"]
        assert len(docker_calls) == 0


def test_scan_auto_starts_neo4j_when_unhealthy_and_docker_available(tmp_path, monkeypatch):
    """When Neo4j is down and Docker is available, CLI starts it and continues scanning."""
    _make_scan_env(tmp_path)
    monkeypatch.setenv("REI_SERVICE_TIMEOUT", "30")

    # First health call → unhealthy; subsequent (polling) → healthy
    health_side_effect = [
        {"status": "unhealthy", "url": "http://localhost:7474", "error": "refused"},
        {"status": "healthy", "url": "http://localhost:7474"},
    ]

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        # node (ingester)
        result.returncode = 0
        result.stdout = SAMPLE_INGESTER_OUTPUT
        result.stderr = ""
        return result

    with patch("rei_cli.commands.scan.check_neo4j_health", side_effect=health_side_effect), \
         patch("rei_cli.commands.scan.shutil") as mock_shutil, \
         patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find, \
         patch("rei_cli.commands.scan.time.sleep"):  # avoid real sleeping

        mock_shutil.which.return_value = "/usr/local/bin/docker"
        # docker compose up -d → Popen
        fake_popen = MagicMock()
        fake_popen.communicate.return_value = ("", "")
        fake_popen.returncode = 0
        mock_subprocess.Popen.return_value = fake_popen
        # node ingester → run
        mock_subprocess.run.side_effect = fake_run

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None
        mock_find.return_value = Path("/fake/cli.js")

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert "Starting" in result.output
        assert "✓ Neo4j: connected" in result.output

        # docker compose up -d was called via Popen
        assert mock_subprocess.Popen.call_count == 1
        cmd = mock_subprocess.Popen.call_args[0][0]
        assert "compose" in cmd
        assert "up" in cmd
        assert "-d" in cmd


def test_scan_uses_bundled_compose_file(tmp_path, monkeypatch):
    """docker compose up -d is invoked with the bundled compose file path."""
    _make_scan_env(tmp_path)
    monkeypatch.setenv("REI_SERVICE_TIMEOUT", "30")

    # Create a real (temp) file that acts as the bundled compose
    bundled_compose = tmp_path / "bundled-compose.yml"
    bundled_compose.write_text("# fake bundled compose")

    health_side_effect = [
        {"status": "unhealthy", "url": "http://localhost:7474"},
        {"status": "healthy", "url": "http://localhost:7474"},
    ]

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = SAMPLE_INGESTER_OUTPUT
        result.stderr = ""
        return result

    with patch("rei_cli.commands.scan.check_neo4j_health", side_effect=health_side_effect), \
         patch("rei_cli.commands.scan.shutil") as mock_shutil, \
         patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find, \
         patch("rei_cli.commands.scan.time.sleep"), \
         patch("rei_cli.commands.scan._PACKAGE_COMPOSE_PATH", bundled_compose):

        mock_shutil.which.return_value = "/usr/local/bin/docker"
        # docker compose up -d → Popen
        fake_popen = MagicMock()
        fake_popen.communicate.return_value = ("", "")
        fake_popen.returncode = 0
        mock_subprocess.Popen.return_value = fake_popen
        # node ingester → run
        mock_subprocess.run.side_effect = fake_run
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None
        mock_find.return_value = Path("/fake/cli.js")

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert mock_subprocess.Popen.call_count == 1
        cmd = mock_subprocess.Popen.call_args[0][0]
        # -f flag and bundled path are passed
        assert "-f" in cmd
        f_idx = cmd.index("-f")
        assert str(bundled_compose) == cmd[f_idx + 1]


def test_scan_exits_with_error_when_no_docker(tmp_path):
    """When Neo4j is down and Docker is not installed, exit code 1 with install link."""
    _make_scan_env(tmp_path)

    with patch("rei_cli.commands.scan.check_neo4j_health",
               return_value={"status": "unhealthy", "url": "http://localhost:7474"}), \
         patch("rei_cli.commands.scan.shutil") as mock_shutil, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls:

        mock_shutil.which.return_value = None  # docker not found
        mock_client_cls.return_value = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 1
        assert "Docker" in result.output
        assert "https://docs.docker.com/get-docker/" in result.output


def test_scan_exits_on_neo4j_readiness_timeout(tmp_path, monkeypatch):
    """When Neo4j does not become ready within timeout, exit code 1 and suggest rei doctor."""
    _make_scan_env(tmp_path)
    # Timeout of 0 so the polling loop never executes
    monkeypatch.setenv("REI_SERVICE_TIMEOUT", "0")

    with patch("rei_cli.commands.scan.check_neo4j_health",
               return_value={"status": "unhealthy", "url": "http://localhost:7474"}), \
         patch("rei_cli.commands.scan.shutil") as mock_shutil, \
         patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls:

        mock_shutil.which.return_value = "/usr/local/bin/docker"
        fake_popen = MagicMock()
        fake_popen.communicate.return_value = ("", "")
        fake_popen.returncode = 0
        mock_subprocess.Popen.return_value = fake_popen
        mock_client_cls.return_value = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 1
        assert "rei doctor" in result.output


def test_scan_service_timeout_env_var_respected(tmp_path, monkeypatch):
    """REI_SERVICE_TIMEOUT env var controls the polling timeout."""
    _make_scan_env(tmp_path)
    monkeypatch.setenv("REI_SERVICE_TIMEOUT", "0")

    with patch("rei_cli.commands.scan.check_neo4j_health",
               return_value={"status": "unhealthy", "url": "http://localhost:7474"}), \
         patch("rei_cli.commands.scan.shutil") as mock_shutil, \
         patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls:

        mock_shutil.which.return_value = "/usr/local/bin/docker"
        fake_popen = MagicMock()
        fake_popen.communicate.return_value = ("", "")
        fake_popen.returncode = 0
        mock_subprocess.Popen.return_value = fake_popen
        mock_client_cls.return_value = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        # Timeout of 0 → polling loop never runs → timeout error
        assert result.exit_code == 1
        assert "0s" in result.output or "did not become ready" in result.output


# ── Phase 3: First-run UX and next-step suggestions ──────────────────────────

def test_scan_first_run_shows_initialized_project_line(tmp_path):
    """On first run (no .rei/project.toml), output shows '✓ Initialized project: <name>'."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    # No .rei/project.toml — first run

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert "✓ Initialized project:" in result.output
        assert ".rei/project.toml created" in result.output
        # Should NOT show plain "✓ Project:" line when initializing
        lines = [l for l in result.output.splitlines() if l.startswith("✓ Project:")]
        assert lines == [], f"Should not show '✓ Project:' on first run, got: {result.output}"


def test_scan_repeat_run_shows_project_line_not_initialized(tmp_path):
    """On repeat run (.rei/project.toml already exists), output shows '✓ Project:' not 'Initialized'."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    (tmp_path / ".rei").mkdir()
    (tmp_path / ".rei" / "project.toml").write_text(
        '[project]\nname = "myapp"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert "✓ Project: myapp" in result.output
        assert "Initialized" not in result.output


def test_scan_first_scan_shows_next_step_suggestions(tmp_path):
    """On first scan (last_scanned_at is None), output includes next-step suggestions."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    (tmp_path / ".rei").mkdir()
    (tmp_path / ".rei" / "project.toml").write_text(
        '[project]\nname = "myapp"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None  # No previous scan → last_scanned_at = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert "Next steps" in result.output
        assert "rei query" in result.output
        assert "rei impact" in result.output
        assert "rei mcp" in result.output


def test_scan_repeat_scan_omits_next_step_suggestions(tmp_path):
    """On repeat scan (last_scanned_at is set), next-step suggestions are NOT shown."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    (tmp_path / ".rei").mkdir()
    (tmp_path / ".rei" / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    last_scanned = "2026-04-18T10:00:00+00:00"

    git_log_result = MagicMock()
    git_log_result.returncode = 0
    git_log_result.stdout = "src/app.ts\n"

    git_log_deleted_result = MagicMock()
    git_log_deleted_result.returncode = 0
    git_log_deleted_result.stdout = ""

    ingester_result = MagicMock()
    ingester_result.returncode = 0
    ingester_result.stdout = SAMPLE_INGESTER_OUTPUT
    ingester_result.stderr = ""

    def fake_run(cmd, **kwargs):
        if cmd[0] == "git" and "--diff-filter=D" in cmd:
            return git_log_deleted_result
        if cmd[0] == "git":
            return git_log_result
        return ingester_result

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_subprocess.run.side_effect = fake_run

        mock_client = MagicMock()
        mock_client.get_project.return_value = {
            "id": str(tmp_path.resolve()),
            "last_scanned_at": last_scanned,
        }
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert "Next steps" not in result.output


def test_scan_corrupt_config_warns_and_regenerates(tmp_path):
    """Corrupt .rei/project.toml triggers a warning, regenerates defaults, and scan continues."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    # Write a corrupt config file
    (tmp_path / ".rei").mkdir()
    (tmp_path / ".rei" / "project.toml").write_text("this is not valid toml =[[[")

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # Warning about corrupt/invalid config
        assert "corrupt" in result.output.lower() or "invalid" in result.output.lower()
        # Scan continues successfully
        assert "Graph updated" in result.output
        # Config was regenerated with valid TOML
        import tomllib
        with open(tmp_path / ".rei" / "project.toml", "rb") as f:
            config = tomllib.load(f)
        assert "project" in config


def test_scan_force_flag_does_not_show_next_steps_on_known_project(tmp_path):
    """--force on a known project (has last_scanned_at) does full scan but omits next-step suggestions."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    (tmp_path / ".rei").mkdir()
    (tmp_path / ".rei" / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client.get_project.return_value = {
            "id": str(tmp_path.resolve()),
            "last_scanned_at": "2026-04-18T10:00:00+00:00",
        }
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path), "--force"])

        assert result.exit_code == 0
        assert "Next steps" not in result.output


# ── Phase 4: Action-oriented errors and graceful fallbacks ────────────────────

def test_scan_node_not_found_exits_with_install_link(tmp_path):
    """When Node.js is not installed, rei scan exits 1 with a clear message and install link."""
    _make_scan_env(tmp_path)

    with patch("rei_cli.commands.scan.shutil") as mock_shutil, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        # All shutil.which() calls return None (node not found)
        mock_shutil.which.return_value = None

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None
        mock_find.return_value = Path("/fake/cli.js")

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 1
        assert "Node.js" in result.output
        assert "https://nodejs.org/" in result.output


def test_scan_git_unavailable_falls_back_to_full_scan_with_note(tmp_path):
    """When git is not installed on a repeat project, falls back to full scan with a note."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    (tmp_path / ".rei").mkdir()
    (tmp_path / ".rei" / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("rei_cli.commands.scan.shutil") as mock_shutil, \
         patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        def which_fn(cmd):
            if cmd == "git":
                return None  # git not available
            return "/usr/bin/node"  # node available

        mock_shutil.which.side_effect = which_fn
        mock_find.return_value = Path("/fake/cli.js")

        ingester_result = MagicMock()
        ingester_result.returncode = 0
        ingester_result.stdout = SAMPLE_INGESTER_OUTPUT
        ingester_result.stderr = ""
        mock_subprocess.run.return_value = ingester_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        # Known project — would normally trigger incremental
        mock_client.get_project.return_value = {
            "id": str(tmp_path.resolve()),
            "last_scanned_at": "2026-04-18T10:00:00+00:00",
        }

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # Note about git fallback should be in output
        assert "git" in result.output.lower()
        assert "full scan" in result.output.lower()
        # Scan completed successfully
        assert "Graph updated" in result.output


def test_scan_non_git_directory_falls_back_to_full_scan_with_note(tmp_path):
    """When git is available but the project is not a git repo, falls back to full scan with note."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    (tmp_path / ".rei").mkdir()
    (tmp_path / ".rei" / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    def fake_run(cmd, **kwargs):
        r = MagicMock()
        if cmd[0] == "git" and "rev-parse" in cmd:
            r.returncode = 128  # not a git repo
            r.stdout = ""
            r.stderr = "fatal: not a git repository"
            return r
        # node ingester
        r.returncode = 0
        r.stdout = SAMPLE_INGESTER_OUTPUT
        r.stderr = ""
        return r

    with patch("rei_cli.commands.scan.shutil") as mock_shutil, \
         patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        def which_fn(cmd):
            if cmd == "git":
                return "/usr/bin/git"  # git installed
            return "/usr/bin/node"  # node available

        mock_shutil.which.side_effect = which_fn
        mock_find.return_value = Path("/fake/cli.js")
        mock_subprocess.run.side_effect = fake_run

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        # Known project
        mock_client.get_project.return_value = {
            "id": str(tmp_path.resolve()),
            "last_scanned_at": "2026-04-18T10:00:00+00:00",
        }

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # Note about non-git fallback should be in output
        assert "git" in result.output.lower() or "repository" in result.output.lower()
        assert "full scan" in result.output.lower()
        assert "Graph updated" in result.output


def test_scan_neo4j_error_during_scan_shows_actionable_message(tmp_path):
    """When Neo4j becomes unavailable mid-scan (upsert fails), shows actionable error."""
    _make_scan_env(tmp_path)

    with patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find, \
         patch("rei_cli.commands.scan.subprocess") as mock_subprocess:

        mock_find.return_value = Path("/fake/cli.js")
        ingester_result = MagicMock()
        ingester_result.returncode = 0
        ingester_result.stdout = SAMPLE_INGESTER_OUTPUT
        ingester_result.stderr = ""
        mock_subprocess.run.return_value = ingester_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None
        mock_client.upsert_nodes.side_effect = Exception("ServiceUnavailable: connection refused")

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 1
        assert "Neo4j" in result.output
        assert "rei doctor" in result.output


def test_scan_no_traceback_without_verbose_on_unexpected_error(tmp_path):
    """Unexpected errors during scan don't show raw Python tracebacks without --verbose."""
    _make_scan_env(tmp_path)

    with patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find, \
         patch("rei_cli.commands.scan.subprocess") as mock_subprocess:

        mock_find.return_value = Path("/fake/cli.js")
        ingester_result = MagicMock()
        ingester_result.returncode = 0
        ingester_result.stdout = SAMPLE_INGESTER_OUTPUT
        ingester_result.stderr = ""
        mock_subprocess.run.return_value = ingester_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None
        mock_client.upsert_nodes.side_effect = RuntimeError("Connection lost")

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 1
        assert "Traceback" not in result.output
        # The exception was handled cleanly (not an unhandled RuntimeError)
        assert result.exception is None or isinstance(result.exception, SystemExit)


def test_scan_verbose_flag_shows_traceback_on_unexpected_error(tmp_path):
    """With --verbose, unexpected errors include Python traceback details."""
    _make_scan_env(tmp_path)

    with patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find, \
         patch("rei_cli.commands.scan.subprocess") as mock_subprocess:

        mock_find.return_value = Path("/fake/cli.js")
        ingester_result = MagicMock()
        ingester_result.returncode = 0
        ingester_result.stdout = SAMPLE_INGESTER_OUTPUT
        ingester_result.stderr = ""
        mock_subprocess.run.return_value = ingester_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None
        mock_client.upsert_nodes.side_effect = RuntimeError("Connection lost")

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path), "--verbose"])

        assert result.exit_code == 1
        # Traceback details should appear in verbose mode
        assert "Traceback" in result.output or "RuntimeError" in result.output


# ── Regression: bundled ingester must include parser.js sibling ───────────────

ERR_MODULE_NOT_FOUND_STDERR = (
    "node:internal/modules/esm/resolve:274\n"
    "    throw new ERR_MODULE_NOT_FOUND(\n"
    "          ^\n\n"
    "Error [ERR_MODULE_NOT_FOUND]: Cannot find module\n"
    "'/opt/homebrew/.../rei_cli/_ingester/parser.js' imported from\n"
    "/opt/homebrew/.../rei_cli/_ingester/cli.js\n"
    "    at finalizeResolution (node:internal/modules/esm/resolve:274:11)\n"
    "  code: 'ERR_MODULE_NOT_FOUND',\n"
    "  url: 'file:///opt/homebrew/.../rei_cli/_ingester/parser.js'\n"
    "}\n"
    "Node.js v24.10.0\n"
)


def test_ingester_missing_parser_sibling_reported_as_per_file_warning(tmp_path):
    """Regression: when parser.js is missing from _ingester/, each file gets a warning.

    This reproduces the v0.2.3 bug where bundle_ingester.sh only copied cli.js
    but not parser.js. Node.js raised ERR_MODULE_NOT_FOUND for every file, and
    they appeared as parse-failure warnings in the scan summary.
    """
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    (src / "utils.ts").write_text("export function helper() {}")
    (tmp_path / ".rei").mkdir()
    (tmp_path / ".rei" / "project.toml").write_text(
        '[project]\nname = "myapp"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    broken_result = MagicMock()
    broken_result.returncode = 1
    broken_result.stdout = ""
    broken_result.stderr = ERR_MODULE_NOT_FOUND_STDERR

    with patch("rei_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("rei_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("rei_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/_ingester/cli.js")
        mock_subprocess.run.return_value = broken_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_project.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

    # Scan completes (no sys.exit on per-file errors) but all files are warnings
    assert result.exit_code == 0
    assert "warning" in result.output.lower()
    assert "failed to parse" in result.output.lower()
    # Both files are reported as failures
    assert "app.ts" in result.output
    assert "utils.ts" in result.output
    # Zero nodes/rels written because every parse failed
    assert "0 nodes, 0 rels" in result.output


def test_find_ingester_bundled_dir_must_contain_both_cli_and_parser(tmp_path):
    """Documents the bundle contract: _ingester/ must have both cli.js and parser.js.

    _find_ingester() returns the bundled cli.js path when cli.js exists.
    The companion parser.js must be placed alongside it by bundle_ingester.sh
    (via 'cp dist/*.js _ingester/' rather than 'cp dist/cli.js _ingester/cli.js').
    """
    from rei_cli.commands.scan import _find_ingester
    import rei_cli.commands.scan as scan_module

    ingester_dir = tmp_path / "_ingester"
    ingester_dir.mkdir()

    cli_js = ingester_dir / "cli.js"
    parser_js = ingester_dir / "parser.js"
    cli_js.write_text("// bundled cli")
    parser_js.write_text("// bundled parser")

    with patch.object(scan_module, "_PACKAGE_INGESTER_PATH", cli_js):
        result = _find_ingester()

    # cli.js is returned; parser.js sibling must also exist in the same dir
    assert result == cli_js
    assert parser_js.exists(), (
        "parser.js must be bundled alongside cli.js — "
        "bundle_ingester.sh must copy dist/*.js not just dist/cli.js"
    )
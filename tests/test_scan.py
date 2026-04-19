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
        assert "Done in" in result.output
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
        # Warning must NOT appear before the summary line ("Done in...")
        output = result.output
        done_pos = output.lower().find("done in")
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
        assert "Done in" in result.output
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
        assert "Done in" in result.output
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
        # Warning should mention last scan timestamp and incremental
        assert "already scanned" in result.output.lower() or "incremental" in result.output.lower()
        assert last_scanned in result.output
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
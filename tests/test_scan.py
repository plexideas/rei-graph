import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from click.testing import CliRunner

from dgk_cli.main import cli


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
    """dgk scan <file> calls the TS ingester and writes results to Neo4j."""
    # Create a dummy TS file
    ts_file = tmp_path / "test.ts"
    ts_file.write_text("export function hello() {}")

    with patch("dgk_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("dgk_cli.commands.scan.Neo4jClient") as mock_client_cls:

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

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
    """dgk scan <file> reports error when ingester fails."""
    ts_file = tmp_path / "bad.ts"
    ts_file.write_text("invalid content")

    with patch("dgk_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("dgk_cli.commands.scan.Neo4jClient"):

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
    """dgk scan reports error for non-existent file."""
    runner = CliRunner()
    result = runner.invoke(cli, ["scan", "/nonexistent/file.ts"])
    assert result.exit_code == 0
    assert "not found" in result.output.lower() or "error" in result.output.lower()


def test_scan_directory_scans_all_ts_files(tmp_path):
    """dgk scan <dir> walks the directory and scans all TS/TSX files."""
    # Create project structure
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.ts").write_text("export function login() {}")
    (src / "utils.tsx").write_text("export function helper() {}")
    (src / "readme.md").write_text("# docs")  # non-TS file, should be skipped

    # Create .dgk/project.toml with include=["src"]
    dgk = tmp_path / ".dgk"
    dgk.mkdir()
    (dgk / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("dgk_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("dgk_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("dgk_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # Ingester should be called twice (auth.ts + utils.tsx), not for readme.md
        assert mock_subprocess.run.call_count == 2
        mock_client.close.assert_called_once()


def test_scan_directory_respects_exclude_patterns(tmp_path):
    """dgk scan <dir> respects exclude patterns from config."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "bundle.ts").write_text("export function bundle() {}")

    dgk = tmp_path / ".dgk"
    dgk.mkdir()
    (dgk / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src", "dist"]\nexclude = ["dist"]\n'
    )

    with patch("dgk_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("dgk_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("dgk_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # Only src/app.ts should be scanned; dist/bundle.ts is excluded
        assert mock_subprocess.run.call_count == 1


def test_scan_directory_stores_resolved_import_paths(tmp_path):
    """dgk scan <dir> stores IMPORTS relationships with resolved file paths, not raw specifiers."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "App.tsx").write_text("export function App() {}")
    (src / "utils.ts").write_text("export function helper() {}")

    dgk = tmp_path / ".dgk"
    dgk.mkdir()
    (dgk / "project.toml").write_text(
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

    with patch("dgk_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("dgk_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("dgk_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_subprocess.run.side_effect = fake_run

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

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
    """dgk scan stores Package nodes and DEPENDS_ON relationships for external imports."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "App.tsx").write_text("export function App() {}")

    dgk = tmp_path / ".dgk"
    dgk.mkdir()
    (dgk / "project.toml").write_text(
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

    with patch("dgk_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("dgk_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("dgk_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ingester_output
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

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
    """dgk scan --changed uses git diff to detect modified files and scans only those."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "auth.ts").write_text("export function login() {}")
    (src / "utils.ts").write_text("export function helper() {}")

    dgk = tmp_path / ".dgk"
    dgk.mkdir()
    (dgk / "project.toml").write_text(
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

    with patch("dgk_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("dgk_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("dgk_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_subprocess.run.side_effect = fake_run

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

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
    """dgk scan --changed reports 'no changed files' when git diff returns nothing."""
    dgk = tmp_path / ".dgk"
    dgk.mkdir()
    (dgk / "project.toml").write_text('[project]\nname = "test"\n')

    git_result = MagicMock()
    git_result.returncode = 0
    git_result.stdout = ""

    with patch("dgk_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("dgk_cli.commands.scan.Neo4jClient") as mock_client_cls:

        mock_subprocess.run.return_value = git_result
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path), "--changed"])

        assert result.exit_code == 0
        assert "no" in result.output.lower() or "0" in result.output


def test_scan_changed_removes_nodes_for_deleted_files(tmp_path):
    """dgk scan --changed deletes nodes for files removed in git diff (D status)."""
    src = tmp_path / "src"
    src.mkdir()

    dgk = tmp_path / ".dgk"
    dgk.mkdir()
    (dgk / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    # git diff reports auth.ts as Deleted
    git_result = MagicMock()
    git_result.returncode = 0
    git_result.stdout = "src/deleted.ts\n"

    with patch("dgk_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("dgk_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("dgk_cli.commands.scan._find_ingester") as mock_find, \
         patch("dgk_cli.commands.scan._get_deleted_files") as mock_deleted:

        mock_find.return_value = Path("/fake/cli.js")
        mock_deleted.return_value = ["src/deleted.ts"]
        mock_subprocess.run.return_value = git_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path), "--changed"])

        assert result.exit_code == 0
        # delete_file_nodes was called for the deleted file
        mock_client.delete_file_nodes.assert_called_with("src/deleted.ts")


# ── Phase 1: progress bar + enriched summary ─────────────────────────────────

def test_scan_directory_summary_contains_elapsed_time(tmp_path):
    """dgk scan <dir> summary line includes elapsed time (e.g. 'Done in Xs')."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text("export function app() {}")

    dgk = tmp_path / ".dgk"
    dgk.mkdir()
    (dgk / "project.toml").write_text(
        '[project]\nname = "test"\n[scan]\ninclude = ["src"]\nexclude = []\n'
    )

    with patch("dgk_cli.commands.scan.subprocess") as mock_subprocess, \
         patch("dgk_cli.commands.scan.Neo4jClient") as mock_client_cls, \
         patch("dgk_cli.commands.scan._find_ingester") as mock_find:

        mock_find.return_value = Path("/fake/cli.js")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_INGESTER_OUTPUT
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert "Done in" in result.output
        assert "nodes" in result.output
        assert "rels" in result.output
        assert "files" in result.output


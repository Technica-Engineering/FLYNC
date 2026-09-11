"""Tests for the automatic error-number fixer and the ``errors sync`` pipeline entry point."""

from textwrap import dedent

import pytest
from typer.testing import CliRunner

from flync.core.utils.exceptions import Severity
from flync_cli.commands.errors import app
from flync_cli.utils import error_renumber, errors
from flync_cli.utils.error_renumber import (
    Renumbering,
    RenumberPlan,
    apply_renumbering,
    plan_renumbering,
    propagate_ids,
    resolve_base_ref,
    sync_catalog,
)
from flync_cli.utils.errors import ErrorRecord, next_error_number, render_catalog

runner = CliRunner()

CALL = 'raise err_minor("{msg}", category=Category.VALUE_RANGE, error_number="{number}")'


def rec(number, file="src/flync/a.py", lineno=1, number_pos=(1, 0, 5), category=1, module="ECU", severity=Severity.MIN):
    """A record standing in for one factory call site."""

    return ErrorRecord(
        error_id=f"FLYNC-{module}-{severity.value}-VAL-{number}",
        module=module,
        severity=severity,
        category=category,
        number=number,
        location="a.f",
        message="'boom'",
        file=file,
        lineno=lineno,
        number_pos=number_pos,
    )


def write_module(root, relpath, calls):
    """Write a source file raising one error per (msg, number) pair; returns its path."""

    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join("    " + CALL.format(msg=msg, number=number) for msg, number in calls)
    path.write_text(
        dedent("""
            from flync.core.utils.exceptions import err_minor, Category

            def f():
            """) + body + "\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throw-away source tree the scanner and the fixer both point at."""

    root = tmp_path / "src"
    (root / "flync").mkdir(parents=True)
    monkeypatch.setattr(errors, "SRC_ROOT", root)
    monkeypatch.setattr(error_renumber, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(error_renumber, "scan_error_calls", lambda: errors.scan_error_calls(root))
    return root


class TestScannerNumberPosition:
    def test_records_span_of_the_number_literal(self, repo):
        write_module(repo, "flync/mod.py", [("x", "007")])
        record = errors.scan_error_calls(repo)[0]
        line = (repo / "flync/mod.py").read_text().splitlines()[record.number_pos[0] - 1]
        assert line[record.number_pos[1] : record.number_pos[2]] == '"007"'

    def test_numbers_in_source_reads_raw_text(self):
        text = dedent("""
            from flync.core.utils.exceptions import err_major, Category

            def f():
                raise err_major("x", category=Category.REQUIRED, error_number="042")
            """)
        assert errors.numbers_in_source(text) == {"042"}

    @pytest.mark.parametrize(
        "text, expected",
        [
            pytest.param("def f():\n    pass\n", set(), id="no-factory-import"),
            pytest.param("this is not python(", set(), id="syntax-error"),
        ],
    )
    def test_numbers_in_source_tolerates_unusable_input(self, text, expected):
        assert errors.numbers_in_source(text) == expected


class TestNextErrorNumberReserved:
    def test_a_gap_left_by_a_deleted_error_is_not_reused(self):
        assert next_error_number([rec("001"), rec("002"), rec("004")]) == "005"

    def test_reserved_numbers_count_as_spent(self):
        assert next_error_number([rec("003")], reserved={"250"}) == "251"

    def test_non_numeric_reserved_entries_are_ignored(self):
        assert next_error_number([rec("003")], reserved={"NNN"}) == "004"

    def test_catalog_numbers_extracted_from_ids(self):
        assert errors.catalog_numbers(render_catalog([rec("009")])) == {"009"}

    @pytest.mark.parametrize("text", [None, ""], ids=["missing", "empty"])
    def test_catalog_numbers_without_a_catalog(self, text):
        assert errors.catalog_numbers(text) == set()


class TestPlanRenumbering:
    def test_no_duplicates_yields_empty_plan(self):
        plan = plan_renumbering([rec("001"), rec("002")])
        assert plan.empty
        assert plan.unfixable == []

    def test_keeps_the_call_site_present_on_the_base_branch(self, monkeypatch):
        old = rec("071", file="src/flync/old.py", lineno=10)
        new = rec("071", file="src/flync/new.py", lineno=5)
        monkeypatch.setattr(error_renumber, "base_numbers", lambda ref, files: {"src/flync/old.py": {"071"}, "src/flync/new.py": set()})
        plan = plan_renumbering([old, new], base_ref="origin/main")
        assert [(i.record.file, i.new_number) for i in plan.renumberings] == [("src/flync/new.py", "072")]

    def test_falls_back_to_file_order_without_git(self):
        first = rec("071", file="src/flync/a.py", lineno=10)
        second = rec("071", file="src/flync/b.py", lineno=5)
        plan = plan_renumbering([first, second], base_ref=None)
        assert [i.record.file for i in plan.renumberings] == ["src/flync/b.py"]

    def test_fresh_numbers_clear_code_catalog_and_base(self, monkeypatch):
        records = [rec("001", file="src/flync/a.py"), rec("001", file="src/flync/b.py", lineno=2)]
        monkeypatch.setattr(error_renumber, "base_numbers", lambda ref, files: {"src/flync/a.py": {"300"}})
        plan = plan_renumbering(records, base_ref="origin/main", catalog_text=render_catalog([rec("200")]))
        assert plan.renumberings[0].new_number == "301"

    def test_three_way_collision_gets_distinct_numbers(self):
        records = [rec("005", file=f"src/flync/{name}.py") for name in ("a", "b", "c")]
        plan = plan_renumbering(records, base_ref=None)
        assert sorted(i.new_number for i in plan.renumberings) == ["006", "007"]

    def test_unpositioned_number_is_reported_not_rewritten(self):
        records = [rec("005", file="src/flync/a.py"), rec("005", file="src/flync/b.py", number_pos=None)]
        plan = plan_renumbering(records, base_ref=None)
        assert plan.empty
        assert plan.unfixable[0].number == "005"

    def test_new_error_id_only_moves_the_number(self):
        item = Renumbering(record=rec("071", module="TSN"), new_number="248")
        assert item.old_error_id == "FLYNC-TSN-MIN-VAL-071"
        assert item.new_error_id == "FLYNC-TSN-MIN-VAL-248"


class TestApplyRenumbering:
    def test_rewrites_only_the_number_literal(self, repo, tmp_path):
        write_module(repo, "flync/mod.py", [("keep me", "071")])
        record = errors.scan_error_calls(repo)[0]
        apply_renumbering(RenumberPlan([Renumbering(record, "248")], [], None), repo_root=tmp_path)
        text = (repo / "flync/mod.py").read_text()
        assert 'error_number="248"' in text
        assert "keep me" in text

    def test_rewrites_several_sites_in_one_file(self, repo, tmp_path):
        write_module(repo, "flync/mod.py", [("a", "001"), ("b", "002"), ("c", "003")])
        records = errors.scan_error_calls(repo)
        plan = RenumberPlan([Renumbering(records[0], "301"), Renumbering(records[2], "302")], [], None)
        apply_renumbering(plan, repo_root=tmp_path)
        assert errors.numbers_in_source((repo / "flync/mod.py").read_text()) == {"301", "002", "302"}

    def test_preserves_single_quotes(self, repo, tmp_path):
        path = repo / "flync/mod.py"
        path.write_text(
            "from flync.core.utils.exceptions import err_minor, Category\n\ndef f():\n    raise err_minor('x', category=Category.VALUE_RANGE, error_number='071')\n",
            encoding="utf-8",
        )
        record = errors.scan_error_calls(repo)[0]
        apply_renumbering(RenumberPlan([Renumbering(record, "248")], [], None), repo_root=tmp_path)
        assert "error_number='248'" in path.read_text()

    def test_non_ascii_earlier_on_the_line_does_not_shift_the_span(self, repo, tmp_path):
        path = repo / "flync/mod.py"
        path.write_text(
            'from flync.core.utils.exceptions import err_minor, Category\n\ndef f():\n    raise err_minor("café über", category=Category.VALUE_RANGE, error_number="071")\n',
            encoding="utf-8",
        )
        record = errors.scan_error_calls(repo)[0]
        apply_renumbering(RenumberPlan([Renumbering(record, "248")], [], None), repo_root=tmp_path)
        text = path.read_text(encoding="utf-8")
        assert 'error_number="248"' in text
        assert "café über" in text


class TestPropagateIds:
    def test_rewrites_pinned_ids_in_tests(self, tmp_path):
        test_file = tmp_path / "tests" / "test_x.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text('assert_single_error(exc, "FLYNC-TSN-MIN-VAL-071", "boom")\n', encoding="utf-8")
        plan = RenumberPlan([Renumbering(rec("071", module="TSN"), "248")], [], None)
        changed = propagate_ids(plan, repo_root=tmp_path, roots=("tests",))
        assert changed == [test_file]
        assert "FLYNC-TSN-MIN-VAL-248" in test_file.read_text()

    def test_leaves_other_ids_alone(self, tmp_path):
        test_file = tmp_path / "tests" / "test_x.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text('"FLYNC-ECU-MIN-VAL-071"\n', encoding="utf-8")
        plan = RenumberPlan([Renumbering(rec("071", module="TSN"), "248")], [], None)
        assert propagate_ids(plan, repo_root=tmp_path, roots=("tests",)) == []

    def test_skips_generated_directories(self, tmp_path):
        generated = tmp_path / "docs" / "source" / "build" / "page.rst"
        generated.parent.mkdir(parents=True)
        generated.write_text("FLYNC-TSN-MIN-VAL-071\n", encoding="utf-8")
        plan = RenumberPlan([Renumbering(rec("071", module="TSN"), "248")], [], None)
        assert propagate_ids(plan, repo_root=tmp_path, roots=("docs/source",)) == []

    def test_empty_plan_touches_nothing(self, tmp_path):
        assert propagate_ids(RenumberPlan([], [], None), repo_root=tmp_path) == []

    def test_never_touches_files_outside_the_root(self, tmp_path):
        outsider = tmp_path.parent / "outside.txt"
        outsider.parent.mkdir(parents=True, exist_ok=True)
        outsider.write_text("FLYNC-TSN-MIN-VAL-071\n", encoding="utf-8")
        plan = RenumberPlan([Renumbering(rec("071", module="TSN"), "248")], [], None)
        assert propagate_ids(plan, repo_root=tmp_path, roots=("..",)) == []
        assert "FLYNC-TSN-MIN-VAL-071" in outsider.read_text()


class TestResolveBaseRef:
    def test_explicit_ref_wins_when_it_resolves(self, monkeypatch):
        monkeypatch.setattr(error_renumber, "_git", lambda *args: "abc\n" if "release-1" in args[-1] else None)
        assert resolve_base_ref("release-1") == "release-1"

    def test_none_when_nothing_resolves(self, monkeypatch):
        monkeypatch.setattr(error_renumber, "_git", lambda *args: None)
        assert resolve_base_ref() is None

    def test_reads_the_ci_target_branch(self, monkeypatch):
        monkeypatch.setenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", "release-2")
        monkeypatch.setattr(error_renumber, "_git", lambda *args: "abc\n" if args[-1].startswith("origin/release-2") else None)
        assert resolve_base_ref() == "origin/release-2"


class TestSyncCatalog:
    def test_generates_the_catalog_and_drops_orphans(self, repo, tmp_path):
        write_module(repo, "flync/mod.py", [("live", "001")])
        catalog = tmp_path / "cat.rst"
        catalog.write_text(render_catalog([rec("999")]), encoding="utf-8")
        result = sync_catalog(base_ref=None, catalog_path=catalog)
        assert result.ok
        assert result.catalog_changed
        text = catalog.read_text()
        assert "-001" in text
        assert "999" not in text

    def test_second_run_is_a_no_op(self, repo, tmp_path):
        write_module(repo, "flync/mod.py", [("live", "001")])
        catalog = tmp_path / "cat.rst"
        sync_catalog(base_ref=None, catalog_path=catalog)
        assert sync_catalog(base_ref=None, catalog_path=catalog).clean

    def test_fixes_duplicates_before_generating(self, repo, tmp_path):
        write_module(repo, "flync/a.py", [("a", "001")])
        write_module(repo, "flync/b.py", [("b", "001")])
        catalog = tmp_path / "cat.rst"
        result = sync_catalog(base_ref=None, catalog_path=catalog)
        assert result.ok
        assert len(result.plan.renumberings) == 1
        assert errors.numbers_in_source((repo / "flync/b.py").read_text()) == {"002"}

    def test_check_mode_writes_nothing(self, repo, tmp_path):
        write_module(repo, "flync/a.py", [("a", "001")])
        write_module(repo, "flync/b.py", [("b", "001")])
        catalog = tmp_path / "cat.rst"
        result = sync_catalog(base_ref=None, write=False, catalog_path=catalog)
        assert not catalog.exists()
        assert result.plan.renumberings
        assert not result.clean
        assert errors.numbers_in_source((repo / "flync/b.py").read_text()) == {"001"}

    def test_no_fix_duplicates_reports_them_as_blocking(self, repo, tmp_path):
        write_module(repo, "flync/a.py", [("a", "001")])
        write_module(repo, "flync/b.py", [("b", "001")])
        result = sync_catalog(base_ref=None, fix_duplicates=False, catalog_path=tmp_path / "cat.rst")
        assert not result.ok
        assert any("duplicate number 001" in reason for reason in result.blocking)

    def test_unnumbered_call_site_blocks_generation(self, repo, tmp_path):
        (repo / "flync/mod.py").write_text(
            'from flync.core.utils.exceptions import err_minor, Category\n\ndef f():\n    raise err_minor("x", category=Category.VALUE_RANGE)\n',
            encoding="utf-8",
        )
        catalog = tmp_path / "cat.rst"
        result = sync_catalog(base_ref=None, catalog_path=catalog)
        assert not result.ok
        assert not catalog.exists()
        assert "unnumbered call site" in result.blocking[0]


class TestSyncCommand:
    def test_clean_tree_exits_zero(self, repo, tmp_path, monkeypatch):
        write_module(repo, "flync/mod.py", [("live", "001")])
        catalog = tmp_path / "cat.rst"
        monkeypatch.setattr("flync_cli.utils.error_renumber.CATALOG_PATH", catalog)
        sync_catalog(base_ref=None, catalog_path=catalog)
        result = runner.invoke(app, ["sync", "--base", "does-not-exist"])
        assert result.exit_code == 0
        assert "already in sync" in result.stdout

    def test_check_exits_one_when_the_catalog_is_stale(self, repo, tmp_path, monkeypatch):
        write_module(repo, "flync/mod.py", [("live", "001")])
        monkeypatch.setattr("flync_cli.utils.error_renumber.CATALOG_PATH", tmp_path / "cat.rst")
        result = runner.invoke(app, ["sync", "--check"])
        assert result.exit_code == 1

    def test_blocking_problem_exits_one(self, repo, tmp_path, monkeypatch):
        (repo / "flync/mod.py").write_text(
            'from flync.core.utils.exceptions import err_minor\n\ndef f():\n    raise err_minor("x")\n',
            encoding="utf-8",
        )
        monkeypatch.setattr("flync_cli.utils.error_renumber.CATALOG_PATH", tmp_path / "cat.rst")
        result = runner.invoke(app, ["sync"])
        assert result.exit_code == 1
        assert "Needs a human" in result.stdout


class TestFixNumbersCommand:
    def test_reports_when_there_is_nothing_to_do(self, repo, tmp_path, monkeypatch):
        write_module(repo, "flync/mod.py", [("a", "001")])
        monkeypatch.setattr("flync_cli.commands.errors.scan_error_calls", lambda: errors.scan_error_calls(repo))
        monkeypatch.setattr("flync_cli.commands.errors.CATALOG_PATH", tmp_path / "cat.rst")
        result = runner.invoke(app, ["fix-numbers"])
        assert result.exit_code == 0
        assert "No duplicated error numbers" in result.stdout

    def test_dry_run_leaves_the_source_untouched(self, repo, tmp_path, monkeypatch):
        write_module(repo, "flync/a.py", [("a", "001")])
        write_module(repo, "flync/b.py", [("b", "001")])
        monkeypatch.setattr("flync_cli.commands.errors.scan_error_calls", lambda: errors.scan_error_calls(repo))
        monkeypatch.setattr("flync_cli.commands.errors.CATALOG_PATH", tmp_path / "cat.rst")
        result = runner.invoke(app, ["fix-numbers", "--dry-run", "--base", "does-not-exist"])
        assert result.exit_code == 0
        assert "would be renumbered" in result.stdout
        assert errors.numbers_in_source((repo / "flync/b.py").read_text()) == {"001"}

    def test_renumbers_the_duplicate(self, repo, tmp_path, monkeypatch):
        write_module(repo, "flync/a.py", [("a", "001")])
        write_module(repo, "flync/b.py", [("b", "001")])
        monkeypatch.setattr("flync_cli.commands.errors.scan_error_calls", lambda: errors.scan_error_calls(repo))
        monkeypatch.setattr("flync_cli.commands.errors.CATALOG_PATH", tmp_path / "cat.rst")
        result = runner.invoke(app, ["fix-numbers", "--base", "does-not-exist"])
        assert result.exit_code == 0
        assert errors.numbers_in_source((repo / "flync/b.py").read_text()) == {"002"}

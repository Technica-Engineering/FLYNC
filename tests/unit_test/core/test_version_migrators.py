"""Tests for the FLYNC workspace schema-migration mechanism."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from flync.core.version_migrators._base import FLYNCMigration, MigrationRegistry, migration, migration_registry
from flync.core.version_migrators.engine import (
    MigrationEngine,
    Migrator,
)
from flync.core.version_migrators.engine import WorkspaceMigrationState as State
from flync.core.version_migrators.engine import _write_documents, apply_migration_policy
from flync.core.version_migrators.history import MigrationHistory, MigrationRecord, load_history, save_history
from flync.model.flync_4_metadata.metadata import BaseVersion
from flync.sdk.context.workspace_config import WorkspaceConfiguration
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

V = lambda v: BaseVersion(version_schema="pep440", version=v)  # noqa: E731

#: Deterministic "installed" version used by the runtime-behavior tests, so they never depend on
#: how (or whether) the ``flync`` distribution metadata resolves under CI (where detection can
#: fall back to ``0.0.0`` and otherwise bias every recorded stamp toward ``NEWER``).
CURRENT_VERSION = "1.2.3"


@pytest.fixture(autouse=True)
def _fixed_current_version(monkeypatch):
    monkeypatch.setattr(
        "flync.core.version_migrators.engine._get_current_flync_version",
        lambda: V(CURRENT_VERSION),
    )


# ============================================================================
# Sample migrations
# ============================================================================


class RenameFooToBarMigration(FLYNCMigration):
    unique_id = "test_rename_foo"
    target_version = "0.10.0"
    description = "Renames a top-level 'foo' key to 'bar'."

    def should_apply(self, documents):
        return any(isinstance(doc, dict) and "foo" in doc for doc in documents.values())

    def apply(self, documents):
        for doc in documents.values():
            if isinstance(doc, dict) and "foo" in doc:
                doc["bar"] = doc.pop("foo")


class WrapBazMigration(FLYNCMigration):
    unique_id = "test_wrap_baz"
    target_version = "0.11.0"
    description = "Wraps a top-level 'baz' value in a list."

    def apply(self, documents):
        for doc in documents.values():
            if isinstance(doc, dict) and "baz" in doc:
                doc["baz"] = [doc["baz"]]


@pytest.fixture
def global_registry():
    """The process-global registry, restored to its previous contents after the test."""
    snapshot = migration_registry.all()
    yield migration_registry
    migration_registry.clear()
    for registered in snapshot:
        migration_registry.register(registered)


@pytest.fixture
def two_migrations():
    registry = MigrationRegistry.new()
    registry.register(RenameFooToBarMigration())
    registry.register(WrapBazMigration())
    return registry


# ============================================================================
# Registry invariants
# ============================================================================


class TestMigrationRegistry:
    @pytest.mark.parametrize(
        "bad_cls",
        [
            type(
                "NoId",
                (FLYNCMigration,),
                {"target_version": "0.1.0", "apply": lambda self, documents: None},
            ),
        ],
    )
    def test_empty_unique_id_rejected(self, bad_cls):
        registry = MigrationRegistry.new()
        with pytest.raises(ValueError, match="unique_id"):
            registry.register(bad_cls)

    def test_duplicate_unique_id_rejected(self):
        registry = MigrationRegistry.new()
        registry.register(RenameFooToBarMigration())
        duplicate = RenameFooToBarMigration()
        with pytest.raises(ValueError, match="Duplicate migration unique_id"):
            registry.register(duplicate)

    def test_duplicate_target_version_rejected(self):
        registry = MigrationRegistry.new()

        class Other(FLYNCMigration):
            unique_id = "test_other"
            target_version = "0.10.0"

            def apply(self, documents):
                pass

        registry.register(RenameFooToBarMigration())
        other = Other()
        with pytest.raises(ValueError, match="share target_version"):
            registry.register(other)

    @pytest.mark.parametrize("target_version", ["", "not-a-version"])
    def test_invalid_target_version_rejected(self, target_version):
        class BadTarget(FLYNCMigration):
            unique_id = "test_bad_target"

            def apply(self, documents):
                pass

        BadTarget.target_version = target_version
        registry = MigrationRegistry.new()
        with pytest.raises(ValueError, match="not a PEP 440 version"):
            registry.register(BadTarget)

    def test_decorator_registers_into_default_registry(self, global_registry):
        @migration
        class Ephemeral(FLYNCMigration):
            unique_id = "test_ephemeral_deco"
            target_version = "99.0.0"

            def apply(self, documents):
                pass

        assert global_registry.get("test_ephemeral_deco") is not None


# ============================================================================
# Status classification
# ============================================================================


class TestEvaluate:
    def test_no_version(self):
        status = MigrationEngine().evaluate(None, V("0.12.0"))
        assert status.state is State.NO_VERSION

    def test_newer_refuses_migration(self):
        status = MigrationEngine().evaluate(V("0.12.0"), V("0.11.0"))
        assert status.state is State.NEWER

    def test_unsupported_old(self):
        status = MigrationEngine().evaluate(V("0.1.0"), V("0.12.0"))
        assert status.state is State.UNSUPPORTED_OLD

    def test_up_to_date_exact(self):
        status = MigrationEngine().evaluate(V("0.12.0"), V("0.12.0"))
        assert status.state is State.UP_TO_DATE
        assert status.requires_stamp is False

    def test_up_to_date_but_stamp_lags(self, two_migrations):
        # recorded < current but no migration covers the gap -> nothing to transform,
        # yet the stamp should be advanced so the warning stops.
        status = MigrationEngine(registry=two_migrations).evaluate(V("0.12.0"), V("0.12.5"))
        assert status.state is State.UP_TO_DATE
        assert status.requires_stamp is True

    def test_pending_lists_ordered_chain(self, two_migrations):
        status = MigrationEngine(registry=two_migrations).evaluate(V("0.9.0"), V("0.12.0"))
        assert status.state is State.PENDING_MIGRATION
        assert [m.unique_id for m in status.pending] == ["test_rename_foo", "test_wrap_baz"]

    def test_pending_only_covering_migrations(self, two_migrations):
        # recorded 0.10.5 skips the 0.10 rename (already done) but still needs the 0.11 wrap.
        status = MigrationEngine(registry=two_migrations).evaluate(V("0.10.5"), V("0.12.0"))
        assert [m.unique_id for m in status.pending] == ["test_wrap_baz"]


# ============================================================================
# Engine transform (pure)
# ============================================================================


class TestApply:
    def test_transforms_a_copy_and_reports_changed_uris(self, two_migrations):
        documents = {
            "root.flync.yaml": {"name": "x", "foo": 1},
            "other.flync.yaml": {"baz": 2},
        }
        original = {"root.flync.yaml": {"name": "x", "foo": 1}, "other.flync.yaml": {"baz": 2}}

        applied, working, changed = MigrationEngine(registry=two_migrations).apply(documents, V("0.9.0"), V("0.12.0"))

        # Input untouched.
        assert documents == original
        # Both migrated in the copy.
        assert working["root.flync.yaml"] == {"name": "x", "bar": 1}
        assert working["other.flync.yaml"] == {"baz": [2]}
        assert set(changed) == {"root.flync.yaml", "other.flync.yaml"}
        assert [a.unique_id for a in applied] == ["test_rename_foo", "test_wrap_baz"]

    def test_should_apply_error_propagates(self):
        class BrokenGuard(FLYNCMigration):
            unique_id = "test_broken_guard"
            target_version = "0.10.0"

            def should_apply(self, documents):
                raise KeyError("guard")

            def apply(self, documents):  # pragma: no cover - must not run
                raise AssertionError("apply ran despite a failing should_apply")

        registry = MigrationRegistry.new()
        registry.register(BrokenGuard)
        engine = MigrationEngine(registry=registry)
        documents = {"a.flync.yaml": {}}
        recorded, current = V("0.9.0"), V("0.12.0")
        with pytest.raises(KeyError, match="guard"):
            engine.apply(documents, recorded, current)

    def test_untouched_uris_not_reported_as_changed(self, two_migrations):
        documents = {"root.flync.yaml": {"name": "x", "bar": 1}}
        _, working, changed = MigrationEngine(registry=two_migrations).apply(documents, V("0.9.0"), V("0.12.0"))
        assert working["root.flync.yaml"] == {"name": "x", "bar": 1}
        assert changed == []


# ============================================================================
# History manifest
# ============================================================================


class TestHistory:
    def test_round_trip_preserves_order(self, tmp_path):
        history = MigrationHistory(
            migrations=[
                MigrationRecord(id="a", target_version="0.10.0", applied_at="t1", applied_by="0.12.0"),
                MigrationRecord(id="b", target_version="0.11.0", applied_at="t2", applied_by="0.12.0"),
            ]
        )
        save_history(tmp_path, history)
        loaded = load_history(tmp_path)
        assert loaded.applied_ids() == ["a", "b"]

    def test_appending_keeps_chronology(self, tmp_path):
        history = MigrationHistory()
        for i, m_id in enumerate(["m1", "m2", "m3"]):
            history.migrations.append(MigrationRecord(id=m_id, target_version="0.1.0", applied_at=f"t{i}", applied_by="x"))
        save_history(tmp_path, history)
        assert load_history(tmp_path).applied_ids() == ["m1", "m2", "m3"]

    def test_missing_history_loads_empty(self, tmp_path):
        assert load_history(tmp_path).migrations == []

    def test_file_under_flync_migrations_dir(self, tmp_path):
        save_history(tmp_path, MigrationHistory(migrations=[MigrationRecord(id="a", target_version="0.10.0", applied_at="t", applied_by="x")]))
        assert (tmp_path / ".flync" / "migrations" / "history.yaml").exists()


# ============================================================================
# Workspace-level orchestration (fakes avoid needing a fully loadable workspace)
# ============================================================================


@dataclass
class FakeDoc:
    ast: object = None
    text: str = ""
    compose_ast: object = None


@dataclass
class FakeWorkspace:
    configuration: WorkspaceConfiguration
    workspace_root: Path
    documents: dict = field(default_factory=dict)
    name: str = "fake"
    saved: bool = False

    def save_workspace_config(self):
        self.saved = True


def _fake_workspace(tmp_path, migration_mode="propose", recorded="0.9.0", documents=None) -> FakeWorkspace:
    docs = {uri: FakeDoc(ast=ast) for uri, ast in (documents or {}).items()}
    config = WorkspaceConfiguration(migration_mode=migration_mode, version=V(recorded))
    return FakeWorkspace(configuration=config, workspace_root=Path(tmp_path), documents=docs)


class TestMigrator:
    def test_check_reads_stamp_from_config_file(self, tmp_path, two_migrations):
        config_file = Path(tmp_path) / ".flync" / "config.yaml"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("version:\n  version_schema: pep440\n  version: '0.9.0'\n", encoding="utf-8")

        status = Migrator(registry=two_migrations).check(tmp_path)
        assert status.state is State.PENDING_MIGRATION

    def test_check_no_config_is_no_version(self, tmp_path):
        status = Migrator().check(tmp_path)
        assert status.state is State.NO_VERSION

    def test_check_config_without_version_is_no_version(self, tmp_path):
        config_file = Path(tmp_path) / ".flync" / "config.yaml"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("map_objects: true\n", encoding="utf-8")

        assert Migrator().check(tmp_path).state is State.NO_VERSION

    def test_run_raises_on_no_version(self, tmp_path, two_migrations):
        migrator = Migrator(registry=two_migrations)
        with pytest.raises(RuntimeError, match="no recorded FLYNC version"):
            migrator.run(tmp_path)

    def test_run_raises_on_unsupported_old(self, tmp_path, two_migrations):
        config = WorkspaceConfiguration(version=V("0.1.0"))
        workspace = FakeWorkspace(configuration=config, workspace_root=Path(tmp_path))
        migrator = Migrator(registry=two_migrations)
        with pytest.raises(RuntimeError, match="lowest supported"):
            migrator.run(workspace.workspace_root, workspace_config=config)

    def test_apply_in_place_writes_docs_history_and_stamps(self, tmp_path, two_migrations, monkeypatch):
        workspace = _fake_workspace(
            tmp_path,
            migration_mode="propose",
            recorded="0.9.0",
            documents={"root.flync.yaml": {"name": "x", "foo": 1}, "other.flync.yaml": {"keep": True}},
        )
        status = MigrationEngine(registry=two_migrations).evaluate(workspace.configuration.version, V("0.12.0"))

        Migrator(registry=two_migrations).apply_in_place(workspace, status)

        # Only the touched document was rewritten.
        assert (Path(tmp_path) / "root.flync.yaml").exists()
        assert not (Path(tmp_path) / "other.flync.yaml").exists()
        content = (Path(tmp_path) / "root.flync.yaml").read_text(encoding="utf-8")
        assert "bar: 1" in content
        assert "foo" not in content.split("bar", 1)[0]
        # History recorded, config save requested.
        assert load_history(tmp_path).applied_ids() == ["test_rename_foo", "test_wrap_baz"]
        assert workspace.saved is True
        # In-memory documents reflect the migration for the caller to keep loading from.
        assert workspace.documents["root.flync.yaml"].ast == {"name": "x", "bar": 1}
        # The stamp is advanced to the version the documents were migrated to.
        assert workspace.configuration.version == V("0.12.0")

    def test_apply_in_place_keeps_key_order_and_drops_stale_compose_ast(self, tmp_path, two_migrations):
        workspace = _fake_workspace(tmp_path, documents={"root.flync.yaml": {"zeta": 1, "foo": 2, "alpha": 3}})
        workspace.documents["root.flync.yaml"].compose_ast = object()
        status = MigrationEngine(registry=two_migrations).evaluate(workspace.configuration.version, V("0.12.0"))

        Migrator(registry=two_migrations).apply_in_place(workspace, status)

        lines = (Path(tmp_path) / "root.flync.yaml").read_text(encoding="utf-8").splitlines()
        assert lines == ["zeta: 1", "alpha: 3", "bar: 2"]
        assert workspace.documents["root.flync.yaml"].compose_ast is None

    def test_failed_document_write_leaves_workspace_untouched(self, tmp_path):
        original = Path(tmp_path) / "a.flync.yaml"
        original.write_text("old: 1\n", encoding="utf-8")
        (Path(tmp_path) / "blocker").write_text("", encoding="utf-8")

        # The second target's parent is a file, so staging fails after the first file is staged.
        with pytest.raises(OSError):
            _write_documents(Path(tmp_path), {"a.flync.yaml": "new: 1\n", "blocker/b.flync.yaml": "x: 1\n"})

        assert original.read_text(encoding="utf-8") == "old: 1\n"
        assert not list(Path(tmp_path).glob(".*.tmp"))

    def test_run_migrates_the_documents_as_written(self, tmp_path, two_migrations, monkeypatch):
        # Assembling the model would validate (and prune) the old-schema documents before the
        # migrations see them, so `run` must only open them.
        config_file = Path(tmp_path) / ".flync" / "config.yaml"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("version:\n  version_schema: pep440\n  version: '0.9.0'\n", encoding="utf-8")
        (Path(tmp_path) / "root.flync.yaml").write_text("foo: 1\nbaz: 2\n", encoding="utf-8")

        def fail_model_load(*args, **kwargs):
            raise AssertionError("Migrator.run must not assemble the model")

        monkeypatch.setattr("flync.sdk.workspace.flync_workspace.FLYNCWorkspace._load_from_path", fail_model_load)

        result = Migrator(registry=two_migrations).run(tmp_path)

        assert result.applied == ["test_rename_foo", "test_wrap_baz"]
        assert load_history(tmp_path).applied_ids() == ["test_rename_foo", "test_wrap_baz"]
        assert (Path(tmp_path) / "root.flync.yaml").read_text(encoding="utf-8") == "baz:\n- 2\nbar: 1\n"

    def test_stamp_writes_config_with_current_version(self, tmp_path, monkeypatch):
        saved = {}
        monkeypatch.setattr(WorkspaceConfiguration, "to_yaml_file", lambda self, path, **kwargs: saved.update({"path": str(path)}))
        Migrator().stamp(tmp_path)
        assert saved, "stamp() should persist the configuration"


# ============================================================================
# Load-time policy
# ============================================================================


class TestApplyMigrationPolicy:
    def test_off_does_nothing(self, tmp_path, caplog):
        workspace = _fake_workspace(tmp_path, migration_mode="off", recorded="0.9.0")
        with caplog.at_level(logging.WARNING):
            apply_migration_policy(workspace)
        assert not caplog.text

    def test_propose_warns_without_changing(self, tmp_path, caplog, two_migrations):
        workspace = _fake_workspace(
            tmp_path,
            migration_mode="propose",
            recorded="0.9.0",
            documents={"root.flync.yaml": {"foo": 1}},
        )
        with caplog.at_level(logging.WARNING):
            apply_migration_policy(workspace, registry=two_migrations)
        assert "flync migrate" in caplog.text
        assert workspace.documents["root.flync.yaml"].ast == {"foo": 1}
        assert not (Path(tmp_path) / "root.flync.yaml").exists()

    def test_up_to_date_no_warning(self, tmp_path, caplog):
        workspace = _fake_workspace(tmp_path, migration_mode="propose", recorded="0.12.0")
        with caplog.at_level(logging.WARNING):
            apply_migration_policy(workspace, registry=MigrationRegistry.new())
        assert not caplog.text

    def test_unsupported_old_warns(self, tmp_path, caplog):
        workspace = _fake_workspace(tmp_path, migration_mode="propose", recorded="0.1.0")
        with caplog.at_level(logging.WARNING):
            apply_migration_policy(workspace)
        assert "cannot be migrated" in caplog.text

    def test_newer_warns_without_changing(self, tmp_path, caplog):
        workspace = _fake_workspace(
            tmp_path,
            migration_mode="propose",
            recorded="99.0.0",  # arbitrarily-newer than any installed release
            documents={"root.flync.yaml": {"new_schema_key": 1}},
        )
        with caplog.at_level(logging.WARNING):
            apply_migration_policy(workspace)
        # Refuses and leaves data untouched; the stamp is never downgraded.
        assert "newer than the installed" in caplog.text
        assert workspace.documents["root.flync.yaml"].ast == {"new_schema_key": 1}
        assert not (Path(tmp_path) / "root.flync.yaml").exists()

    def test_auto_migrates_documents(self, tmp_path, two_migrations):
        workspace = _fake_workspace(tmp_path, migration_mode="auto", recorded="0.9.0", documents={"root.flync.yaml": {"foo": 1}})

        apply_migration_policy(workspace, registry=two_migrations)

        assert workspace.documents["root.flync.yaml"].ast == {"bar": 1}
        assert workspace.configuration.version == V(CURRENT_VERSION)
        assert workspace.saved is True

    def test_auto_failure_is_logged_and_load_continues(self, tmp_path, caplog):
        class Failing(FLYNCMigration):
            unique_id = "test_failing"
            target_version = "1.0.0"

            def apply(self, documents):
                raise RuntimeError("boom")

        registry = MigrationRegistry.new()
        registry.register(Failing)
        workspace = _fake_workspace(tmp_path, migration_mode="auto", recorded="0.9.0", documents={"root.flync.yaml": {"foo": 1}})

        with caplog.at_level(logging.ERROR):
            apply_migration_policy(workspace, registry=registry)

        assert "Automatic migration of workspace fake" in caplog.text
        assert "boom" in caplog.text
        assert workspace.documents["root.flync.yaml"].ast == {"foo": 1}
        assert workspace.configuration.version == V("0.9.0")
        assert workspace.saved is False


# ============================================================================
# Saving the configuration
# ============================================================================


class TestSaveWorkspaceConfig:
    @pytest.fixture(autouse=True)
    def _pending_global_migration(self, monkeypatch, global_registry):
        monkeypatch.setattr("flync.sdk.context.workspace_config._get_current_flync_version", lambda: V(CURRENT_VERSION))
        # Only WrapBazMigration is pending, whatever migrations FLYNC itself ships.
        global_registry.clear()
        global_registry.register(WrapBazMigration)

    def _saved_version(self, tmp_path, recorded: str) -> str:
        workspace = FLYNCWorkspace(name="ws", workspace_path=str(tmp_path), configuration=WorkspaceConfiguration(version=V(recorded)))
        workspace.save_workspace_config()
        return str(WorkspaceConfiguration.from_yaml_file(Path(tmp_path) / ".flync" / "config.yaml").version.version)

    def test_pending_migration_keeps_stamp(self, tmp_path):
        assert self._saved_version(tmp_path, "0.10.0") == "0.10.0"

    def test_unsupported_old_keeps_stamp(self, tmp_path):
        assert self._saved_version(tmp_path, "0.1.0") == "0.1.0"

    def test_no_pending_migration_advances_stamp(self, tmp_path):
        assert self._saved_version(tmp_path, "0.12.0") == CURRENT_VERSION

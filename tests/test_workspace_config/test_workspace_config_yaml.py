"""Tests for WorkspaceConfiguration YAML loading/saving and auto-discovery.

Tests:
1. Loading config from YAML file (from_yaml_file)
2. Saving config to YAML file (to_yaml_file)
3. Auto-discovery of .flync/config.yaml
4. Config file path override
5. Explicit config object override
6. Round-trip (load -> modify -> save -> load)
7. The configuration file stays inert data: it can neither name nor import a model class
"""

import importlib.metadata
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from flync.model.flync_4_metadata.metadata import BaseVersion
from flync.model.flync_model import FLYNCModel
from flync.sdk.context.workspace_config import (
    CONFIG_RELPATH,
    UNKNOWN_VERSION,
    ListObjectsMode,
    WorkspaceConfiguration,
    _get_current_flync_version,
)
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace


class TestWorkspaceConfigYamlLoading:
    """Test loading WorkspaceConfiguration from YAML files."""

    def test_load_config_with_multiple_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text("exclude_unset: false\nmap_objects: true\n")

            config = WorkspaceConfiguration.from_yaml_file(config_path)
            assert config.exclude_unset is False
            assert config.map_objects is True

    def test_load_config_with_custom_extensions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text("allowed_extensions:\n" "  - .flync.yaml\n" "  - .flync.yml\n" "  - .safety.yaml\n")

            config = WorkspaceConfiguration.from_yaml_file(config_path)
            assert ".safety.yaml" in config.allowed_extensions

    def test_load_config_with_list_objects_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text("list_objects_mode:\n" "  - INDEX\n" "  - NAME\n")

            config = WorkspaceConfiguration.from_yaml_file(config_path)
            assert config.list_objects_mode == (ListObjectsMode.INDEX | ListObjectsMode.NAME)

    def test_load_nonexistent_file_raises_error(self):
        with pytest.raises(FileNotFoundError):
            WorkspaceConfiguration.from_yaml_file("nonexistent.yaml")

    def test_load_invalid_yaml_raises_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "invalid.yaml"
            config_path.write_text("invalid: yaml: content: :[")

            with pytest.raises(yaml.YAMLError):  # YAML parsing error
                WorkspaceConfiguration.from_yaml_file(config_path)

    def test_unknown_key_is_rejected(self):
        """A typo in a hand-edited file must fail loudly, not be silently ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text("map_object: true\n")  # typo: missing 's'

            with pytest.raises(ValidationError, match="map_object"):
                WorkspaceConfiguration.from_yaml_file(config_path)


class TestRootModelIsNotConfigurable:
    """``root_model`` is programmatic-only and never crosses the file boundary."""

    def test_root_model_in_config_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text("root_model: some.module.SomeModel\n")

            with pytest.raises(ValueError, match="root_model cannot be set from a configuration file"):
                WorkspaceConfiguration.from_yaml_file(config_path)

    def test_root_model_as_string_is_rejected(self):
        """A class path is never resolved: that would import code named by data."""
        with pytest.raises(ValidationError, match="must be a FLYNC model class, not a module path"):
            WorkspaceConfiguration(root_model="flync.model.flync_model.FLYNCModel")

    def test_root_model_defaults_to_flync_model(self):
        assert WorkspaceConfiguration().root_model is FLYNCModel

    def test_root_model_is_never_written_to_yaml(self):
        """Even a non-default root model set in code stays out of the file."""

        class LocalRoot(FLYNCModel):
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            WorkspaceConfiguration(root_model=LocalRoot).to_yaml_file(config_path)

            content = config_path.read_text()
            assert "root_model" not in content
            assert "LocalRoot" not in content

            # The saved file is loadable, and falls back to the default root model.
            assert WorkspaceConfiguration.from_yaml_file(config_path).root_model is FLYNCModel

    def test_loading_workspace_does_not_touch_sys_path(self, example_workspace_path):
        """Opening a workspace must not make its directory importable."""
        before = list(sys.path)

        FLYNCWorkspace.safe_load_workspace(
            workspace_name="test_sys_path",
            workspace_path=example_workspace_path,
        )

        assert sys.path == before


class TestWorkspaceConfigYamlSaving:
    """Test saving WorkspaceConfiguration to YAML files."""

    def test_save_simple_config_excludes_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            WorkspaceConfiguration().to_yaml_file(config_path)

            content = config_path.read_text()
            # Defaults should be excluded
            assert "exclude_unset" not in content
            assert "map_objects" not in content
            assert "list_objects_mode" not in content

    def test_save_custom_config_includes_nondefaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config = WorkspaceConfiguration(
                exclude_unset=False,
                map_objects=True,
                list_objects_mode=ListObjectsMode.NAME,
            )
            config.to_yaml_file(config_path)

            content = config_path.read_text()
            assert "exclude_unset: false" in content
            assert "map_objects: true" in content
            assert "- NAME" in content

    def test_save_writes_allowed_extensions_as_sorted_sequence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            WorkspaceConfiguration(allowed_extensions={".b.yaml", ".a.yaml"}).to_yaml_file(config_path)

            content = config_path.read_text()
            assert "!!set" not in content
            assert content.index(".a.yaml") < content.index(".b.yaml")

    def test_save_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "subdir" / "nested" / "test.yaml"
            config = WorkspaceConfiguration()
            config.to_yaml_file(config_path)

            assert config_path.exists()


class TestWorkspaceConfigRoundTrip:
    """Test round-trip: load -> modify -> save -> load."""

    def test_roundtrip_preserves_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"

            # Create original config
            original = WorkspaceConfiguration(
                exclude_unset=False,
                map_objects=True,
                allowed_extensions={".flync.yaml", ".safety.yaml"},
            )
            original.to_yaml_file(config_path)

            # Load it back
            loaded = WorkspaceConfiguration.from_yaml_file(config_path)

            # Verify values match
            assert loaded.exclude_unset is False
            assert loaded.map_objects is True
            assert loaded.allowed_extensions == {".flync.yaml", ".safety.yaml"}

            # Save again and load to double-check
            config_path2 = Path(tmpdir) / "test2.yaml"
            loaded.to_yaml_file(config_path2)
            reloaded = WorkspaceConfiguration.from_yaml_file(config_path2)

            assert reloaded.exclude_unset is False
            assert reloaded.map_objects is True
            assert reloaded.allowed_extensions == {".flync.yaml", ".safety.yaml"}


class TestWorkspaceAutoDiscovery:
    """Test auto-discovery of .flync/config.yaml in workspace root."""

    def test_auto_discovery_finds_config(self, example_workspace_path):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Copy example workspace to temp directory
            temp_ws = Path(tmpdir) / "workspace"
            shutil.copytree(example_workspace_path, temp_ws)

            # Create .flync/config.yaml in temp workspace root
            config_path = temp_ws / CONFIG_RELPATH
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("exclude_unset: false\nmap_objects: true\n")

            # Load workspace without explicit config - should auto-discover
            ws = FLYNCWorkspace.safe_load_workspace(
                workspace_name="test_autodiscover",
                workspace_path=temp_ws,
                workspace_config=None,  # Auto-discover
            )

            # Config should be loaded from .flync/config.yaml
            assert ws.configuration.exclude_unset is False
            assert ws.configuration.map_objects is True

    def test_auto_discovery_uses_defaults_if_no_config(self, example_workspace_path):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Copy example workspace to temp directory
            temp_ws = Path(tmpdir) / "workspace"
            shutil.copytree(example_workspace_path, temp_ws)

            # Ensure config file doesn't exist
            (temp_ws / CONFIG_RELPATH).unlink(missing_ok=True)

            # Load workspace - should use defaults
            ws = FLYNCWorkspace.safe_load_workspace(
                workspace_name="test_no_config",
                workspace_path=temp_ws,
                workspace_config=None,
            )

            # Should have default config
            assert ws.configuration.root_model is FLYNCModel
            assert ws.configuration.exclude_unset is True
            assert ws.configuration.map_objects is False

    def test_explicit_config_object_overrides_autodiscovery(self, example_workspace_path):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Copy example workspace to temp directory
            temp_ws = Path(tmpdir) / "workspace"
            shutil.copytree(example_workspace_path, temp_ws)

            # Create .flync/config.yaml with different config
            config_path = temp_ws / CONFIG_RELPATH
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("exclude_unset: false\n")

            # Pass explicit config object - should override discovery
            explicit_config = WorkspaceConfiguration(
                exclude_unset=True,  # Different from file
                map_objects=True,
            )

            ws = FLYNCWorkspace.safe_load_workspace(
                workspace_name="test_override",
                workspace_path=temp_ws,
                workspace_config=explicit_config,
            )

            # Should use explicit config, not discovered one
            assert ws.configuration.exclude_unset is True
            assert ws.configuration.map_objects is True

    @pytest.mark.parametrize("as_path", [False, True])
    def test_explicit_config_file_path_overrides_autodiscovery(self, example_workspace_path, as_path):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Copy example workspace to temp directory
            temp_ws = Path(tmpdir) / "workspace"
            shutil.copytree(example_workspace_path, temp_ws)

            # Create .flync/config.yaml
            config_path = temp_ws / CONFIG_RELPATH
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("exclude_unset: false\n")

            # Create different config at custom path
            custom_config_path = temp_ws / "custom.yaml"
            custom_config_path.write_text("exclude_unset: true\nmap_objects: true\n")

            # Pass custom config path (str or Path) - should override auto-discovery
            ws = FLYNCWorkspace.safe_load_workspace(
                workspace_name="test_custom_path",
                workspace_path=temp_ws,
                workspace_config=custom_config_path if as_path else str(custom_config_path),
            )

            # Should use custom config, not auto-discovered
            assert ws.configuration.exclude_unset is True
            assert ws.configuration.map_objects is True


class TestWorkspaceConfigEdgeCases:
    """Test edge cases and special scenarios."""

    def test_load_empty_yaml_file_uses_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "empty.yaml"
            config_path.write_text("")

            config = WorkspaceConfiguration.from_yaml_file(config_path)
            assert config.root_model is FLYNCModel
            assert config.exclude_unset is True

    def test_list_objects_mode_string_format(self):
        """Test list_objects_mode string format compatibility."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"

            # Test string format with pipe separator
            config_path.write_text("list_objects_mode: INDEX|NAME\n")
            config = WorkspaceConfiguration.from_yaml_file(config_path)
            assert config.list_objects_mode == (ListObjectsMode.INDEX | ListObjectsMode.NAME)

    def test_nonexistent_config_file_path_raises_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_path = Path(tmpdir)

            with pytest.raises(FileNotFoundError):
                FLYNCWorkspace.safe_load_workspace(
                    workspace_name="test",
                    workspace_path=workspace_path,
                    workspace_config="nonexistent.yaml",
                )


class TestExampleWorkspaceWithConfig:
    """Test that the bundled example workspace loads through the configuration path."""

    def test_example_workspace_without_config_uses_defaults(self, example_workspace_path):
        """The example ships no .flync/config.yaml, so loading it falls back to defaults."""
        assert not (example_workspace_path / CONFIG_RELPATH).exists()

        ws = FLYNCWorkspace.safe_load_workspace(
            workspace_name="flync_example",
            workspace_path=example_workspace_path,
        )

        assert ws is not None
        assert ws.flync_model is not None
        assert ws.configuration.exclude_unset is True
        assert ws.configuration.map_objects is False
        # The version is stamped from the running release rather than read from disk.
        assert ws.configuration.version.version_schema == "pep440"

    def test_example_workspace_config_explicit_override(self, example_workspace_path):
        """An explicit config parameter takes precedence over auto-discovery."""
        explicit_config = WorkspaceConfiguration(map_objects=True)

        ws = FLYNCWorkspace.safe_load_workspace(
            workspace_name="flync_example_override",
            workspace_path=example_workspace_path,
            workspace_config=explicit_config,
        )

        assert ws is not None
        assert ws.flync_model is not None
        # Should use the explicit config, not the defaults auto-discovery would produce.
        assert ws.configuration.map_objects is True


class TestWorkspaceConfigSaving:
    """generate_configs / save_workspace_config persist the configuration."""

    def test_generate_configs_writes_config_file(self, example_workspace_path, tmp_path, monkeypatch):
        # tmp_path (not TemporaryDirectory) because the chdir below keeps the directory
        # busy on Windows until pytest tears the fixture down.
        temp_ws = tmp_path / "workspace"
        shutil.copytree(example_workspace_path, temp_ws)
        (temp_ws / CONFIG_RELPATH).unlink(missing_ok=True)

        ws = FLYNCWorkspace.load_workspace("save_test", temp_ws, WorkspaceConfiguration(map_objects=True))
        # Document URIs of a disk-loaded workspace are workspace-relative, so
        # generate_configs() writes them relative to the working directory.
        monkeypatch.chdir(temp_ws)
        ws.generate_configs()

        config_file = temp_ws / CONFIG_RELPATH
        assert config_file.exists()
        # The written file must always be loadable again
        assert WorkspaceConfiguration.from_yaml_file(config_file).map_objects is True

    def test_save_workspace_config_only(self, example_workspace_path):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_ws = Path(tmpdir) / "workspace"
            shutil.copytree(example_workspace_path, temp_ws)

            ws = FLYNCWorkspace.load_workspace("save_only", temp_ws, WorkspaceConfiguration(exclude_unset=False))
            ws.save_workspace_config()

            assert WorkspaceConfiguration.from_yaml_file(temp_ws / CONFIG_RELPATH).exclude_unset is False


class TestPersistConfigSuppression:
    """``persist_config`` suppresses the implicit .flync/config.yaml write."""

    @staticmethod
    def _prepare(example_workspace_path, tmp_path, monkeypatch, config):
        """Copy the example workspace, drop any existing config file, and chdir into it."""
        temp_ws = tmp_path / "workspace"
        shutil.copytree(example_workspace_path, temp_ws)
        (temp_ws / CONFIG_RELPATH).unlink(missing_ok=True)

        ws = FLYNCWorkspace.load_workspace("suppress_test", temp_ws, config)
        # Document URIs of a disk-loaded workspace are workspace-relative, so
        # generate_configs() writes them relative to the working directory.
        monkeypatch.chdir(temp_ws)
        return ws, temp_ws

    def test_default_is_enabled(self):
        assert WorkspaceConfiguration().persist_config is True

    def test_config_flag_suppresses_the_write(self, example_workspace_path, tmp_path, monkeypatch):
        ws, temp_ws = self._prepare(example_workspace_path, tmp_path, monkeypatch, WorkspaceConfiguration(persist_config=False))
        ws.generate_configs()

        assert not (temp_ws / CONFIG_RELPATH).exists()
        # The workspace documents themselves are still written.
        assert any(temp_ws.rglob("*.flync.yaml"))

    def test_call_argument_suppresses_the_write(self, example_workspace_path, tmp_path, monkeypatch):
        ws, temp_ws = self._prepare(example_workspace_path, tmp_path, monkeypatch, WorkspaceConfiguration())
        ws.generate_configs(persist_config=False)

        assert not (temp_ws / CONFIG_RELPATH).exists()

    def test_call_argument_overrides_a_disabled_config(self, example_workspace_path, tmp_path, monkeypatch):
        ws, temp_ws = self._prepare(example_workspace_path, tmp_path, monkeypatch, WorkspaceConfiguration(persist_config=False))
        ws.generate_configs(persist_config=True)

        assert (temp_ws / CONFIG_RELPATH).exists()

    def test_explicit_save_ignores_the_flag(self, example_workspace_path, tmp_path, monkeypatch):
        # persist_config governs only the implicit write; asking for the file directly always produces it.
        ws, temp_ws = self._prepare(example_workspace_path, tmp_path, monkeypatch, WorkspaceConfiguration(persist_config=False))
        ws.save_workspace_config()

        assert WorkspaceConfiguration.from_yaml_file(temp_ws / CONFIG_RELPATH).persist_config is False

    def test_flag_is_omitted_from_yaml_when_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / CONFIG_RELPATH
            WorkspaceConfiguration().to_yaml_file(config_file)

            assert "persist_config" not in yaml.safe_load(config_file.read_text())

    def test_flag_roundtrips_through_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / CONFIG_RELPATH
            WorkspaceConfiguration(persist_config=False).to_yaml_file(config_file)

            assert yaml.safe_load(config_file.read_text())["persist_config"] is False
            assert WorkspaceConfiguration.from_yaml_file(config_file).persist_config is False

    def test_hand_disabled_file_is_not_rewritten(self, example_workspace_path, tmp_path, monkeypatch):
        # A workspace whose config.yaml opts out keeps that file untouched across saves.
        ws, temp_ws = self._prepare(example_workspace_path, tmp_path, monkeypatch, WorkspaceConfiguration())
        config_file = temp_ws / CONFIG_RELPATH
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("persist_config: false\n")

        reloaded = FLYNCWorkspace.load_workspace("hand_edited", temp_ws)
        assert reloaded.configuration.persist_config is False
        reloaded.generate_configs()

        assert config_file.read_text() == "persist_config: false\n"


class TestWorkspaceConfigVersion:
    """Test version field auto-detection and serialization."""

    @staticmethod
    def _pin_running_version(monkeypatch, version: str) -> None:
        """
        Pin the release that :meth:`WorkspaceConfiguration._version_to_persist` compares against.

        The real version is derived from git tags at build time, so a checkout without them
        (a mirror that does not replicate tags, or a shallow clone) reports ``0.0.0.postN+<sha>``.
        Pinning keeps these tests about the comparison rule rather than about how the repository
        happened to be cloned.
        """
        monkeypatch.setattr(
            "flync.sdk.context.workspace_config._get_current_flync_version",
            lambda: BaseVersion(version_schema="pep440", version=version),
        )

    def test_version_auto_detects_current_flync_version(self):
        config = WorkspaceConfiguration()
        assert config.version is not None
        assert config.version.version_schema == "pep440"
        assert str(config.version.version) != ""

    def test_version_falls_back_when_distribution_missing(self, monkeypatch):
        """A missing 'flync' distribution must not break configuration construction."""

        def _raise(_name):
            raise importlib.metadata.PackageNotFoundError("flync")

        monkeypatch.setattr(importlib.metadata, "version", _raise)
        config = WorkspaceConfiguration()
        assert str(config.version.version) == UNKNOWN_VERSION

    def test_version_always_serialized_to_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config = WorkspaceConfiguration()
            config.to_yaml_file(config_path)

            content = config_path.read_text()
            # Version should always be serialized
            assert "version:" in content

    def test_version_default_includes_version_schema_and_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config = WorkspaceConfiguration()
            config.to_yaml_file(config_path)

            content = config_path.read_text()
            assert "version_schema:" in content
            assert "version:" in content

    def test_version_loaded_from_yaml_dict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text("version:\n  version_schema: pep440\n  version: '1.0.0'\n")

            config = WorkspaceConfiguration.from_yaml_file(config_path)
            assert config.version.version_schema == "pep440"
            assert str(config.version.version) == "1.0.0"

    def test_version_roundtrip_keeps_newer_recorded_version(self, monkeypatch):
        """A version newer than the running release is never moved backwards on save."""
        self._pin_running_version(monkeypatch, "1.0.0")
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text("version:\n  version_schema: pep440\n  version: '2.0.0'\n")

            loaded = WorkspaceConfiguration.from_yaml_file(config_path)
            assert str(loaded.version.version) == "2.0.0"

            config_path2 = Path(tmpdir) / "test2.yaml"
            loaded.to_yaml_file(config_path2)

            reloaded = WorkspaceConfiguration.from_yaml_file(config_path2)
            assert str(reloaded.version.version) == "2.0.0"

    def test_version_roundtrip_bumps_older_recorded_version(self, monkeypatch):
        """Rewriting an older file stamps it with the running release, which wrote its format."""
        self._pin_running_version(monkeypatch, "1.0.0")
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text("version:\n  version_schema: pep440\n  version: '0.5.0'\n")

            loaded = WorkspaceConfiguration.from_yaml_file(config_path)
            # Loading reports what is on disk; only writing moves the stamp forward.
            assert str(loaded.version.version) == "0.5.0"

            config_path2 = Path(tmpdir) / "test2.yaml"
            loaded.to_yaml_file(config_path2)

            reloaded = WorkspaceConfiguration.from_yaml_file(config_path2)
            assert str(reloaded.version.version) == "1.0.0"

    def test_version_roundtrip_leaves_other_schema_untouched(self, monkeypatch):
        """A semver-stamped file is not comparable to the pep440 running version, so it is kept."""
        self._pin_running_version(monkeypatch, "1.0.0")
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text("version:\n  version_schema: semver\n  version: '0.0.1'\n")

            loaded = WorkspaceConfiguration.from_yaml_file(config_path)
            config_path2 = Path(tmpdir) / "test2.yaml"
            loaded.to_yaml_file(config_path2)

            reloaded = WorkspaceConfiguration.from_yaml_file(config_path2)
            assert reloaded.version.version_schema == "semver"
            assert str(reloaded.version.version) == "0.0.1"

    def test_untagged_build_normalizes_to_unknown_version(self, monkeypatch):
        """A build with no release tag reports 0.0.0 rather than a per-commit dev version."""
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "0.0.0.post20+07e3a84")
        assert str(_get_current_flync_version().version) == UNKNOWN_VERSION

    def test_untagged_build_does_not_advance_recorded_version(self, monkeypatch):
        """A build that cannot determine its own version must not overwrite a real stamp."""
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "0.0.0.post20+07e3a84")
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text("version:\n  version_schema: pep440\n  version: '0.13.0'\n")

            loaded = WorkspaceConfiguration.from_yaml_file(config_path)
            config_path2 = Path(tmpdir) / "test2.yaml"
            loaded.to_yaml_file(config_path2)

            reloaded = WorkspaceConfiguration.from_yaml_file(config_path2)
            assert str(reloaded.version.version) == "0.13.0"

    def test_version_invalid_format_raises_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text("version: invalid\n")

            # Pydantic raises ValidationError for invalid version format
            with pytest.raises(ValidationError, match="version"):
                WorkspaceConfiguration.from_yaml_file(config_path)

    def test_version_with_other_config_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text("version:\n" "  version_schema: pep440\n" "  version: '1.5.0'\n" "exclude_unset: false\n")

            config = WorkspaceConfiguration.from_yaml_file(config_path)
            assert str(config.version.version) == "1.5.0"
            assert config.exclude_unset is False


class TestDotFlyncDirectoryLayout:
    """The workspace config lives in .flync/, and nowhere else."""

    def test_saving_creates_the_dot_flync_directory(self, tmp_path):
        WorkspaceConfiguration(map_objects=True).to_yaml_file(tmp_path / CONFIG_RELPATH)
        assert (tmp_path / ".flync").is_dir()
        assert (tmp_path / ".flync" / "config.yaml").is_file()

    def test_no_stray_root_level_config_is_written(self, tmp_path):
        WorkspaceConfiguration(map_objects=True).to_yaml_file(tmp_path / CONFIG_RELPATH)
        assert not (tmp_path / "flync.config.yaml").exists()
        assert not (tmp_path / "config.yaml").exists()

    def test_legacy_root_file_is_not_discovered(self, tmp_path):
        """V3: the pre-move name never shipped and must stay inert."""
        (tmp_path / "flync.config.yaml").write_text("exclude_unset: false\n")
        assert WorkspaceConfiguration.from_workspace(tmp_path).exclude_unset is True

    def test_dot_flync_is_not_a_flync_document(self, tmp_path):
        """V5: neither .flync nor .flync/config.yaml matches allowed_extensions."""
        cfg = WorkspaceConfiguration()
        assert "".join(Path(".flync").suffixes) not in cfg.allowed_extensions
        assert "".join(Path(".flync/config.yaml").suffixes) not in cfg.allowed_extensions

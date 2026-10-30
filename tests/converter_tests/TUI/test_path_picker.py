"""TUI Browse button and path picker for the config_path field."""

from textual.widgets import Button, Input, Select

from flync_converter.cli.tui.app import FlyncTUI
from flync_converter.cli.tui.widgets import ConverterPanel
from flync_converter.cli.tui.widgets.path_picker import PathPicker, PickMode, shown_paths


async def _wait_for(pilot, condition):
    """Let the app process messages until ``condition()`` holds; the fields are rebuilt asynchronously."""
    for _ in range(50):
        if condition():
            return
        await pilot.pause(0.02)
    assert condition()


async def _open_picker(app, pilot, panel_id):
    await _wait_for(pilot, lambda: bool(app.query(f"#{panel_id} #browse")))
    app.query_one(f"#{panel_id} #browse", Button).press()
    await _wait_for(pilot, lambda: isinstance(app.screen, PathPicker) and bool(app.screen.query("#picker-path")))
    return app.screen


def test_browse_picks_a_folder_for_directory_converters(helpers, tmp_path):
    """The flync converter uses folders, so the picker returns the typed or selected folder."""

    async def _impl():
        app = FlyncTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            panel = app.query_one("#source-panel-1", ConverterPanel)
            picker = await _open_picker(app, pilot, panel.id)
            assert picker._mode is PickMode.FOLDER

            picker.query_one("#picker-path", Input).value = str(tmp_path)
            picker.query_one("#picker-select", Button).press()
            await _wait_for(pilot, lambda: not isinstance(app.screen, PathPicker))
            assert panel.query_one(f"#field-{panel.id}-config_path", Input).value == str(tmp_path)

    helpers.run(_impl())


def test_browse_cancel_keeps_the_current_path(helpers):
    """Cancelling the picker leaves config_path unchanged."""

    async def _impl():
        app = FlyncTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            panel = app.query_one("#source-panel-1", ConverterPanel)
            helpers.set_config_path(panel, "/tmp/keep")
            picker = await _open_picker(app, pilot, panel.id)
            picker.query_one("#picker-path", Input).value = "/tmp/other"
            await pilot.press("escape")
            await _wait_for(pilot, lambda: not isinstance(app.screen, PathPicker))
            assert panel.query_one(f"#field-{panel.id}-config_path", Input).value == "/tmp/keep"

    helpers.run(_impl())


def test_browse_destination_file_gets_the_converter_extension(helpers, tmp_path):
    """A destination file name without an extension gets the converter's default extension."""

    async def _impl():
        app = FlyncTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            panel = app.query_one("#destination-panel-1", ConverterPanel)
            panel.query_one("#select", Select).value = "json"
            await _wait_for(pilot, lambda: panel.converter_type == "json" and bool(panel.query(f"#field-{panel.id}-config_path")))
            picker = await _open_picker(app, pilot, panel.id)
            assert picker._mode is PickMode.SAVE_FILE

            path_input = picker.query_one("#picker-path", Input)
            path_input.value = str(tmp_path / "system")
            picker.query_one("#picker-select", Button).press()
            await _wait_for(pilot, lambda: not isinstance(app.screen, PathPicker))
            assert panel.query_one(f"#field-{panel.id}-config_path", Input).value == str(tmp_path / "system.json")

    helpers.run(_impl())


def test_source_file_picker_lists_only_matching_files(tmp_path):
    """Source file mode shows folders and files with the converter's extensions only."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.json").write_text("{}")
    (tmp_path / "b.txt").write_text("")
    assert sorted(path.name for path in shown_paths(tmp_path.iterdir(), False, (".json",))) == ["a.json", "sub"]
    assert [path.name for path in shown_paths(tmp_path.iterdir(), True, ())] == ["sub"]

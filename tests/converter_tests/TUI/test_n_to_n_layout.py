"""TUI N-to-N layout: balanced columns, small terminals, and nested scrolling."""

import pytest
from textual.widgets import Button, Input, Label

from flync_converter.cli.tui.app import FlyncTUI
from flync_converter.cli.tui.widgets import ConverterPanelList


@pytest.mark.parametrize(
    ("width", "height", "panels_height", "log_height"),
    [
        (80, 24, 14, 3),
        (81, 31, 18, 6),
        (120, 40, 27, 6),
    ],
)
def test_layout_fits_standard_terminals(helpers, width, height, panels_height, log_height):
    """The screen, columns, and controls stay inside the terminal at supported sizes."""

    async def _impl():
        app = FlyncTUI()
        async with app.run_test(size=(width, height)) as pilot:
            await pilot.pause()
            sources = app.query_one("#source-panels", ConverterPanelList)
            destinations = app.query_one("#destination-panels", ConverterPanelList)
            source_panel = sources.panels[0]
            destination_panel = destinations.panels[0]
            source_select = source_panel.query_one("#select")
            destination_select = destination_panel.query_one("#select")
            source_input = source_panel.query_one("Input")
            source_add = sources.query_one("Button.add-endpoint", Button)
            add_row = sources.query_one(".add-row")

            assert app.screen.scrollbar_size_vertical == 0
            assert app.screen.virtual_size.height == height
            assert app.query_one("#panels").region.height == panels_height
            assert app.query_one("#run-log").region.height == log_height
            assert abs(sources.region.width - destinations.region.width) <= 1
            assert abs(source_panel.region.width - destination_panel.region.width) <= 1
            assert abs(source_select.region.width - destination_select.region.width) <= 1
            assert abs(source_add.region.width - source_select.region.width) <= 1
            assert source_select.region.x == 3
            assert width - (destination_select.region.x + destination_select.region.width) == 3
            assert add_row.region.bottom == sources.region.bottom
            assert add_row.region.right <= sources.region.right
            assert source_input.region.bottom <= add_row.region.y

    helpers.run(_impl())


def test_small_terminal_pins_add_row_with_multiple_endpoints(helpers):
    """At 80x24 the Add control stays visible while three endpoints scroll."""

    async def _impl():
        app = FlyncTUI()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            sources = app.query_one("#source-panels", ConverterPanelList)
            destinations = app.query_one("#destination-panels", ConverterPanelList)
            await sources.add_panel()
            await destinations.add_panel()
            await sources.add_panel()
            await destinations.add_panel()
            await pilot.pause()

            assert len(sources.panels) == 3
            assert len(destinations.panels) == 3
            assert sources.scrollbar_size_vertical >= 1
            assert destinations.scrollbar_size_vertical >= 1
            assert app.screen.scrollbar_size_vertical == 0

            for panel_list in (sources, destinations):
                add_row = panel_list.query_one(".add-row")
                add_button = panel_list.query_one("Button.add-endpoint", Button)
                assert add_row.region.bottom == panel_list.region.bottom
                assert add_row.region.right <= panel_list.region.right
                assert add_button.region.bottom <= panel_list.region.bottom
                assert add_button.region.y >= panel_list.region.y

    helpers.run(_impl())


def test_fields_do_not_get_a_nested_scrollbar(helpers):
    """Four or more config fields grow the panel and scroll the column instead."""

    async def _impl():
        app = FlyncTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            sources = app.query_one("#source-panels", ConverterPanelList)
            panel = sources.panels[0]
            fields = panel.query_one("#fields")
            for index in range(3):
                await fields.mount(Label(f"Extra {index}", classes="field-label"))
                await fields.mount(Input(id=f"field-{panel.id}-extra-{index}"))
            await pilot.pause()

            assert fields.scrollbar_size_vertical == 0
            assert fields.virtual_size.height <= fields.region.height
            assert sources.scrollbar_size_vertical >= 1
            assert sources.query_one(".add-row").region.bottom == sources.region.bottom

    helpers.run(_impl())


def test_resize_rebalances_columns_and_log(helpers):
    """Resizing from 120x40 to 80x24 and back keeps the layout inside the screen."""

    async def _impl():
        app = FlyncTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            sources = app.query_one("#source-panels", ConverterPanelList)
            add_row = sources.query_one(".add-row")
            assert app.query_one("#panels").region.height == 27
            assert app.query_one("#run-log").region.height == 6

            await pilot.resize_terminal(80, 24)
            await pilot.pause()
            assert app.screen.scrollbar_size_vertical == 0
            assert app.query_one("#panels").region.height == 14
            assert app.query_one("#run-log").region.height == 3
            assert add_row.region.bottom == sources.region.bottom

            await pilot.resize_terminal(120, 40)
            await pilot.pause()
            assert app.screen.scrollbar_size_vertical == 0
            assert app.query_one("#panels").region.height == 27
            assert app.query_one("#run-log").region.height == 6

    helpers.run(_impl())

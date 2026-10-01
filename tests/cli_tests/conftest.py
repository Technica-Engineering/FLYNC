"""Shared pytest fixtures for flync_cli tests."""

import os

# flync_cli.utils.console builds its shared Console at import time from the process's terminal size.
# Force it wide here (before that import can happen, and overriding any real COLUMNS/LINES the test
# runner inherited) so report-content assertions on wide tables don't depend on the ambient tty width.
#
# test_info.py, test_model_views.py and test_validate.py no longer depend on this: they pin their own
# width per test via tests.cli_tests.rich_output.capture(). It is kept for test_generate_uml.py, which
# still reads the shared console directly and is scoped for its own follow-up rewrite.
os.environ["COLUMNS"] = "200"
os.environ["LINES"] = "50"

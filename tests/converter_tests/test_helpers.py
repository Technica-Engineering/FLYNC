from pathlib import Path

CURRENT_DIR = Path(__file__).parent
EXAMPLE_DIR = str(CURRENT_DIR.parent.parent / "examples" / "flync_example")
GENERATED_TEST_OUTPUT_DIR = str(CURRENT_DIR / "generated_test_output")

import os
import random
import shutil
import string
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ITERATIONS = 10
current_dir = Path(__file__).resolve().parent


def __fuzz_keys(obj):
    if isinstance(obj, dict):
        obj = __fuzz_remove_key(obj)
        obj = __fuzz_add_key(obj)
        obj = __fuzz_rename_key(obj)
        return {k: __fuzz_keys(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [__fuzz_keys(v) for v in obj]

    return obj


def __fuzz_rename_key(obj: dict, probability=0.1):
    if not isinstance(obj, dict) or len(obj) < 1:
        return obj

    if random.random() < probability:
        key = random.choice(list(obj.keys()))
        obj[key + "_fuzz"] = obj.pop(key)

    return obj


def __random_key(prefix="fuzz"):
    return f"{prefix}_{''.join(random.choices(string.ascii_lowercase, k=6))}"


def __fuzz_add_key(obj: dict, probability=0.2):
    if not isinstance(obj, dict):
        return obj

    if random.random() < probability:
        obj[__random_key()] = "FUZZ_VALUE"

    return obj


def __fuzz_remove_key(obj: dict, probability=0.2):
    if not isinstance(obj, dict) or not obj:
        return obj

    if random.random() < probability:
        key = random.choice(list(obj.keys()))
        del obj[key]

    return obj


def __fuzz_yaml_file(path: Path) -> None:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    fuzzed = __fuzz_yaml(data)
    fuzzed = __fuzz_keys(fuzzed)

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(fuzzed, f, sort_keys=False)


def __pick_yaml_files(root: Path, max_files: int) -> list[Path]:
    yamls = list(root.rglob("*.yaml")) + list(root.rglob("*.yml"))
    if not yamls:
        return []
    return random.sample(yamls, k=min(max_files, len(yamls)))


def __copy_input_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)


def __fuzz_value(value: Any) -> Any:
    if isinstance(value, int):
        return value + random.randint(-10, 10)
    if isinstance(value, float):
        return value * random.uniform(0.5, 1.5)
    if isinstance(value, str):
        if value.strip() == "":
            return value
        return value + random.choice(["", "_fuzz", "XXX"])
    if isinstance(value, bool):
        return not value
    return value  # leave unknown types untouched


def __fuzz_yaml(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: __fuzz_yaml(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [__fuzz_yaml(v) for v in obj]
    return __fuzz_value(obj)


def __run_script(
    input_dir: Path,
    output_file: Path,
    package_root: Path,
    workspace: Path,
    fuzzed_fies: list[Path],
):
    script_path = str(
        package_root
        / "src"
        / "flync"
        / "sdk"
        / "helpers"
        / "validate_workspace.py"
    )
    result = subprocess.run(
        [sys.executable, script_path, str(input_dir)],
        capture_output=True,
        text=True,
        env={**os.environ, "TERM": "dumb"},
        encoding="utf-8",
    )

    output_file.write_text(
        "fuzzed fies:\n"
        + "\n".join(str(p.relative_to(workspace)) for p in fuzzed_fies)
        + "\nSTDOUT:\n"
        + result.stdout
        + "\n\nSTDERR:\n"
        + result.stderr,
        encoding="utf-8",
    )

    return result.returncode


@pytest.mark.parametrize(
    "seed",
    range(ITERATIONS),
    ids=[f"fizzy_iteration_{i}" for i in range(ITERATIONS)],
)  # 10 fuzz runs
def test_fuzzed_yaml(seed, pytestconfig, get_flync_example_path):
    random.seed(seed)

    original = Path(get_flync_example_path)
    working = current_dir / "fuzzed"
    fuzzed = working / f"iteration_{seed}"
    output_file = working / f"iteration_{seed}_output.txt"
    # cleanup iteration just in case
    if fuzzed.exists():
        shutil.rmtree(fuzzed)
    if output_file.exists():
        output_file.unlink()
    __copy_input_tree(original, fuzzed)
    # fuzz 3 random YAML files
    to_fuzz = __pick_yaml_files(fuzzed, max_files=3)
    for yaml_file in to_fuzz:
        __fuzz_yaml_file(yaml_file)

    rc = __run_script(
        fuzzed, output_file, pytestconfig.rootpath, fuzzed, to_fuzz
    )

    # Assertions depend on your expectations
    assert rc in (0, 1)  # e.g. must not crash

import shutil
import tracemalloc

import pytest
from approvaltests import Path

from flync.sdk.context.diagnostics_result import WorkspaceState
from flync.sdk.helpers.generation_helpers import dump_flync_workspace
from flync.sdk.helpers.validation_helpers import validate_workspace

__PERFORMANCE_THRESHOLDS = {
    validate_workspace.__name__: {"max_duration_ms": 3700, "max_memory_mb": 14},
    dump_flync_workspace.__name__: {"max_duration_ms": 16000, "max_memory_mb": 160},
}
current_dir = Path(__file__).resolve().parent


def __performance_assertion(api: str, duration_ms: float, memory_mb: float):
    expected = __PERFORMANCE_THRESHOLDS[api]
    assert duration_ms < expected["max_duration_ms"], f"{api} took {duration_ms}ms, exceeded {expected['max_duration_ms']}ms"
    assert memory_mb < expected["max_memory_mb"], f"{api} used {memory_mb}MB, exceeded {expected['max_memory_mb']}MB"


@pytest.mark.performance
@pytest.mark.critical_api
def test_validate_workspace_benchmark(benchmark, get_relative_flync_example_path):
    """Benchmark validate_workspace API"""

    def run_validate():
        tracemalloc.start()
        result = validate_workspace(get_relative_flync_example_path)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        memory_mb = peak / 1024 / 1024
        assert result.state in (WorkspaceState.VALID, WorkspaceState.WARNING)
        return memory_mb

    memory_mb = benchmark(run_validate)
    mean_ms = benchmark.stats["mean"] * 1000
    __performance_assertion(validate_workspace.__name__, mean_ms, memory_mb)


@pytest.mark.performance
@pytest.mark.critical_api
def test_dump_flync_workspace_benchmark(benchmark, loaded_workspace):
    """Benchmark dump_flync_workspace API"""
    ws_name = loaded_workspace.name + "_dump_flync_workspace_performance"
    output_path = Path(current_dir / "generated" / ws_name)
    if output_path.exists():
        shutil.rmtree(output_path)

    def run_dump():
        tracemalloc.start()
        dump_flync_workspace(loaded_workspace.flync_model, output_path, ws_name)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return peak / 1024 / 1024

    memory_mb = benchmark(run_dump)
    mean_ms = benchmark.stats["mean"] * 1000

    __performance_assertion(dump_flync_workspace.__name__, mean_ms, memory_mb)

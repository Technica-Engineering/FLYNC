import shutil
import time
import tracemalloc

import pytest
from approvaltests import Path

from flync.sdk.context.diagnostics_result import WorkspaceState
from flync.sdk.helpers.generation_helpers import dump_flync_workspace
from flync.sdk.helpers.validation_helpers import validate_workspace

__PERFORMANCE_THRESHOLDS = {
    validate_workspace.__name__: {"max_duration_ms": 4000, "max_memory_mb": 14},
    # Increased max duration to 25 seconds to account for the difference of computational power of different CI agents
    dump_flync_workspace.__name__: {"max_duration_ms": 25000, "max_memory_mb": 200},
}
current_dir = Path(__file__).resolve().parent


def __performance_assertion(api: str, duration_ms: float, memory_mb: float):
    expected = __PERFORMANCE_THRESHOLDS[api]
    assert duration_ms < expected["max_duration_ms"], f"{api} took {duration_ms}ms, exceeded {expected['max_duration_ms']}ms"
    assert memory_mb < expected["max_memory_mb"], f"{api} used {memory_mb}MB, exceeded {expected['max_memory_mb']}MB"


def __benchmark_duration_ms(benchmark, func):
    """Runs the benchmarked callable and returns (return_value, mean_duration_ms).

    pytest-benchmark disables itself under xdist (so ``benchmark.stats`` is ``None``),
    but still runs the callable once. Fall back to a manual timing in that case so the
    duration assertion still applies.
    """
    result = benchmark(func)
    if benchmark.stats is not None:
        return result, benchmark.stats["mean"] * 1000
    start = time.perf_counter()
    func()
    return result, (time.perf_counter() - start) * 1000


def __run_validate(path, trace_memory: bool) -> float:
    """Validate the workspace at ``path``.

    Returns the peak traced memory in MB when ``trace_memory`` is true, else 0.0.
    Memory tracing has significant overhead, so the duration metric is taken from a
    separate, tracing-free run to reflect the real cost of the API rather than the
    cost of ``tracemalloc`` itself.
    """
    if trace_memory:
        tracemalloc.start()
    result = validate_workspace(path)
    peak = 0.0
    if trace_memory:
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    assert result.state in (WorkspaceState.VALID, WorkspaceState.WARNING)
    return peak / 1024 / 1024


@pytest.mark.performance
@pytest.mark.critical_api
def test_validate_workspace_benchmark(benchmark, get_relative_flync_example_path):
    """Benchmark validate_workspace API"""

    # Warm up one-time imports/caches so the traced peak reflects steady-state memory.
    __run_validate(get_relative_flync_example_path, trace_memory=False)

    # Time a memory-tracing-free run so the duration metric reflects real code cost.
    _, mean_ms = __benchmark_duration_ms(benchmark, lambda: __run_validate(get_relative_flync_example_path, trace_memory=False))
    # Measure peak memory in a separate, untimed run.
    memory_mb = __run_validate(get_relative_flync_example_path, trace_memory=True)

    __performance_assertion(validate_workspace.__name__, mean_ms, memory_mb)


@pytest.mark.performance
@pytest.mark.critical_api
def test_dump_flync_workspace_benchmark(benchmark, loaded_workspace_with_object_map):
    """Benchmark dump_flync_workspace API"""
    loaded_workspace = loaded_workspace_with_object_map
    ws_name = loaded_workspace.name + "_dump_flync_workspace_performance"
    output_path = Path(current_dir / "generated" / ws_name)
    if output_path.exists():
        shutil.rmtree(output_path)

    def run_dump(trace_memory: bool) -> float:
        if trace_memory:
            tracemalloc.start()
        dump_flync_workspace(loaded_workspace.flync_model, output_path, ws_name)
        peak = 0.0
        if trace_memory:
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        return peak / 1024 / 1024

    # Time a memory-tracing-free run; measure peak memory in a separate, untimed run.
    _, mean_ms = __benchmark_duration_ms(benchmark, lambda: run_dump(trace_memory=False))
    memory_mb = run_dump(trace_memory=True)

    __performance_assertion(dump_flync_workspace.__name__, mean_ms, memory_mb)

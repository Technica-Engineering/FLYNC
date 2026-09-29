"""Automated hot-path profiler for the FLYNC SDK public API surface.

Profiles each SDK API entry point under :mod:`cProfile`, converts the captured
call statistics into an inline SVG flame graph, then writes a combined HTML
index alongside the raw ``.prof`` files and hot-path ``.txt`` tables into an
artifact directory.

This is the engine behind the FLYNC SDK profiling pipeline. It is advisory:
it never fails the build, it only publishes the report.

Run from the repository root through the project environment::

    uv run python scripts/ci/profile_sdk_apis.py

The report is written to ``profiler_reports/`` by default (override with the
``FLYNC_PROFILER_OUT`` environment variable).
"""

from __future__ import annotations

import cProfile
import hashlib
import io
import os
import shutil
import sys
import tempfile
from collections import deque
from pathlib import Path
from pstats import Stats
from typing import Optional

from flync.sdk.context.workspace_config import WorkspaceConfiguration

# ---------------------------------------------------------------------------
# Paths & environment
# ---------------------------------------------------------------------------

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]
EXAMPLE_DIR = REPO_ROOT / "examples" / "flync_example"

DEFAULT_OUT_DIR = REPO_ROOT / "profiler_reports"


def _norm(p) -> str:
    """Normalize a filesystem path to forward slashes for stable comparisons."""
    return str(p).replace("\\", "/")


# Frames that belong to this runner (the closures we call through) are noise:
# drop them so the flame tree starts at the actual SDK API call.
_RUNNER_REL = _norm(THIS_FILE).lower()


def _out_dir() -> Path:
    return Path(os.environ.get("FLYNC_PROFILER_OUT", DEFAULT_OUT_DIR))


# ---------------------------------------------------------------------------
# Profiling wrappers
# ---------------------------------------------------------------------------


CO_VARKEYWORDS = 0x08


def _is_runner_frame(frame) -> bool:
    """True when ``frame`` belongs to this runner script (the workload closures)."""
    fname = _norm(frame.f_code.co_filename).lower()
    return fname == _RUNNER_REL


def _code_defaults(frame) -> dict:
    """Resolve a callee frame's parameter defaults via ``inspect.signature``.

    The code object in this environment strips ``co_defaults``/``co_kwdefaults``
    (and hides defaults in ``co_consts``), so defaults are recovered by resolving
    the callable from the frame's globals (by ``co_qualname``) and reading its
    signature. Generic — nothing about a specific API is hardcoded here.
    """
    try:
        import inspect

        frame_globals = frame.f_globals or {}
        qualname = frame.f_code.co_qualname
        name = frame.f_code.co_name
        if "." in qualname:
            cls_name, method = qualname.split(".", 1)
            cls = frame_globals.get(cls_name)
            if cls is None:
                return {}
            func = getattr(cls, method, None)
        else:
            func = frame_globals.get(name)
        if func is None:
            return {}
        sig = inspect.signature(func)
        return {p.name: p.default for p in sig.parameters.values() if p.default is not inspect.Parameter.empty}
    except Exception:  # noqa: BLE001 - defaults are a nicety, never fatal
        return {}


def _same_value(a, b) -> bool:
    if type(a) is not type(b):
        return False
    try:
        return a == b
    except Exception:  # noqa: BLE001 - a failing comparison just means "not default"
        return False


def _fmt_str(v: str) -> str:
    if "/" in v and len(v) > 30:
        return "'…/…/" + v.rsplit("/", 1)[-1] + "'"
    if len(v) > 72:
        return "'" + v[:69] + "…'"
    return "'" + v + "'"


def _fmt_seq(v) -> str:
    items = [_fmt_value(x) for x in v]
    joined = ", ".join(items)
    if len(joined) > 80:
        joined = ", ".join(items[:3]) + ", …"
    open_b, close_b = ("[", "]") if isinstance(v, list) else ("(", ")")
    return open_b + joined + close_b


def _fmt_value(v) -> str:
    """Render one captured argument as a short, human string."""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return _fmt_str(v)
    if isinstance(v, (list, tuple)):
        return _fmt_seq(v)
    if isinstance(v, Path):
        return "'…/" + v.name + "'"
    if isinstance(v, type):
        return v.__name__
    return "…"


def _format_call_str(fallback_name: str, func_name, args: dict, defaults: dict) -> str:
    if not func_name:
        return f"{fallback_name}()"
    kept = []
    for k, v in args.items():
        if k in defaults and _same_value(v, defaults[k]):
            continue
        kept.append(f"{k}={_fmt_value(v)}")
    return f"{func_name}({', '.join(kept)})"


def _capture_first_flync_call(frame, captured: dict) -> None:
    """Record the call leaving the runner into FLYNC, then stop tracing."""
    caller = frame.f_back
    if caller is None or not _is_runner_frame(caller) or not _is_flync(frame.f_code.co_filename):
        return
    varnames = frame.f_code.co_varnames
    argc = frame.f_code.co_argcount
    locals_ = frame.f_locals
    args = {k: locals_.get(k) for k in varnames[:argc] if k not in ("self", "cls")}
    if frame.f_code.co_flags & CO_VARKEYWORDS:
        kw = locals_.get(varnames[argc])
        if isinstance(kw, dict):
            args.update(kw)
    captured["name"] = frame.f_code.co_name
    captured["args"] = args
    captured["defaults"] = _code_defaults(frame)
    sys.settrace(None)


def _profile_call(workload, profile_name: str, out: Path):
    """Profile ``workload``, write ``<out>.prof``, and return Stats + an error.

    cProfile drives tracing through ``sys.setprofile``; we piggyback the separate
    ``sys.settrace`` hook only long enough to observe the *first* call that leaves
    the runner and enters FLYNC code — the public SDK entry. Its name and bound
    arguments (minus ``self``/``cls``, defaults suppressed) become the report's
    ``call_str``, so the subtitle is derived from the live call, never hardcoded.
    The trace removes itself right after that entry, so overhead is negligible.
    """
    profiler = cProfile.Profile()
    error = None
    captured: dict = {}

    def tracer(frame, event, arg):
        if event == "call":
            _capture_first_flync_call(frame, captured)
        return tracer

    try:
        profiler.enable()
        try:
            sys.settrace(tracer)
            try:
                workload()
            finally:
                sys.settrace(None)
        except Exception as exc:  # noqa: BLE001 - capture any failure, keep profiling
            error = f"{type(exc).__name__}: {exc}"
        finally:
            profiler.disable()
    finally:
        stats = Stats(profiler)
        stats.dump_stats(str(out))

    call_str = _format_call_str(profile_name, captured.get("name"), captured.get("args", {}), captured.get("defaults", {}))
    return stats, error, call_str


def _relative_frame(path: str) -> str:
    try:
        return _norm(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return path


def _clean_frame_name(func) -> str:
    """Strip the ``{...}`` size annotations cProfile appends to frame names."""
    return str(func).replace("{", "").replace("}", "").strip()


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _is_flync(path: str) -> bool:
    """True when a frame belongs to FLYNC code.

    Matches the ``flync`` package whether it is resolved from the source
    checkout (``src/flync/``), an installed wheel (``.../site-packages/flync/``)
    or the bundled example workspaces (``examples/``). Everything else - the
    stdlib, third-party site-packages (pydantic, yaml, ...) and the interpreter
    - is treated as "external" so the report can offer a FLYNC-only view that
    hides that noise.
    """
    rel = _norm(_relative_frame(path)).lower()
    if rel.startswith(("src/flync/", "examples/")):
        return True
    parts = rel.split("/")
    return "site-packages" in parts and "flync" in parts


# ---------------------------------------------------------------------------
# Call tree construction
# ---------------------------------------------------------------------------


def _build_tree(stats: Stats):
    """Collapse a cProfile call graph into a cycle-safe single-parent tree.

    Returns ``(roots, children, cumtime, tottime)``. Each function is given
    exactly one parent so the flame/SVG output stays linear instead of
    exploding combinatorially over every stack path.

    A frame shared between several callers (e.g. ``generate_configs`` invoked
    both directly by a workload and from inside a save helper) is attached to
    its *shallowest* caller (closest to a root, ties broken toward the caller
    that contributed the most time). That keeps shared helpers visible next to
    the public API instead of being buried under whichever caller happened to
    dominate, and makes the layout stable from run to run.
    """
    data = stats.stats  # {(filename, lineno, func): (cc, nc, tt, ct, callers)}

    def keep(key) -> bool:
        filename, _, _func = key
        return not _norm(filename).lower().startswith(_RUNNER_REL)

    entries = {k: v for k, v in data.items() if keep(k)}
    cumtime = {k: float(v[3]) for k, v in entries.items()}
    tottime = {k: float(v[2]) for k, v in entries.items()}

    def callers_of(key):
        return [c for c in entries[key][4] if keep(c)]

    def callees_of(key):
        # Reverse lookup: every entry that has `key` in its callers dict.
        return [c for c in entries if key in entries[c][4]]

    # Per-frame "distance from a root", found with a single BFS over the call
    # graph. First-visit-only so self-recursion can never grow the depth.
    depth: dict = {}
    queue: deque = deque()
    for root in [k for k in entries if not callers_of(k)]:
        depth[root] = 0
        queue.append(root)
    while queue:
        key = queue.popleft()
        for callee in callees_of(key):
            if callee not in depth:
                depth[callee] = depth[key] + 1
                queue.append(callee)

    parents = {}
    for key, (_cc, _nc, _tt, _ct, callers) in entries.items():
        candidates = [c for c in callers if keep(c)]
        if not candidates:
            continue
        # Prefer the shallowest caller; break ties toward the one that
        # contributed the most inclusive time to this frame.
        parents[key] = min(candidates, key=lambda c: (depth.get(c, 10**9), -callers[c][3]))

    children: dict = {}
    for key, parent in parents.items():
        children.setdefault(parent, []).append(key)

    roots = [k for k in entries if k not in parents]

    # Make sure every node is reachable from some root (parent maps can leave
    # small cycles/isolated nodes unreachable).
    reached: set = set()
    stack = list(roots)
    while stack:
        node = stack.pop()
        if node in reached:
            continue
        reached.add(node)
        stack.extend(children.get(node, []))

    roots.extend(k for k in entries if k not in reached)
    return roots, children, cumtime, tottime


# ---------------------------------------------------------------------------
# Hot-path text table
# ---------------------------------------------------------------------------


def _hot_path_text(stats: Stats, profile_name: str) -> str:
    out = io.StringIO()
    out.write(f"Hot path for {profile_name}\n")
    out.write("=" * 78 + "\n\n")
    out.write("Top 25 functions by cumulative time (inclusive):\n")
    stats.sort_stats("cumtime")
    stats.stream = out
    stats.print_stats(25)
    out.write("\nTop 25 functions by own time (exclusive):\n")
    stats.sort_stats("tottime")
    stats.stream = out
    stats.print_stats(25)
    return out.getvalue()


# ---------------------------------------------------------------------------
# SVG flame graph from cumulative time
# ---------------------------------------------------------------------------

_ROW_H = 18
_PADDING = 22


def _color_for(label: str) -> str:
    h = int(hashlib.md5(label.encode()).hexdigest()[:6], 16) % 360
    return f"hsl({h} 45% 45%)"


def _flame_label(key) -> str:
    _fn, _ln, func = key
    return _clean_frame_name(func)


def _flame_full(key) -> str:
    fn, ln, _func = key
    return f"{_flame_label(key)} ({_relative_frame(fn)}:{ln})"


def _expand_children(stack, key, alloc, level, x, children, cumtime) -> None:
    """Offset a node's children to partition its allocation, then queue them."""
    child_list = sorted(children.get(key, []), key=lambda c: float(cumtime[c]), reverse=True)
    total_child = sum(float(cumtime[c]) for c in child_list)
    if total_child <= 0.0:
        return
    factor = min(1.0, alloc / total_child) if alloc > 0.0 else 0.0
    entries = []
    off = 0.0
    for child in child_list:
        child_alloc = float(cumtime[child]) * factor
        entries.append((child, child_alloc, x + off))
        off += child_alloc
    for child, child_alloc, child_x in reversed(entries):
        stack.append((child, child_alloc, level + 1, child_x))


def _renormalize(records):
    """Shift rows so the shallowest FLYNC frame sits on level 0."""
    if not records:
        return records
    base = min(r[1] for r in records)
    if not base:
        return records
    return [(x, level - base, width, name, title) for x, level, width, name, title in records]


def _flame_records(stats: Stats, flync_only: bool = False):
    """Yield (x, level, width, label, title) for every frame.

    Widths are normalized inclusive times. cProfile's ``cumtime`` is the total
    time a frame was on the stack across *all* call paths, but the flame tree
    assigns each frame a single parent ``_build_tree`` - so raw ``cumtime`` can
    exceed a parent's box and bleed into (overlap) a sibling. Each node's
    children are scaled to partition their parent's allocation exactly, so bars
    always nest inside their parent and never overlap.
    """
    roots, children, cumtime, _tottime = _build_tree(stats)

    records: list = []
    seen: set = set()
    base_x = 0.0
    for root in roots:
        stack: list[tuple] = [(root, float(cumtime[root]), 0, base_x)]
        while stack:
            key, alloc, level, x = stack.pop()
            if key in seen:
                continue
            seen.add(key)
            if not (flync_only and not _is_flync(key[0])):
                records.append((x, level, alloc, _flame_label(key), _flame_full(key)))
            _expand_children(stack, key, alloc, level, x, children, cumtime)
        base_x += float(cumtime[root])

    return _renormalize(records) if flync_only else records


def _flame_svg(stats: Stats, total_seconds: float, flync_only: bool = False) -> str:
    records = _flame_records(stats, flync_only)
    width_px = 1000.0
    max_level = max((r[1] for r in records), default=0)
    height_px = max_level * _ROW_H + 2 * _PADDING + 4
    scale = width_px / total_seconds if total_seconds else 1.0

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(width_px) + 4}" '
        f'height="{int(height_px) + 4}" viewBox="0 0 {int(width_px) + 4} {int(height_px) + 4}" '
        f'data-total="{total_seconds:g}">',
        f'<rect class="bg" x="0" y="0" width="{int(width_px) + 4}" height="{int(height_px) + 4}" fill="#141414"/>',
    ]

    for x, level, width, label_, title in records:
        w = max(width * scale, 0.0)
        if w < 0.5:
            continue
        px = x * scale + 2
        py = level * _ROW_H + _PADDING
        fill = _color_for(label_)
        label_text = f"{label_} · {width * 1000:.1f}ms"
        show_label = w > len(label_text) * 6.6 + 10 and w > 24
        text = ""
        if show_label:
            text = (
                f'<text class="fbar-text" x="{px + 3:.1f}" y="{py + 13:.1f}" font-family="sans-serif" '
                f'font-size="11" fill="#fff">{_esc(label_text)}</text>'
            )
        _file = ""
        _line = ""
        if " (" in title and title.endswith(")"):
            _inner = title.rsplit("(", 1)[1][:-1]
            _file, _sep, _line = _inner.rpartition(":")
            if not _sep:
                _file, _line = _inner, ""
        parts.append(
            f'<g class="fbar" data-x="{x:.6g}" data-w="{width:.6g}" data-level="{level}" '
            f'data-color="{fill}" data-label="{_esc(label_)}" data-file="{_esc(_file)}" data-line="{_esc(_line)}">'
            f'<rect class="fbar-rect" x="{px:.1f}" y="{py}" width="{w:.1f}" height="{_ROW_H - 2}" '
            f'fill="{fill}" stroke="#0b0b0b" stroke-width="0.5"></rect>'
            f"{text}</g>"
        )

    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# API workloads
# ---------------------------------------------------------------------------

_SCRATCH_DIRS: list[Path] = []

WORKSPACE_OBJECT_API = "Workspace object API"


class ProfilerContext:
    _instance: Optional[ProfilerContext] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent reinitialization if already created
        if getattr(self, "_initialized", False):
            return
        self.ws: Optional[FLYNCWorkspace] = None
        self.model: Optional[FLYNCModel] = None
        self.object_id: Optional[str] = None
        self.referencing_obj_id: str = "ecus.eth_ecu.ports.ports.eth_ecu_p1"
        self.referenced_obj_id: str = "ecus.high_performance_compute.topology.connections.2.ecu_port"
        self.loaded: bool = False
        self._initialized = True

    def ensure_loaded(self, ws_root: Path) -> ProfilerContext:
        if not self.loaded:
            ws = FLYNCWorkspace.safe_load_workspace("ws", ws_root, workspace_config=WorkspaceConfiguration(map_objects=True))
            self.ws = ws
            self.model = ws.flync_model
            self.object_id = self._get_duplicate_object_id(ws)
            self.loaded = True
        return self

    @staticmethod
    def _get_duplicate_object_id(ws):
        _, dup_ids = next(iter((ws._duplicated_objects_ids or {}).items()))
        if dup_ids:
            return dup_ids[0]

        ids = ws.list_objects()
        return ids[0] if ids else None


def _scratch_copy() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="flync_profiler_"))
    _SCRATCH_DIRS.append(tmp)
    shutil.copytree(EXAMPLE_DIR, tmp / "ws", dirs_exist_ok=True)
    return tmp


def _build_workloads():
    # Profile against a private temp snapshot of the example, never the checkout
    # itself: the SDK persists `.flync/config.yaml` (and generated files) into a
    # workspace on load, so pointing it at the repo would dirty the tree.
    work = _scratch_copy()
    ws_root = work / "ws"
    ctx = ProfilerContext().ensure_loaded(ws_root)

    def gen_path(kind: str) -> Path:
        p = work / kind
        p.mkdir(parents=True, exist_ok=True)
        return p

    def workload_validate_workspace():
        validate_workspace(ws_root)

    def workload_validate_external_node():
        validate_external_node(FLYNCModel, ws_root)

    def workload_validate_node():
        validate_node(ws_root)

    def workload_dump_flync_workspace():
        dump_flync_workspace(ctx.model, gen_path("dump"), "dump_ws")

    def workload_generate_external_node():
        generate_external_node(ECUPort, gen_path("gen_external"))

    def workload_generate_node():
        generate_node(ctx.ws, ["ecus.eth_ecu.ports"], name="profile_port")

    def workload_available_flync_nodes():
        available_flync_nodes()

    def workload_type_from_input():
        type_from_input("FLYNCModel")

    def workload_load_model():
        FLYNCWorkspace.load_model(ctx.model, "load_model_ws", gen_path("load_model"))

    def workload_safe_load_workspace():
        FLYNCWorkspace.safe_load_workspace("safe_load_ws", _scratch_copy() / "ws", workspace_config=WorkspaceConfiguration(map_objects=True))

    def workload_list_objects():
        ctx.ws.list_objects()

    def workload_get_object():
        ctx.ws.get_object(ctx.object_id)

    def workload_get_metadata():
        ctx.ws.get_metadata(ctx.object_id)

    def workload_get_child_ids():
        ctx.ws.get_child_ids(ctx.object_id)

    def workload_get_references_of():
        ctx.ws.get_references_of(ctx.referencing_obj_id)

    def workload_objects_at():
        uri = next(iter(ctx.ws.documents))
        ctx.ws.objects_at(uri, 0, 0)

    def workload_get_source():
        ctx.ws.get_source(ctx.object_id)

    def workload_update_document():
        uri = next(iter(ctx.ws.documents))
        ctx.ws.update_document(uri)

    def workload_generate_configs():
        ctx.ws.generate_configs()

    return [
        ("validate_workspace", "Validation", workload_validate_workspace),
        ("validate_external_node", "Validation", workload_validate_external_node),
        ("validate_node", "Validation", workload_validate_node),
        ("dump_flync_workspace", "Generation", workload_dump_flync_workspace),
        ("generate_external_node", "Generation", workload_generate_external_node),
        ("generate_node", "Generation", workload_generate_node),
        ("available_flync_nodes", "Node helpers", workload_available_flync_nodes),
        ("type_from_input", "Node helpers", workload_type_from_input),
        ("load_model", "Workspace load", workload_load_model),
        ("safe_load_workspace", "Workspace load", workload_safe_load_workspace),
        ("list_objects", WORKSPACE_OBJECT_API, workload_list_objects),
        ("get_object", WORKSPACE_OBJECT_API, workload_get_object),
        ("get_metadata", WORKSPACE_OBJECT_API, workload_get_metadata),
        ("get_child_ids", WORKSPACE_OBJECT_API, workload_get_child_ids),
        ("get_references_of", WORKSPACE_OBJECT_API, workload_get_references_of),
        ("objects_at", WORKSPACE_OBJECT_API, workload_objects_at),
        ("get_source", WORKSPACE_OBJECT_API, workload_get_source),
        ("update_document", WORKSPACE_OBJECT_API, workload_update_document),
        ("generate_configs", WORKSPACE_OBJECT_API, workload_generate_configs),
    ]


# ---------------------------------------------------------------------------
# Combined HTML index
# ---------------------------------------------------------------------------


def _index_page(profiles) -> str:
    cards = []
    for name, group, call_str, svg_all, svg_flync, summary_ms in profiles:
        cards.append(
            f'<section class="card" data-group="{group}">'
            f'<div class="card-head">'
            f'<h2>{name}<span class="ms">{summary_ms:.2f} ms CPU</span></h2>'
            f'<div class="toolbar">'
            f'<span class="switch" role="group" aria-label="frame filter">'
            f'<button type="button" data-view="all">All frames</button>'
            f'<button type="button" data-view="flync" class="active">FLYNC only</button>'
            f"</span>"
            f'<button class="zbtn" type="button">Reset zoom</button>'
            f"</div>"
            f"</div>"
            f'<div class="call">{_esc(call_str)}</div>'
            f'<div class="svg" data-view="all">{svg_all}</div>'
            f'<div class="svg" data-view="flync">{svg_flync}</div>'
            f'<div class="bar-info" role="status" aria-live="polite"></div></section>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FLYNC SDK hot-path profiler report</title>
<style>
  :root {{
    --bg: #08090A; --s1: #16171C; --s2: #1E1F25; --s3: #26272E;
    --line: rgba(255,255,255,0.06); --line-strong: rgba(255,255,255,0.10);
    --txt: #F7F8F8; --txt2: #9CA3AF; --txt3: #6B7280;
    --accent: #5B8DEF; --accent-dim: #3b6fd4;
    --r-sm: 6px; --r-md: 12px;
    --ease: cubic-bezier(0.22, 1, 0.36, 1);
    --mono: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo, Consolas, monospace;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--txt);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif; font-size: 14px; line-height: 1.5; }}
  header {{ position: sticky; top: 0; z-index: 20; padding: 16px 28px; background: color-mix(in srgb, var(--bg) 88%, transparent);
    backdrop-filter: blur(10px); border-bottom: 1px solid var(--line); }}
  h1 {{ margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -0.02em; }}
  header p {{ margin: 6px 0 0; color: var(--txt2); font-size: 13px; max-width: 900px; }}
  header code {{ font-family: var(--mono); font-size: 12px; color: var(--accent); background: var(--s2); padding: 1px 5px; border-radius: 4px; }}
  .filters {{ position: sticky; top: 86px; z-index: 15; padding: 10px 28px; background: color-mix(in srgb, var(--bg) 94%, transparent);
    backdrop-filter: blur(8px); border-bottom: 1px solid var(--line); }}
  .filters button {{ background: var(--s2); color: var(--txt2); border: 1px solid var(--line-strong); border-radius: 999px;
    padding: 5px 14px; margin: 0 6px 0 0; cursor: pointer; font-size: 12.5px; transition: all .15s var(--ease); }}
  .filters button:hover {{ color: var(--txt); border-color: var(--txt3); }}
  .filters button.active {{ background: color-mix(in srgb, var(--accent) 22%, var(--s2)); color: var(--txt); border-color: var(--accent); }}
  .card {{ margin: 16px 28px; padding: 16px 18px; background: var(--s1); border: 1px solid var(--line);
    border-radius: var(--r-md); box-shadow: 0 1px 2px rgba(0,0,0,0.3); }}
  .card[hidden] {{ display: none; }}
  .card-head {{ display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }}
  .card h2 {{ margin: 0; font-size: 15px; font-weight: 600; letter-spacing: -0.01em; }}
  .card h2 .ms {{ color: var(--txt3); font-weight: 400; font-size: 12.5px; margin-left: 10px; font-family: var(--mono); }}
  .call {{ margin: -2px 0 10px; color: var(--accent); font-family: var(--mono); font-size: 12px;
    overflow-x: auto; white-space: nowrap; padding: 4px 8px; background: var(--s2); border: 1px solid var(--line);
    border-radius: var(--r-sm); }}
  .bar-info {{ min-height: 40px; margin-top: 10px; padding: 9px 10px; font-family: var(--mono); font-size: 12.5px;
    color: var(--txt); background: var(--s2); border: 1px solid var(--line); border-radius: var(--r-sm);
    display: flex; flex-wrap: wrap; align-items: center; gap: 6px 18px; }}
  .bar-info::before {{ content: "Hover a bar to inspect"; color: var(--txt3); }}
  .bar-info:not(:empty)::before {{ content: none; }}
  .bar-info b {{ color: var(--txt2); font-weight: 500; }}
  .bar-info .fn {{ color: var(--txt); font-weight: 600; letter-spacing: -0.01em; }}
  .bar-info .loc {{ color: var(--txt3); font-size: 11.5px; }}
  .toolbar {{ display: flex; align-items: center; gap: 10px; }}
  .switch {{ display: inline-flex; background: var(--s2); border: 1px solid var(--line-strong); border-radius: var(--r-sm); padding: 2px; }}
  .switch button {{ background: transparent; border: 0; color: var(--txt3); padding: 4px 12px; border-radius: 4px;
    cursor: pointer; font-size: 12.5px; transition: all .15s var(--ease); }}
  .switch button.active {{ background: var(--accent); color: #fff; }}
  .zbtn {{ background: var(--s2); color: var(--txt2); border: 1px solid var(--line-strong); border-radius: var(--r-sm);
    padding: 6px 12px; cursor: pointer; font-size: 12.5px; transition: all .15s var(--ease); }}
  .zbtn:hover {{ color: var(--txt); border-color: var(--txt3); }}
  .svg[data-view="all"] {{ display: none; }}
  .svg {{ max-width: 100%; overflow: hidden; }}
  .svg svg {{ max-width: 100%; height: auto; display: block; background: var(--bg);
    border: 1px solid var(--line); border-radius: var(--r-sm); }}
  .fbar rect {{ cursor: pointer; transition: filter .12s var(--ease); }}
  .fbar:hover rect {{ filter: brightness(1.18); }}
  .fbar text {{ font-family: var(--mono); font-size: 11px; pointer-events: none; }}
  footer {{ padding: 18px 28px 28px; color: var(--txt3); font-size: 12px; border-top: 1px solid var(--line); }}
  @media (prefers-reduced-motion: reduce) {{
    * {{ transition: none !important; }}
  }}
</style>
</head>
<body>
<header>
  <h1>FLYNC SDK · API hot-path profiler</h1>
  <p>Bar widths are inclusive time; labels carry cumulative ms. <b>Click any bar</b> to zoom into its
  children — the ancestor path stays visible (dimmed) on top, and clicking one zooms back out. Use
  <b>All frames / FLYNC only</b> to show or hide stdlib/third-party frames, and <b>Reset zoom</b> to
   return to the full view. Report generated against the bundled example <code>examples/flync_example</code>.</p>
</header>
<div class="filters" id="filters">
  <button class="active" data-group="all">All</button>
  <button data-group="Validation">Validation</button>
  <button data-group="Generation">Generation</button>
  <button data-group="Node helpers">Node helpers</button>
  <button data-group="Workspace load">Workspace load</button>
  <button data-group="{WORKSPACE_OBJECT_API}">{WORKSPACE_OBJECT_API}</button>
</div>
{''.join(cards)}
<footer>Generated by scripts/ci/profile_sdk_apis.py</footer>
<script>
  function flameD (g) {{
    return {{ x: parseFloat(g.dataset.x) || 0,
              w: parseFloat(g.dataset.w) || 0,
              lvl: parseInt(g.dataset.level, 10) || 0 }};
  }}
  function setLabel (g, txt, x, y, tc) {{
    var t = g.querySelector('text.fbar-text');
    if (!t) {{
      var ns = 'http://www.w3.org/2000/svg';
      t = document.createElementNS(ns, 'text');
      t.setAttribute('class', 'fbar-text');
      g.appendChild(t);
    }}
    t.setAttribute('x', x); t.setAttribute('y', y); t.setAttribute('fill', tc);
    t.textContent = txt;
  }}
  function removeLabel (g) {{
    var t = g.querySelector('text.fbar-text');
    if (t) t.remove();
  }}
  function render (svg) {{
    var bars = svg.querySelectorAll('.fbar');
    var total = parseFloat(svg.dataset.total) || 0;
    var FULLW = 1000, PADX = 2, ROWH = 18, PAD = 22;
    var sel = svg._sel;
    var eps = 1e-6, specs = [], ancList = [], i, base = 0;
    if (sel) {{
      var sd = flameD(sel), sx = sd.x, sw = sd.w, sx2 = sx + sw, sLvl = sd.lvl;
      for (i = 0; i < bars.length; i++) {{
        var g = bars[i], d = flameD(g);
        var isAnc = d.lvl < sLvl && d.x <= sx + eps && d.x + d.w >= sx2 - eps;
        var isDesc = d.lvl > sLvl && d.x >= sx - eps && d.x + d.w <= sx2 + eps;
        var self = g === sel;
        var s = {{ g: g, d: d, vis: false, anc: false, row: 0, x: 0, w: 0, col: '', tc: '#9CA3AF', dlvl: d.lvl }};
        if (isAnc) {{ s.vis = true; s.anc = true; ancList.push(s); }}
        else if (self || isDesc) {{
          s.vis = true;
          s.x = (d.x - sx) / sw * FULLW + PADX;
          s.w = d.w / sw * FULLW;
          s.col = g.dataset.color; s.tc = '#E9EAEE';
        }}
        specs.push(s);
      }}
      ancList.sort(function (a, b) {{ return a.d.lvl - b.d.lvl; }});
      base = ancList.length;
      ancList.forEach(function (s, idx) {{
        s.row = idx; s.x = PADX; s.w = FULLW;
        s.col = '#26272E'; s.tc = '#9CA3AF';
      }});
      specs.forEach(function (s) {{ if (s.vis && !s.anc) s.row = base + (s.dlvl - sLvl); }});
    }} else {{
      for (i = 0; i < bars.length; i++) {{
        var g = bars[i], d = flameD(g);
        specs.push({{ g: g, d: d, vis: true, anc: false, row: d.lvl,
          x: d.x / total * FULLW + PADX, w: d.w / total * FULLW,
          col: g.dataset.color, tc: '#E9EAEE', dlvl: d.lvl }});
      }}
    }}
    var maxRow = 0;
    specs.forEach(function (s) {{ if (s.vis && s.row > maxRow) maxRow = s.row; }});
    var newH = maxRow * ROWH + 2 * PAD + 4;
    svg.setAttribute('height', newH);
    svg.setAttribute('viewBox', '0 0 1004 ' + newH);
    var bg = svg.querySelector('rect.bg');
    if (bg) bg.setAttribute('height', newH);
    specs.forEach(function (s) {{
      if (!s.vis) {{ s.g.style.display = 'none'; removeLabel(s.g); return; }}
      s.g.style.display = '';
      var y = s.row * ROWH + PAD;
      var rect = s.g.querySelector('rect.fbar-rect');
      rect.setAttribute('x', s.x); rect.setAttribute('y', y);
      rect.setAttribute('width', s.w); rect.setAttribute('fill', s.col);
      var txt = s.g.dataset.label + ' · ' + (parseFloat(s.g.dataset.w) * 1000).toFixed(1) + 'ms';
      if (s.w > txt.length * 6.6 + 10 && s.w > 24) {{ setLabel(s.g, txt, s.x + 3, y + 13, s.tc); }}
      else {{ removeLabel(s.g); }}
    }});
  }}
  document.querySelectorAll('.filters button').forEach(function (b) {{
    b.addEventListener('click', function () {{
      var btns = document.querySelectorAll('.filters button');
      btns.forEach(function (x) {{ x.classList.remove('active'); }});
      b.classList.add('active');
      var g = b.dataset.group;
      document.querySelectorAll('.card').forEach(function (c) {{
        c.hidden = g !== 'all' && c.dataset.group !== g;
      }});
    }});
  }});
  document.querySelectorAll('.switch').forEach(function (t) {{
    var card = t.closest('.card');
    t.querySelectorAll('button').forEach(function (b) {{
      b.addEventListener('click', function () {{
        t.querySelectorAll('button').forEach(function (x) {{ x.classList.remove('active'); }});
        b.classList.add('active');
        var v = b.dataset.view;
        card.querySelectorAll('.svg').forEach(function (s) {{
          s.style.display = s.dataset.view === v ? 'block' : 'none';
          var svg = s.querySelector('svg');
          svg._sel = null;
          render(svg);
        }});
      }});
    }});
  }});
  document.querySelectorAll('.zbtn').forEach(function (btn) {{
    btn.addEventListener('click', function () {{
      var card = btn.closest('.card');
      card.querySelectorAll('svg').forEach(function (svg) {{ svg._sel = null; render(svg); }});
    }});
  }});
  document.querySelectorAll('.svg svg').forEach(function (svg) {{
    var card = svg.closest('.card');
    var info = card ? card.querySelector('.bar-info') : null;
    svg.querySelectorAll('.fbar').forEach(function (g) {{
      g.addEventListener('click', function (ev) {{
        svg._sel = g;
        render(svg);
        ev.stopPropagation();
      }});
      g.addEventListener('mouseover', function () {{
        if (!info) return;
        var w = parseFloat(g.dataset.w) || 0;
        var total = parseFloat(svg.dataset.total) || 0;
        var ms = (w * 1000).toFixed(2);
        var pct = total ? (w / total * 100).toFixed(2) : '0.00';
        var fn = document.createElement('span');
        fn.className = 'fn';
        fn.textContent = 'function: ' + (g.dataset.label || '');
        var loc = document.createElement('span');
        loc.className = 'loc';
        var locTxt = g.dataset.file ? g.dataset.file + ':' + g.dataset.line : '(external)';
        loc.textContent = 'at ' + locTxt;
        var t = document.createElement('b'); t.textContent = ms + ' ms';
        var pc = document.createElement('b'); pc.textContent = pct + '% of total';
        info.textContent = '';
        info.appendChild(fn);
        info.appendChild(loc);
        info.appendChild(t);
        info.appendChild(pc);
      }});
      g.addEventListener('mouseleave', function () {{
        if (info) info.textContent = '';
      }});
    }});
    render(svg);
  }});
</script>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    out = _out_dir()
    out.mkdir(parents=True, exist_ok=True)

    print(f"Profiling SDK APIs against {EXAMPLE_DIR}\n  output: {out}")

    # imports are deferred so the script can print a useful error if the
    # project is not installed
    global FLYNCWorkspace, FLYNCModel, validate_workspace, validate_external_node
    global validate_node, dump_flync_workspace, generate_external_node
    global generate_node, available_flync_nodes, type_from_input, ECUPort

    from flync.model import FLYNCModel  # noqa: E402
    from flync.model.flync_4_ecu import ECUPort  # noqa: E402
    from flync.sdk.helpers.generation_helpers import (  # noqa: E402
        dump_flync_workspace,
        generate_external_node,
        generate_node,
    )
    from flync.sdk.helpers.nodes_helpers import available_flync_nodes, type_from_input  # noqa: E402
    from flync.sdk.helpers.validation_helpers import (  # noqa: E402
        validate_external_node,
        validate_node,
        validate_workspace,
    )
    from flync.sdk.workspace.flync_workspace import FLYNCWorkspace  # noqa: E402

    workloads = _build_workloads()

    # Optional filter: export FLYNC_PROFILER_APIS="api1,api2" to profile a subset.
    filter_csv = os.environ.get("FLYNC_PROFILER_APIS", "")
    if filter_csv:
        allowed = {a.strip() for a in filter_csv.split(",") if a.strip()}
        workloads = [w for w in workloads if w[0] in allowed]

    counters = {}

    # Guard against any workload writing relative paths into the repo: run with
    # the CWD redirected to a throwaway temp dir so a misbehaving API defaults to
    # writing *there* instead of the checkout.
    run_cwd = Path(tempfile.mkdtemp(prefix="flync_profiler_cwd_"))
    old_cwd = Path.cwd()
    os.chdir(run_cwd)
    try:
        for name, group, workload in workloads:
            prof_path = out / f"{name}.prof"
            stats, error, call_str = _profile_call(workload, name, prof_path)

            roots, _children, cumtime, _tottime = _build_tree(stats)
            total = max((cumtime[r] for r in roots), default=0.0)

            (out / f"{name}.txt").write_text(_hot_path_text(stats, name), encoding="utf-8")
            svg_all = _flame_svg(stats, total, flync_only=False)
            svg_flync = _flame_svg(stats, total, flync_only=True)
            counters[name] = (group, call_str, svg_all, svg_flync, total, error)
            print(f"  [{group}] {name:.<28} {total:>9.3f} s CPU" + (f"  (raised: {error})" if error else ""))
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(run_cwd, ignore_errors=True)
        for d in _SCRATCH_DIRS:
            shutil.rmtree(d, ignore_errors=True)

    # Build combined index
    profiles = [
        (name, group, call_str, svg_all, svg_flync, seconds * 1000.0)
        for name, (group, call_str, svg_all, svg_flync, seconds, _err) in counters.items()
    ]
    (out / "index.html").write_text(_index_page(profiles), encoding="utf-8")

    print(f"\nDone. Report: {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

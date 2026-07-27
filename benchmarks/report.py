# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Run every ``bench_*.py`` in its own environment and render the report.

Each benchmark is a separate PEP 723 script because the libraries under
test pin incompatible dependency sets; this runner only shells out to
``uv run --script`` and merges the JSON they emit.

Usage::

    uv run --no-project --script benchmarks/report.py
    uv run --no-project --script benchmarks/report.py --quick
    uv run --no-project --script benchmarks/report.py --only decorator authz
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "RESULTS.md"

BASELINE_KEY = "baseline"


@dataclass(frozen=True)
class Bench:
    """One benchmark script to execute."""

    key: str
    script: str
    label: str


BENCHES: tuple[Bench, ...] = (
    Bench(BASELINE_KEY, "bench_baseline.py", "no authorization (floor)"),
    Bench("decorator", "bench_decorator.py", "casbin-fastapi-decorator"),
    Bench("authz", "bench_authz.py", "fastapi-authz"),
    Bench("casbin_auth", "bench_casbin_auth.py", "fastapi-casbin-auth"),
)

SCENARIO_TITLES: dict[str, str] = {
    "public": "Unprotected endpoint (`GET /health`)",
    "auth_only": "Authenticated only, no permission check "
    "(`GET /api/profile`)",
    "protected_allow": "Protected endpoint, allowed (`GET /api/items`)",
    "protected_deny": "Protected endpoint, denied (`GET /api/admin`)",
}

SCENARIO_ORDER: tuple[str, ...] = (
    "public",
    "auth_only",
    "protected_allow",
    "protected_deny",
)

#: The library the crossover is computed for.
SUBJECT_KEY = "decorator"

#: A line needs at least this many sweep points to be fitted.
MIN_FIT_POINTS = 2


def run_bench(bench: Bench, extra: list[str]) -> dict:
    """Execute one benchmark script and return its parsed JSON payload."""
    cmd = [
        "uv",
        "run",
        "--no-project",
        "--script",
        str(HERE / bench.script),
        *extra,
    ]
    print(f"→ {bench.label} ...", file=sys.stderr, flush=True)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        msg = f"{bench.script} failed with exit code {proc.returncode}"
        raise RuntimeError(msg)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _index(payload: dict) -> dict[tuple[str, int], dict]:
    return {
        (m["scenario"], m["policy_size"]): m for m in payload["measurements"]
    }


def _fmt_ratio(value: float, base: float) -> str:
    if base <= 0:
        return "—"
    return f"{value / base:.2f}x"


def _linear_fit(points: list[tuple[float, float]]) -> tuple[float, float]:
    """
    Least-squares fit of ``y = intercept + slope * x``.

    Mean latency is linear in the traffic mix by construction, so two
    points would do; fitting all of them just averages out measurement
    noise.
    """
    n = len(points)
    mean_x = sum(x for x, _ in points) / n
    mean_y = sum(y for _, y in points) / n
    denom = sum((x - mean_x) ** 2 for x, _ in points)
    if denom == 0:
        return mean_y, 0.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / denom
    return mean_y - slope * mean_x, slope


def _mix_points(
    cells: dict[tuple[str, int], dict],
    fractions: list[float],
    size: int,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for fraction in fractions:
        cell = cells.get((_mix_name(fraction), size))
        if cell is not None:
            points.append((fraction, cell["mean_us"]))
    return points


def _mix_name(fraction: float) -> str:
    return f"mix_public_{round(fraction * 100):03d}"


def _crossover(
    subject: list[tuple[float, float]],
    rival: list[tuple[float, float]],
) -> str:
    """
    Return the unprotected-traffic share where *subject* overtakes.

    Both series are fitted as lines over the mix fraction and
    intersected.  An intersection outside ``[0, 1]`` means one library
    wins across the whole range.
    """
    if len(subject) < MIN_FIT_POINTS or len(rival) < MIN_FIT_POINTS:
        return "—"
    s0, s1 = _linear_fit(subject)
    r0, r1 = _linear_fit(rival)

    def faster_at(f: float) -> bool:
        return s0 + s1 * f < r0 + r1 * f

    if s1 == r1:
        return "always" if faster_at(0.0) else "never"
    crossing = (r0 - s0) / (s1 - r1)
    if not 0.0 <= crossing <= 1.0:
        return "always" if faster_at(0.0) and faster_at(1.0) else "never"
    return f"{crossing * 100:.0f}%"


def render(payloads: dict[str, dict], sizes: list[int]) -> str:
    """Render the collected payloads as a Markdown report."""
    indexed = {key: _index(p) for key, p in payloads.items()}
    base = indexed.get(BASELINE_KEY, {})

    lines: list[str] = [
        "# Authorization overhead benchmarks",
        "",
        "Generated by `task bench` — do not edit by hand.",
        "",
        "## Environment",
        "",
        f"- Python: {platform.python_version()}",
        f"- Platform: {platform.platform()}",
        f"- Machine: {platform.machine()}",
        "",
        "| library | version | approach | fastapi | casbin engine |",
        "| --- | --- | --- | --- | --- |",
    ]
    for bench in BENCHES:
        payload = payloads.get(bench.key)
        if payload is None:
            continue
        lines.append(
            f"| {payload['library']} | {payload['version']} | "
            f"{payload['approach']} | {payload.get('fastapi', '—')} | "
            f"{payload.get('casbin', '—')} |"
        )

    sample = next(iter(payloads.values()))
    lines += [
        "",
        f"Each cell: {sample['requests_per_cell']} in-process ASGI requests, "
        f"best of {sample['rounds']} rounds, no network involved.",
        "",
    ]

    for scenario in SCENARIO_ORDER:
        lines += [
            f"## {SCENARIO_TITLES[scenario]}",
            "",
            "| policy rules | library | mean µs | p95 µs | p99 µs | "
            "req/s | vs baseline |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for size in sizes:
            for bench in BENCHES:
                cell = indexed.get(bench.key, {}).get((scenario, size))
                if cell is None:
                    continue
                base_cell = base.get((scenario, size))
                ratio = (
                    _fmt_ratio(cell["mean_us"], base_cell["mean_us"])
                    if base_cell
                    else "—"
                )
                lines.append(
                    f"| {size} | {bench.label} | {cell['mean_us']:.1f} | "
                    f"{cell['p95_us']:.1f} | {cell['p99_us']:.1f} | "
                    f"{cell['rps']:,.0f} | {ratio} |"
                )
        lines.append("")

    fractions = sample.get("mix_fractions", [])
    if fractions:
        lines += _render_mix(indexed, fractions, sizes)
        lines += _render_crossover(indexed, fractions, sizes)

    return "\n".join(lines)


def _render_mix(
    indexed: dict[str, dict[tuple[str, int], dict]],
    fractions: list[float],
    sizes: list[int],
) -> list[str]:
    """Render mean latency across the unprotected-traffic sweep."""
    header = " | ".join(f"{round(f * 100)}%" for f in fractions)
    lines = [
        "## Traffic mix sweep",
        "",
        "Mean µs against the share of requests that need no "
        "authorization. 0% is an all-protected service, 100% an "
        "all-public one.",
        "",
    ]
    for size in sizes:
        lines += [
            f"### {size} policy rules",
            "",
            f"| library | {header} |",
            "| --- |" + " ---: |" * len(fractions),
        ]
        for bench in BENCHES:
            cells = indexed.get(bench.key)
            if cells is None:
                continue
            row = []
            for fraction in fractions:
                cell = cells.get((_mix_name(fraction), size))
                row.append(f"{cell['mean_us']:.1f}" if cell else "—")
            lines.append(f"| {bench.label} | " + " | ".join(row) + " |")
        lines.append("")
    return lines


def _render_crossover(
    indexed: dict[str, dict[tuple[str, int], dict]],
    fractions: list[float],
    sizes: list[int],
) -> list[str]:
    """Render where the decorator overtakes each middleware library."""
    subject = indexed.get(SUBJECT_KEY)
    rivals = [
        b for b in BENCHES if b.key not in (BASELINE_KEY, SUBJECT_KEY)
    ]
    if subject is None or not rivals:
        return []

    lines = [
        "## Crossover point",
        "",
        "Share of unprotected traffic at which "
        "`casbin-fastapi-decorator` becomes faster than each "
        "middleware library, from a linear fit over the sweep above. "
        "Lower is better: it is the amount of authorization-free "
        "traffic the decorator approach needs to pay for itself.",
        "",
        "| policy rules | " + " | ".join(b.label for b in rivals) + " |",
        "| ---: |" + " ---: |" * len(rivals),
    ]
    for size in sizes:
        subject_points = _mix_points(subject, fractions, size)
        cells = [
            _crossover(
                subject_points,
                _mix_points(indexed.get(b.key, {}), fractions, size),
            )
            for b in rivals
        ]
        lines.append(f"| {size} | " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def main() -> None:
    """Run the selected benchmarks and write `RESULTS.md`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        nargs="+",
        choices=[b.key for b in BENCHES],
        help="run a subset (the baseline is always included)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="small sweep for a fast sanity check",
    )
    parser.add_argument("--sizes", type=int, nargs="+")
    parser.add_argument("--requests", type=int)
    parser.add_argument("--rounds", type=int)
    parser.add_argument(
        "--json",
        type=Path,
        help="also dump the raw payloads to this path",
    )
    args = parser.parse_args()

    extra: list[str] = []
    if args.quick:
        extra += ["--sizes", "10", "--requests", "500", "--rounds", "1"]
    if args.sizes:
        extra += ["--sizes", *[str(s) for s in args.sizes]]
    if args.requests:
        extra += ["--requests", str(args.requests)]
    if args.rounds:
        extra += ["--rounds", str(args.rounds)]

    selected = [
        b
        for b in BENCHES
        if args.only is None or b.key == BASELINE_KEY or b.key in args.only
    ]

    payloads: dict[str, dict] = {}
    for bench in selected:
        payloads[bench.key] = run_bench(bench, extra)

    sizes = sorted({
        m["policy_size"]
        for p in payloads.values()
        for m in p["measurements"]
    })
    report = render(payloads, sizes)
    OUT_PATH.write_text(report, encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(payloads, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT_PATH}", file=sys.stderr)
    print(report)


if __name__ == "__main__":
    main()

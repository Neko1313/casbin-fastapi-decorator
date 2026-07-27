"""
Dependency-free benchmark harness shared by all ``bench_*.py`` scripts.

Every benchmark script runs in its own isolated PEP 723 environment
(``uv run --script``) because the libraries under test pin mutually
incompatible versions of ``fastapi``/``casbin``.  This module therefore
must stay **stdlib-only** — it is imported from the script directory,
not installed.

The driver calls the ASGI application in-process: no sockets, no HTTP
parsing, no client library.  What is left in the measurement is the
ASGI stack itself plus whatever the authorization layer adds, which is
exactly the quantity being compared.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

NS_PER_US = 1_000
NS_PER_S = 1_000_000_000


# ---------------------------------------------------------------------------
# Shared workload definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    """One request shape replayed N times against an application."""

    name: str
    method: str
    path: str
    role: str | None
    expected_status: int
    description: str


#: Roles used by the generated policy.  ``editor`` may read
#: ``/api/items`` and ``/api/profile`` but not ``/api/admin``;
#: unauthenticated callers may only read ``/health`` — and only because
#: middleware-based libraries *require* an explicit rule for it.
SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="public",
        method="GET",
        path="/health",
        role=None,
        expected_status=200,
        description="unprotected endpoint (no authorization needed)",
    ),
    Scenario(
        name="auth_only",
        method="GET",
        path="/api/profile",
        role="editor",
        expected_status=200,
        description="authenticated, but no permission check needed",
    ),
    Scenario(
        name="protected_allow",
        method="GET",
        path="/api/items",
        role="editor",
        expected_status=200,
        description="protected endpoint, access granted",
    ),
    Scenario(
        name="protected_deny",
        method="GET",
        path="/api/admin",
        role="editor",
        expected_status=403,
        description="protected endpoint, access denied",
    ),
)

#: Fractions of unprotected traffic to sweep.  The two endpoints of the
#: sweep duplicate ``public`` and ``protected_allow`` on purpose: they
#: anchor the linear fit that locates the crossover point.
MIX_FRACTIONS: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0)

#: Length of one repeat of a mix plan.  Every fraction in
#: ``MIX_FRACTIONS`` must be expressible as a whole number of requests
#: out of this many.
MIX_PLAN_LEN = 20

DEFAULT_POLICY_SIZES: tuple[int, ...] = (10, 100, 1000)
DEFAULT_REQUESTS = 3000
DEFAULT_WARMUP = 300
DEFAULT_ROUNDS = 3


# ---------------------------------------------------------------------------
# Casbin model / policy generation (identical for every library)
# ---------------------------------------------------------------------------

MODEL_CONF = """\
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = r.sub == p.sub && r.obj == p.obj && r.act == p.act
"""


def build_policy(policy_size: int) -> str:
    """
    Return a CSV policy with *policy_size* rules.

    The four rules the scenarios depend on come last, so a larger policy
    means a longer scan before the matching rule is reached — the
    pessimistic case, and the same one for every library.

    ``/api/profile`` needs a rule even though the scenario only asks
    "is this caller authenticated": middleware has no way to express
    that question without a policy lookup.
    """
    padding = max(policy_size - 4, 0)
    lines = [f"p, role{i}, /noise/{i}, GET" for i in range(padding)]
    lines += [
        "p, anonymous, /health, GET",
        "p, editor, /api/profile, GET",
        "p, editor, /api/items, GET",
        "p, admin, /api/admin, GET",
    ]
    return "\n".join(lines) + "\n"


def write_model_and_policy(
    tmpdir: str,
    policy_size: int,
) -> tuple[str, str]:
    """Materialize model/policy files and return their paths."""
    from pathlib import Path  # noqa: PLC0415 — keep import cost out of setup

    model_path = Path(tmpdir) / "model.conf"
    policy_path = Path(tmpdir) / "policy.csv"
    model_path.write_text(MODEL_CONF, encoding="utf-8")
    policy_path.write_text(build_policy(policy_size), encoding="utf-8")
    return str(model_path), str(policy_path)


# ---------------------------------------------------------------------------
# In-process ASGI driver
# ---------------------------------------------------------------------------


def _headers_for(role: str | None) -> list[tuple[bytes, bytes]]:
    headers = [(b"host", b"benchmark"), (b"accept", b"*/*")]
    if role is not None:
        headers.append((b"authorization", f"Bearer {role}".encode()))
    return headers


async def _receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


async def _send_once(
    app: Any,
    method: str,
    path: str,
    headers: Sequence[tuple[bytes, bytes]],
) -> int:
    """Push one request through the ASGI app and return its status."""
    status = 0

    async def send(message: dict[str, Any]) -> None:
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]

    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": list(headers),
        "client": ("127.0.0.1", 50000),
        "server": ("benchmark", 80),
    }
    await app(scope, _receive, send)
    return status


@dataclass
class Measurement:
    """Latency statistics for one (scenario, policy size) cell."""

    scenario: str
    policy_size: int
    requests: int
    status: int
    rps: float
    mean_us: float
    p50_us: float
    p95_us: float
    p99_us: float
    samples: list[float] = field(default_factory=list, repr=False)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view without raw samples."""
        return {
            "scenario": self.scenario,
            "policy_size": self.policy_size,
            "requests": self.requests,
            "status": self.status,
            "rps": self.rps,
            "mean_us": self.mean_us,
            "p50_us": self.p50_us,
            "p95_us": self.p95_us,
            "p99_us": self.p99_us,
        }


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(
        len(sorted_values) - 1,
        round(pct / 100.0 * (len(sorted_values) - 1)),
    )
    return sorted_values[idx]


async def _measure(
    app: Any,
    plan: Sequence[tuple[str, str, str | None]],
    *,
    requests: int,
    warmup: int,
) -> tuple[list[float], int]:
    """Replay *plan* cyclically and return per-request latencies (ns)."""
    prepared = [
        (method, path, _headers_for(role)) for method, path, role in plan
    ]
    last_status = 0

    for i in range(warmup):
        method, path, headers = prepared[i % len(prepared)]
        last_status = await _send_once(app, method, path, headers)

    latencies: list[float] = []
    perf = time.perf_counter_ns
    for i in range(requests):
        method, path, headers = prepared[i % len(prepared)]
        start = perf()
        last_status = await _send_once(app, method, path, headers)
        latencies.append(float(perf() - start))

    return latencies, last_status


async def _run_cell(
    app: Any,
    plan: Sequence[tuple[str, str, str | None]],
    *,
    scenario: str,
    policy_size: int,
    requests: int,
    warmup: int,
    rounds: int,
) -> Measurement:
    """Run *rounds* rounds and keep the fastest (least-noise) one."""
    best: list[float] | None = None
    status = 0
    for _ in range(rounds):
        latencies, status = await _measure(
            app, plan, requests=requests, warmup=warmup
        )
        if best is None or statistics.fmean(latencies) < statistics.fmean(
            best
        ):
            best = latencies

    assert best is not None
    ordered = sorted(best)
    total_ns = sum(best)
    return Measurement(
        scenario=scenario,
        policy_size=policy_size,
        requests=len(best),
        status=status,
        rps=len(best) / (total_ns / NS_PER_S),
        mean_us=statistics.fmean(best) / NS_PER_US,
        p50_us=_percentile(ordered, 50) / NS_PER_US,
        p95_us=_percentile(ordered, 95) / NS_PER_US,
        p99_us=_percentile(ordered, 99) / NS_PER_US,
    )


async def _lifespan_up(app: Any) -> Any:
    """Enter the app lifespan, returning the context to exit later."""
    ctx = app.router.lifespan_context(app)
    await ctx.__aenter__()
    return ctx


def mix_scenario_name(fraction: float) -> str:
    """Return the measurement name for a given unprotected fraction."""
    return f"mix_public_{round(fraction * 100):03d}"


def _mix_plan(fraction: float) -> list[tuple[str, str, str | None]]:
    """
    Build one repeat of a traffic mix with *fraction* unprotected calls.

    Public and protected requests are interleaved rather than issued in
    blocks, so neither side gets an unrealistically warm branch
    predictor or dependency cache.
    """
    by_name = {s.name: s for s in SCENARIOS}
    public = by_name["public"]
    protected = by_name["protected_allow"]

    n_public = round(fraction * MIX_PLAN_LEN)
    plan: list[tuple[str, str, str | None]] = []
    acc = 0
    for _ in range(MIX_PLAN_LEN):
        acc += n_public
        if acc >= MIX_PLAN_LEN:
            acc -= MIX_PLAN_LEN
            chosen = public
        else:
            chosen = protected
        plan.append((chosen.method, chosen.path, chosen.role))
    return plan


# ---------------------------------------------------------------------------
# Entry point used by every bench_*.py
# ---------------------------------------------------------------------------


def _dist_version(name: str) -> str:
    from importlib.metadata import (  # noqa: PLC0415
        PackageNotFoundError,
        version,
    )

    try:
        return version(name)
    except PackageNotFoundError:
        return "—"


def _engine_version() -> str:
    """
    Report the casbin engine, whichever distribution provides it.

    ``casbin`` and ``pycasbin`` both install the same ``casbin`` module
    but version it differently, so the report has to name the source.
    """
    for dist in ("casbin", "pycasbin"):
        found = _dist_version(dist)
        if found != "—":
            return f"{dist} {found}"
    return "—"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the CLI shared by all benchmark scripts."""
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=list(DEFAULT_POLICY_SIZES),
        help="policy sizes (number of rules) to sweep",
    )
    parser.add_argument("--requests", type=int, default=DEFAULT_REQUESTS)
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP)
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    return parser.parse_args(argv)


def run_suite(
    *,
    library: str,
    version: str,
    approach: str,
    build_app: Callable[[str, str], Any],
    supports_deny: bool = True,
    argv: Sequence[str] | None = None,
) -> None:
    """
    Run the full scenario × policy-size sweep and print JSON to stdout.

    Args:
        library: distribution name shown in the report.
        version: installed version of that distribution.
        approach: ``"middleware"``, ``"decorator"`` or ``"none"``.
        build_app: ``(model_path, policy_path) -> ASGI app``.
        supports_deny: ``False`` for the unguarded baseline, whose
            "denied" route answers 200 because nothing denies it.
        argv: override for the command line (tests).

    """
    args = parse_args(argv)
    results = asyncio.run(
        _run_all(
            build_app=build_app,
            supports_deny=supports_deny,
            sizes=args.sizes,
            requests=args.requests,
            warmup=args.warmup,
            rounds=args.rounds,
        )
    )
    payload = {
        "library": library,
        "version": version,
        "approach": approach,
        "python": platform.python_version(),
        "fastapi": _dist_version("fastapi"),
        "casbin": _engine_version(),
        "requests_per_cell": args.requests,
        "rounds": args.rounds,
        "mix_fractions": list(MIX_FRACTIONS),
        "measurements": [m.as_dict() for m in results],
    }
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")


async def _run_all(
    *,
    build_app: Callable[[str, str], Any],
    supports_deny: bool,
    sizes: Sequence[int],
    requests: int,
    warmup: int,
    rounds: int,
) -> list[Measurement]:
    import tempfile  # noqa: PLC0415 — only needed here

    results: list[Measurement] = []
    for policy_size in sizes:
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path, policy_path = write_model_and_policy(
                tmpdir, policy_size
            )
            app = build_app(model_path, policy_path)
            ctx = await _lifespan_up(app)
            try:
                for scenario in SCENARIOS:
                    plan = [
                        (scenario.method, scenario.path, scenario.role),
                    ]
                    measurement = await _run_cell(
                        app,
                        plan,
                        scenario=scenario.name,
                        policy_size=policy_size,
                        requests=requests,
                        warmup=warmup,
                        rounds=rounds,
                    )
                    expected = (
                        scenario.expected_status
                        if supports_deny or scenario.name != "protected_deny"
                        else 200
                    )
                    if measurement.status != expected:
                        msg = (
                            f"{scenario.name} @ {policy_size} rules returned "
                            f"{measurement.status}, expected {expected}"
                        )
                        raise RuntimeError(msg)
                    results.append(measurement)

                for fraction in MIX_FRACTIONS:
                    results.append(
                        await _run_cell(
                            app,
                            _mix_plan(fraction),
                            scenario=mix_scenario_name(fraction),
                            policy_size=policy_size,
                            requests=requests,
                            warmup=warmup,
                            rounds=rounds,
                        )
                    )
            finally:
                await ctx.__aexit__(None, None, None)
    return results

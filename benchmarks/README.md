# Benchmarks

How much does a Casbin authorization layer actually cost a small FastAPI
backend, and when is `casbin-fastapi-decorator` the better trade?

Three libraries are compared against an unguarded baseline:

| library | approach | enforce runs on |
| --- | --- | --- |
| `casbin-fastapi-decorator` | per-route decorator (FastAPI DI) | only decorated routes |
| `fastapi-authz` | ASGI middleware | **every** request |
| `fastapi-casbin-auth` | ASGI middleware | **every** request |

> `fastapi-casbin-auth` 1.5.0 ships a `CasbinMiddleware` that is
> byte-identical to `fastapi-authz` 1.0.0. It is included anyway because
> its exact dependency pins (`fastapi==0.121.2`, `pycasbin==2.6.0`) give
> it a different Casbin engine, and that turns out to matter.
>
> Those pins also mean it is the one entry that cannot follow the rest
> of the table onto the current stack: the baseline, the decorator and
> `fastapi-authz` all run on `fastapi==0.140.2` (matching `uv.lock`),
> while `fastapi-casbin-auth` holds everything back to FastAPI 0.121.
> Keep the pins in `bench_baseline.py`, `bench_decorator.py` and
> `bench_authz.py` in sync with `uv.lock` when the workspace is
> upgraded.

## Running

```bash
task bench:run           # full sweep, regenerates RESULTS.md
task bench:quick         # single policy size, one round
task bench:lint          # ruff over the benchmark scripts

# pass extra flags through
task bench:run -- --sizes 10 100 --requests 5000 --only decorator authz
```

Nothing needs installing first. Every `bench_*.py` is a PEP 723 script
with its own inline dependency set, executed by `uv run --script` in an
isolated environment — which is the only way to have `casbin` 1.43 and
`pycasbin` 2.6 (both of which install a module named `casbin`) in the
same comparison.

## Method

* **In-process ASGI.** `harness.py` builds an ASGI `scope` and calls the
  app directly. No sockets, no HTTP parsing, no client library — so the
  authorization layer is not buried under network noise.
* **Identical model and policy** for every library: a plain
  `sub, obj, act` matcher with exact string comparison. The decorator
  routes pass the same `(role, path, method)` triple the middleware
  derives from the request, so the enforcer does the same work in both.
* **Policy sweep** over 10 / 100 / 1000 rules. The three rules the
  scenarios need are written *last*, so a larger policy means a longer
  scan — the pessimistic case, applied equally to everyone.
* **Best of N rounds** after a warmup, reporting mean / p95 / p99
  latency and requests per second.

### Scenarios

| scenario | request | what it isolates |
| --- | --- | --- |
| `public` | `GET /health`, no credentials | cost on routes that need no authorization |
| `auth_only` | `GET /api/profile` as `editor` | cost of "is the caller logged in", with no permission to check |
| `protected_allow` | `GET /api/items` as `editor` | cost of a granted check |
| `protected_deny` | `GET /api/admin` as `editor` | cost of a denied check |
| `mix_public_NNN` | sweep from 0% to 100% unprotected | where the two approaches cross over |

Two of these are shaped by what middleware cannot express:

* `public` needs an explicit `p, anonymous, /health, GET` rule, because
  with middleware there is no such thing as an unguarded route.
* `auth_only` is the `guard.auth_required()` case — authentication
  without authorization. Middleware has no equivalent: to let a logged
  in caller through it must still run `enforce()`, so the route needs a
  policy rule per role even though no permission is actually being
  checked.

### The mix sweep

`mix_public_000` … `mix_public_100` replay a plan of 20 interleaved
requests with a given share of unprotected traffic — 0% is an
all-protected service, 100% an all-public one. Mean latency is linear in
that share, so `report.py` fits a line per library and intersects the
decorator's line with each middleware line. The result is the
**crossover point**: how much authorization-free traffic a service needs
before the decorator approach comes out ahead. The endpoints of the
sweep are measured, not assumed, so the crossover is a measurement
rather than an extrapolation from a guessed traffic mix.

## Reading the results

Current numbers live in [`RESULTS.md`](RESULTS.md). The shape of them:

**Unprotected routes are free with the decorator and never free with
middleware.** `/health` costs `1.0x` baseline under
`casbin-fastapi-decorator` at any policy size — the route has no
decorator, so nothing is resolved and nothing is enforced. Under
middleware the same route costs `3.5x` at 10 rules and `~60x` at 1000,
because every request pays a full `enforce()` regardless.

**Authentication-only routes stay flat.** `guard.auth_required()`
resolves the user and stops — no enforcer, no policy scan — so
`/api/profile` costs ~45 µs at 10 rules and ~45 µs at 1000. The same
route under middleware goes from `3.2x` baseline to `58x`, because
"let any logged-in caller through" still has to be spelled as a policy
rule and still costs a full `enforce()`.

**On guarded routes the decorator is slightly slower.** Resolving
dependencies through FastAPI's DI costs roughly 40-80 µs more per
request than reading `scope["user"]` in middleware. That is the price of
per-route granularity, request-scoped resources and typed dependencies.

**So the answer depends on the ratio, and the crossover moves with
policy size.** With 10 rules the decorator needs about half the traffic
to be authorization-free before it wins; with 1000 rules it needs
~5-15%. The reason is that middleware pays the policy scan on every
single request, so growing the policy raises its floor, while the
decorator's unprotected routes stay at baseline forever.

**Policy size dominates everything else.** Going from 10 to 1000 rules
costs an order of magnitude more than any difference between libraries.
If your numbers look bad, look at the policy and the matcher before
looking at the integration layer.

### Two gotchas the benchmark surfaced

1. **Make `enforcer_provider` `async def`.** FastAPI offloads *sync*
   dependencies to a threadpool, which adds ~100 µs per request — more
   than the entire authorization check at small policy sizes. Every
   enforcer provider shipped in `packages/` is already async; a
   hand-rolled `def enforcer_provider(): return enforcer` is not.
2. **The Casbin engine version is not neutral.** `pycasbin` 2.6.0 comes
   out consistently ~10-15% faster than `casbin` 1.43.0 on the same
   policy, which is the only reason the two identical middlewares differ
   in the tables.

## Caveats

* Single-process, single-threaded, in-process ASGI. Absolute numbers are
  not throughput predictions for a deployed service; the *ratios* are
  the point.
* No `g` (RBAC role inheritance) and no `keyMatch`/`regexMatch` in the
  matcher. Those make `enforce()` more expensive for everyone and would
  compress the differences between libraries.
* Casbin's own policy caching and filtered adapters are out of scope —
  they help all three approaches equally.

## Layout

```
harness.py           stdlib-only driver, scenarios, policy generation
middleware_app.py    shared app builder for the two middleware libs
bench_baseline.py    no authorization (the floor)
bench_decorator.py   casbin-fastapi-decorator
bench_authz.py       fastapi-authz
bench_casbin_auth.py fastapi-casbin-auth
report.py            runs them all, writes RESULTS.md
```

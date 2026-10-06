# Contributing

Thanks for your interest in `casbin-fastapi-decorator`! Everyone is welcome to open issues and send pull requests — no permission needed. By participating you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Report a bug or ask a question** — open an [issue](https://github.com/Neko1313/casbin-fastapi-decorator/issues/new/choose) and pick a template.
- **Suggest a feature** — open a *Feature request*. For larger changes, please discuss the idea in an issue before writing code.
- **Fix something or add a feature** — send a pull request (see below).
- **Improve docs and examples** — small fixes are very welcome; you can send them straight as a PR.
- **Find a first task** — look for issues labelled [`good first issue`](https://github.com/Neko1313/casbin-fastapi-decorator/labels/good%20first%20issue) or [`help wanted`](https://github.com/Neko1313/casbin-fastapi-decorator/labels/help%20wanted).

> Security problems must **not** be reported in public issues — see [SECURITY.md](SECURITY.md).

## Project layout

A [uv](https://docs.astral.sh/uv/) monorepo:

| Path | What it is |
|---|---|
| `src/casbin_fastapi_decorator/` | Core package (`PermissionGuard`, `AccessSubject`) |
| `packages/casbin-fastapi-decorator-file/` | File policies with hot-reload |
| `packages/casbin-fastapi-decorator-jwt/` | JWT authentication |
| `packages/casbin-fastapi-decorator-db/` | DB-backed policies (SQLAlchemy async) |
| `packages/casbin-fastapi-decorator-casdoor/` | Casdoor OAuth2 integration |
| `examples/` | Runnable examples |
| `tests/` | Core tests |

## Development setup

Requirements: Python 3.10+, [uv](https://docs.astral.sh/uv/), [Task](https://taskfile.dev/). Docker is needed only for the DB package tests (testcontainers).

```bash
# 1. Fork the repository on GitHub, then:
git clone https://github.com/<your-username>/casbin-fastapi-decorator.git
cd casbin-fastapi-decorator
git checkout -b my-change

# 2. Install everything
task install

# 3. Work, then check
task lint                 # ruff + bandit + ty for all packages
task tests                # tests for all packages
```

Run only what you touched:

```bash
task core:lint     && task core:test
task jwt:lint      && task jwt:test
task db:lint       && task db:test        # requires Docker
task casdoor:lint  && task casdoor:test
task file:lint     && task file:test

task core:test PYTEST_ARGS="tests/unit/ -m unit"
task core:test PYTEST_ARGS="tests/ -k test_name"
```

Please run linting and tests through `task` targets rather than invoking `ruff`, `pytest` and friends directly, so your local run matches CI.

## Code style

- Line length 79, Python 3.10 as the minimum target (configured in `ruff.toml`).
- Public code needs type annotations and docstrings; tests are exempt from those rules.
- Add or update tests for every behaviour change. Pytest markers: `unit`, `integration`, `permission_guard`, `access_subject`.
- Enforcer providers that hold state follow the singleton + async context manager pattern described in [CLAUDE.md](CLAUDE.md).

## Pull requests

1. Open (or find) an issue first for anything non-trivial.
2. Keep the PR focused — one logical change per PR.
3. Make sure `task lint` and the relevant tests pass.
4. Fill in the PR template.
5. **Use a [Conventional Commits](https://www.conventionalcommits.org/) title**, for example:
   - `fix(jwt): reject tokens without exp`
   - `feat(db): add poll_interval option`
   - `docs: clarify AccessSubject selector`
   - `feat!: drop Python 3.9` (breaking change)

   Releases and the changelog are generated from these titles with [git-cliff](https://git-cliff.org/), so the title matters.

CI runs automatically on pull requests, including those from forks. A maintainer may need to click *Approve and run* for a first-time contributor's workflows.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).

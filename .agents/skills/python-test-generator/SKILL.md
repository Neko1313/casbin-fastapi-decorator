---
name: python-test-generator
description: Generates comprehensive Python test suites for FastAPI/SQLAlchemy projects using pytest, testcontainers, polyfactory, and pytest-asyncio. Use when asked to write tests, create test fixtures, scaffold test architecture, generate integration or unit tests for Python backend services, or set up test infrastructure with Docker containers.
compatibility: Requires Python 3.11+, Docker (for integration tests), pytest, pytest-asyncio, pytest-cov, pytest-randomly, pytest-xdist, testcontainers, polyfactory
allowed-tools: Bash Read Write
---

# Python Test Generator

Generates production-grade test suites for **FastAPI + SQLAlchemy** projects following a strict architecture with testcontainers, polyfactory factories, async fixtures, and proper cleanup patterns.

## Quick Start

1. Read [Architecture Reference](references/ARCHITECTURE.md) for directory layout
2. Read [Fixture Patterns](references/FIXTURES.md) for container/entity fixtures
3. Read [Test Patterns](references/PATTERNS.md) for writing integration/unit tests
4. Scaffold structure, then generate files bottom-up (containers → entities → tests)

## Core Principles

- **Integration tests** = always use testcontainers (Postgres, Redis, etc.)
- **Unit tests** = no containers, mock everything external
- **Factories** = use `polyfactory` (`ModelFactory` / `AsyncPersistenceFactory`) for entity creation
- **Async** = all fixtures and tests use `pytest-asyncio` with `asyncio_mode = "auto"`
- **Isolation** = every test gets a clean state via cleanup fixtures
- **Markers** = every test carries `@pytest.mark.integration` or `@pytest.mark.unit` + domain marker

---

## Step-by-Step Generation Process

### Step 1 — Identify inputs

Collect from the user:
- List of **models** (SQLAlchemy / Pydantic)
- List of **endpoints** (router, method, path, auth requirements)
- List of **services / use-cases** to test
- Container needs: postgres, redis, rabbitmq, kafka, s3, etc.
- Auth scheme (JWT roles, anonymous, etc.)

### Step 2 — Scaffold directory structure

```
tests/
├── conftest.py
├── fixtures/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   └── <model_name>.py
│   └── containers/
│       ├── __init__.py
│       ├── postgres/
│       │   ├── __init__.py
│       │   ├── container.py
│       │   └── cleanup.py
│       └── redis/           # if needed
│           ├── __init__.py
│           ├── container.py
│           └── cleanup.py
├── integration/
│   └── <BusinessEntity>/
│       └── <action>/
│           ├── act.py
│           └── error.py
└── unit/
    └── <BusinessEntity>/
        └── <action>/
            ├── act.py
            └── error.py
```

### Step 3 — Generate containers (bottom-up)

Generate `container.py` then `cleanup.py` then `__init__.py` for each container.
See [Fixture Patterns](references/FIXTURES.md#containers).

### Step 4 — Generate entity factories

One file per model in `fixtures/entities/`.
See [Fixture Patterns](references/FIXTURES.md#entity-factories).

### Step 5 — Generate test files

Follow the pattern: **Mock/Data → Act → Assert**.
See [Test Patterns](references/PATTERNS.md).

---

## pytest.ini / pyproject.toml configuration

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "integration: marks tests as integration (require containers)",
    "unit: marks tests as unit",
]
addopts = "-v --cov=src --cov-report=term-missing -p no:randomly"
```

For parallel integration runs use:
```bash
pytest -m integration -n auto --dist=loadgroup
```

---

## Helper function (conftest.py)

```python
def _has_integration_marker(request: pytest.FixtureRequest) -> bool:
    """Check if the test or its parents have the integration marker."""
    return request.node.get_closest_marker("integration") is not None
```
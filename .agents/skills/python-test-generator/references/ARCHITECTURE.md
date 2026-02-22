# Architecture Reference

## Full Directory Layout

```
tests/
├── conftest.py                          # Root: pytest_plugins + warnings suppression
├── fixtures/
│   ├── __init__.py                      # pytest_plugins = ["tests.fixtures.entities", "tests.fixtures.containers"]
│   ├── entities/
│   │   ├── __init__.py                  # pytest_plugins = ["tests.fixtures.entities.branch", ...]
│   │   ├── branch.py                    # BranchFactory + branch_factory fixture
│   │   ├── floor.py
│   │   └── annotation.py
│   └── containers/
│       ├── __init__.py                  # pytest_plugins = ["tests.fixtures.containers.postgres", ...]
│       ├── postgres/
│       │   ├── __init__.py              # pytest_plugins = ["tests.fixtures.containers.postgres.container",
│       │   │                            #                   "tests.fixtures.containers.postgres.cleanup"]
│       │   ├── container.py             # postgres_container, db_engine, uow fixtures
│       │   └── cleanup.py               # db_cleanup fixture (truncate all tables)
│       └── redis/
│           ├── __init__.py
│           ├── container.py             # redis_container, redis_client fixtures
│           └── cleanup.py               # redis_cleanup fixture (FLUSHDB)
├── integration/
│   ├── annotation/
│   │   ├── get/
│   │   │   ├── act.py                   # happy-path integration tests
│   │   │   └── error.py                 # error/edge case integration tests
│   │   └── create/
│   │       ├── act.py
│   │       └── error.py
│   └── floor/
│       └── ...
└── unit/
    ├── annotation/
    │   └── get/
    │       ├── act.py
    │       └── error.py
    └── services/
        └── annotation_service/
            ├── act.py
            └── error.py
```

## __init__.py plugin chain

The chain allows pytest to auto-discover fixtures without explicit imports.

### tests/conftest.py
```python
pytest_plugins = ["tests.fixtures"]
```

### tests/fixtures/__init__.py
```python
pytest_plugins = [
    "tests.fixtures.entities",
    "tests.fixtures.containers",
]
```

### tests/fixtures/containers/__init__.py
```python
pytest_plugins = [
    "tests.fixtures.containers.postgres",
    # "tests.fixtures.containers.redis",  # uncomment if needed
]
```

### tests/fixtures/containers/postgres/__init__.py
```python
pytest_plugins = [
    "tests.fixtures.containers.postgres.container",
    "tests.fixtures.containers.postgres.cleanup",
]
```

### tests/fixtures/entities/__init__.py
```python
pytest_plugins = [
    "tests.fixtures.entities.branch",
    "tests.fixtures.entities.floor",
    "tests.fixtures.entities.annotation",
]
```

## Naming conventions

| Concept | Convention | Example |
|---|---|---|
| Container fixture | `{db}_container` | `postgres_container` |
| Engine fixture | `db_engine` | `db_engine` |
| Session/UoW fixture | `uow` | `uow` |
| Cleanup fixture | `{db}_cleanup` | `db_cleanup` |
| Factory class | `{Model}Factory` | `AnnotationFactory` |
| Factory fixture | `{model}_factory` | `annotation_factory` |
| Client tuple fixture | `clients_v{n}` | `clients_v1` |
| Client fixture | `client_{role}_v{n}` | `client_user_v1` |

## Marker strategy

Every test must have:
1. `@pytest.mark.integration` OR `@pytest.mark.unit`
2. A domain marker e.g. `@pytest.mark.annotation`
3. `@pytest.mark.asyncio` (can be omitted when `asyncio_mode = "auto"`)

```python
@pytest.mark.integration
@pytest.mark.annotation
async def test_something(): ...
```
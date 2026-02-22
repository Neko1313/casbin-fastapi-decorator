# Test Patterns

## Integration Test Template

Every integration test follows: **Mock/Data → Act → Assert**

```python
# tests/integration/<entity>/<action>/act.py
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import codes
from polyfactory.factories import ModelFactory

from src.models import Annotation, Branch, Floor, Link
from src.schemas.v1 import AnnotationBatchResponseV1
from src.uow import UnitOfWork
from tests.fixtures.entities.annotation import AnnotationFactory
from tests.fixtures.entities.branch import BranchFactory
from tests.fixtures.entities.floor import FloorFactory

EXPECTED_ANNOTATION_COUNT = 2


@pytest.mark.integration
@pytest.mark.annotation
async def test_get_annotations_with_data(
    clients_v1: ClientTuple,
    uow: UnitOfWork,
    branch_factory: type[BranchFactory],
    floor_factory: type[FloorFactory],
    annotation_factory: type[AnnotationFactory],
) -> None:
    # ── Mock / Data ────────────────────────────────────────────────────
    client_user_v1, client_manager_v1, client_anonymous_v1 = clients_v1

    branch = branch_factory.build()
    floor = floor_factory.build(branch_id=branch.id)
    annotations = annotation_factory.batch(EXPECTED_ANNOTATION_COUNT, floor_id=floor.id)
    cell = Link(object_guid=uuid4(), annotation_id=annotations[0].id)

    async with uow as uow_:
        await uow_.get_repository(Branch).create(branch)
        await uow_.get_repository(Floor).create(floor)
        await uow_.get_repository(Annotation).create_many(annotations)
        await uow_.get_repository(Link).create(cell)

    # ── Act (user role) ────────────────────────────────────────────────
    response = await client_user_v1.get(f"/floor/{floor.id}/annotations")

    # ── Assert ─────────────────────────────────────────────────────────
    assert response.status_code == codes.OK
    batch = AnnotationBatchResponseV1.model_validate(response.json())
    assert len(batch.annotations) == EXPECTED_ANNOTATION_COUNT

    for item in batch.annotations:
        if item.id == annotations[0].id:
            assert item.cell_guid == cell.object_guid
        else:
            assert item.cell_guid is None

    # ── Act (manager role) ────────────────────────────────────────────
    response = await client_manager_v1.get(f"/floor/{floor.id}/annotations")
    assert response.status_code == codes.OK
    assert len(AnnotationBatchResponseV1.model_validate(response.json()).annotations) == EXPECTED_ANNOTATION_COUNT

    # ── Act (anonymous) ───────────────────────────────────────────────
    response = await client_anonymous_v1.get(f"/floor/{floor.id}/annotations")
    assert response.status_code == codes.UNAUTHORIZED
```

## Error Test Template

```python
# tests/integration/<entity>/<action>/error.py

@pytest.mark.integration
@pytest.mark.annotation
async def test_get_annotations_floor_not_found(
    clients_v1: ClientTuple,
) -> None:
    client_user_v1, _, _ = clients_v1
    response = await client_user_v1.get(f"/floor/{uuid4()}/annotations")
    assert response.status_code == codes.NOT_FOUND


@pytest.mark.integration
@pytest.mark.annotation
async def test_get_annotations_unauthorized(
    clients_v1: ClientTuple,
) -> None:
    _, _, client_anonymous_v1 = clients_v1
    response = await client_anonymous_v1.get(f"/floor/{uuid4()}/annotations")
    assert response.status_code == codes.UNAUTHORIZED
```

## Unit Test Template

```python
# tests/unit/<entity>/<action>/act.py

@pytest.mark.unit
@pytest.mark.annotation
async def test_annotation_service_returns_list(
    annotation_factory: type[AnnotationFactory],
) -> None:
    annotations = annotation_factory.batch(3)
    service = AnnotationService(repo=MockAnnotationRepo(annotations))

    result = await service.get_by_floor(floor_id=uuid4())

    assert len(result) == 3
```

## Complex Scenario Template

For files with complex multi-step scenarios create a named file:

```python
# tests/integration/annotation/get/with_pagination.py

@pytest.mark.integration
@pytest.mark.annotation
async def test_get_annotations_pagination(
    clients_v1: ClientTuple,
    uow: UnitOfWork,
    floor_factory: type[FloorFactory],
    annotation_factory: type[AnnotationFactory],
    branch_factory: type[BranchFactory],
) -> None:
    ...
```

## Common Assertion Helpers

```python
def assert_response_matches_model(
    response_item: dict,
    model_instance: Any,
    fields: list[str],
) -> None:
    """Assert that response JSON matches model fields."""
    for field in fields:
        assert str(response_item[field]) == str(getattr(model_instance, field)), (
            f"Field {field!r} mismatch: "
            f"{response_item[field]!r} != {getattr(model_instance, field)!r}"
        )
```

## conftest.py (root)

```python
# tests/conftest.py
import warnings

import pytest

pytest_plugins = ["tests.fixtures"]


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: integration tests (use containers)")
    config.addinivalue_line("markers", "unit: unit tests (no containers)")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Automatically add asyncio marker to async tests."""
    for item in items:
        if isinstance(item, pytest.Function) and item.get_closest_marker("asyncio") is None:
            if item.get_closest_marker("integration") or item.get_closest_marker("unit"):
                pass  # asyncio_mode=auto handles this


# Suppress common noisy warnings
def pytest_configure(config: pytest.Config) -> None:
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="testcontainers")
    warnings.filterwarnings("ignore", message=".*PytestUnraisableExceptionWarning.*")
```

## Running tests

```bash
# All tests
pytest

# Integration only (starts containers)
pytest -m integration

# Unit only (no containers, fast)
pytest -m unit

# Specific domain
pytest -m "integration and annotation"

# Parallel integration
pytest -m integration -n auto --dist=loadgroup

# With coverage
pytest --cov=src --cov-report=html

# Random order (uses pytest-randomly)
pytest -m unit -p randomly
```
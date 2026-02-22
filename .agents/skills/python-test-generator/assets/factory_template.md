# Entity Factory Template

## Minimal factory (Pydantic model)

```python
# tests/fixtures/entities/{model_name_snake}.py
from __future__ import annotations

import pytest
from polyfactory.factories.pydantic_factory import ModelFactory

from src.models import {ModelName}


class {ModelName}Factory(ModelFactory[{ModelName}]):
    __model__ = {ModelName}


@pytest.fixture
def {model_name_snake}_factory() -> type[{ModelName}Factory]:
    return {ModelName}Factory
```

## SQLAlchemy dataclass factory

```python
from polyfactory.factories.dataclass_factory import DataclassFactory

class {ModelName}Factory(DataclassFactory[{ModelName}]):
    __model__ = {ModelName}
```

## Factory with custom field overrides

```python
class {ModelName}Factory(ModelFactory[{ModelName}]):
    __model__ = {ModelName}
    
    # Static override
    is_active = True
    
    # Dynamic override using factory methods
    @classmethod
    def name(cls) -> str:
        return f"test-{cls.__faker__.word()}"
    
    # Use_alias if model uses aliases
    __use_defaults__ = True
```

## __init__.py pattern for entities

```python
# tests/fixtures/entities/__init__.py
pytest_plugins = [
    "tests.fixtures.entities.{model_a}",
    "tests.fixtures.entities.{model_b}",
]
```
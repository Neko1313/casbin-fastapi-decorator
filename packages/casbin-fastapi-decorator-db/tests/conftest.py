from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

pytest_plugins = ["tests.fixtures"]


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: integration tests (real I/O, HTTP)")
    config.addinivalue_line("markers", "unit: unit tests (no real I/O)")
    config.addinivalue_line("markers", "db_provider: DatabaseEnforcerProvider component tests")

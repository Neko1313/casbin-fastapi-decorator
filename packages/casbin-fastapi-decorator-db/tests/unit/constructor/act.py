"""Unit tests for DatabaseEnforcerProvider constructor (no DB calls)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from casbin_fastapi_decorator_db import DatabaseEnforcerProvider


class _Row:
    def __init__(self, sub: str, obj: str, act: str) -> None:
        self.sub = sub
        self.obj = obj
        self.act = act


def _session_factory() -> Any:
    return None


def _mapper(row: _Row) -> tuple[str, str, str]:
    return (row.sub, row.obj, row.act)


@pytest.mark.unit
@pytest.mark.db_provider
def test_model_path_str_converted_to_path() -> None:
    provider = DatabaseEnforcerProvider(
        model_path="path/to/model.conf",
        session_factory=_session_factory,
        policy_model=_Row,
        policy_mapper=_mapper,
    )
    assert isinstance(provider._model_path, Path)
    assert provider._model_path == Path("path/to/model.conf")


@pytest.mark.unit
@pytest.mark.db_provider
def test_model_path_path_object_stays_path(tmp_path: Path) -> None:
    p = tmp_path / "model.conf"
    provider = DatabaseEnforcerProvider(
        model_path=p,
        session_factory=_session_factory,
        policy_model=_Row,
        policy_mapper=_mapper,
    )
    assert provider._model_path == p
    assert isinstance(provider._model_path, Path)


@pytest.mark.unit
@pytest.mark.db_provider
def test_session_factory_stored() -> None:
    provider = DatabaseEnforcerProvider(
        model_path="model.conf",
        session_factory=_session_factory,
        policy_model=_Row,
        policy_mapper=_mapper,
    )
    assert provider._session_factory is _session_factory


@pytest.mark.unit
@pytest.mark.db_provider
def test_policy_model_stored() -> None:
    provider = DatabaseEnforcerProvider(
        model_path="model.conf",
        session_factory=_session_factory,
        policy_model=_Row,
        policy_mapper=_mapper,
    )
    assert provider._policy_model is _Row


@pytest.mark.unit
@pytest.mark.db_provider
def test_policy_mapper_stored() -> None:
    provider = DatabaseEnforcerProvider(
        model_path="model.conf",
        session_factory=_session_factory,
        policy_model=_Row,
        policy_mapper=_mapper,
    )
    assert provider._policy_mapper is _mapper


@pytest.mark.unit
@pytest.mark.db_provider
def test_default_policies_defaults_to_empty_list() -> None:
    provider = DatabaseEnforcerProvider(
        model_path="model.conf",
        session_factory=_session_factory,
        policy_model=_Row,
        policy_mapper=_mapper,
    )
    assert provider._default_policies == []


@pytest.mark.unit
@pytest.mark.db_provider
def test_default_policies_stored_when_provided() -> None:
    defaults: list[tuple[Any, ...]] = [("admin", "*", "*"), ("user", "data", "read")]
    provider = DatabaseEnforcerProvider(
        model_path="model.conf",
        session_factory=_session_factory,
        policy_model=_Row,
        policy_mapper=_mapper,
        default_policies=defaults,
    )
    assert provider._default_policies == defaults


@pytest.mark.unit
@pytest.mark.db_provider
def test_default_policies_none_becomes_empty_list() -> None:
    provider = DatabaseEnforcerProvider(
        model_path="model.conf",
        session_factory=_session_factory,
        policy_model=_Row,
        policy_mapper=_mapper,
        default_policies=None,
    )
    assert provider._default_policies == []


@pytest.mark.unit
@pytest.mark.db_provider
def test_provider_is_callable() -> None:
    provider = DatabaseEnforcerProvider(
        model_path="model.conf",
        session_factory=_session_factory,
        policy_model=_Row,
        policy_mapper=_mapper,
    )
    assert callable(provider)

from __future__ import annotations

import asyncio
import contextlib
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import casbin
from sqlalchemy import select
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession


class _ModelFileHandler(FileSystemEventHandler):
    """Marks the provider dirty when model.conf is modified or recreated."""

    def __init__(self, model_path: str, callback: Callable[[], None]) -> None:
        self._model_path = model_path
        self._callback = callback

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification event."""
        if not event.is_directory and event.src_path == self._model_path:
            self._callback()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation/atomic-rename event."""
        if not event.is_directory and event.src_path == self._model_path:
            self._callback()

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle atomic rename (temp-file write) event."""
        dest = getattr(event, "dest_path", None)
        if dest and not event.is_directory and dest == self._model_path:
            self._callback()


class DatabaseEnforcerProvider:
    """
    Enforcer provider: loads policies from a database via SQLAlchemy.

    The :class:`casbin.Enforcer` is cached after the first call and
    reloaded automatically when:

    * ``model_path`` changes on disk (detected via :mod:`watchdog`).
    * The SHA-256 hash of all policy rows changes in the database
      (checked every ``poll_interval`` seconds by a background task).

    Must be used as an async context manager inside a FastAPI ``lifespan``
    to activate the file watcher and polling task::

        provider = DatabaseEnforcerProvider(
            model_path="model.conf",
            session_factory=get_session,
            policy_model=Policy,
            policy_mapper=lambda p: (p.sub, p.obj, p.act),
        )

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            async with provider:
                yield

        guard = PermissionGuard(enforcer_provider=provider, ...)

    Without the context manager the provider still caches the enforcer
    but will not auto-reload on file or database changes.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        model_path: str | Path,
        session_factory: Callable[..., AsyncSession],
        policy_model: type,
        policy_mapper: Callable[[Any], tuple[Any, ...]],
        default_policies: list[tuple[Any, ...]] | None = None,
        poll_interval: float = 30.0,
    ) -> None:
        self._model_path = Path(model_path).resolve()
        self._session_factory = session_factory
        self._policy_model = policy_model
        self._policy_mapper = policy_mapper
        self._default_policies = default_policies or []
        self._poll_interval = poll_interval

        self._enforcer: casbin.Enforcer | None = None
        self._lock = asyncio.Lock()
        self._needs_reload: bool = True
        self._db_hash: str | None = None
        self._observer: Observer | None = None
        self._poll_task: asyncio.Task[None] | None = None

    def _mark_dirty(self) -> None:
        """Mark the enforcer as stale; called from the watchdog thread."""
        self._needs_reload = True

    async def _fetch_policies(self) -> list[tuple[Any, ...]]:
        """Fetch all policy rows from the database."""
        async with self._session_factory() as session:
            result = await session.execute(select(self._policy_model))
            return [self._policy_mapper(row) for row in result.scalars()]

    @staticmethod
    def _compute_hash(policies: list[tuple[Any, ...]]) -> str:
        """Return a SHA-256 fingerprint of the policy set."""
        serialized = "|".join(sorted(str(p) for p in policies))
        return hashlib.sha256(serialized.encode()).hexdigest()

    def _build_enforcer_sync(
        self, policies: list[tuple[Any, ...]]
    ) -> casbin.Enforcer:
        """Construct the casbin Enforcer from policies (blocking I/O)."""
        all_policies = self._default_policies + policies
        enforcer = casbin.Enforcer(str(self._model_path))
        if all_policies:
            enforcer.add_policies(all_policies)
        return enforcer

    async def _reload(self, policies: list[tuple[Any, ...]]) -> None:
        """Rebuild the enforcer and update the hash (call under the lock)."""
        self._enforcer = await asyncio.to_thread(
            self._build_enforcer_sync, policies
        )
        self._db_hash = self._compute_hash(policies)
        self._needs_reload = False

    async def __call__(self) -> casbin.Enforcer:
        """Return the cached enforcer, reloading if a change was detected."""
        if self._needs_reload or self._enforcer is None:
            async with self._lock:
                if self._needs_reload or self._enforcer is None:
                    policies = await self._fetch_policies()
                    await self._reload(policies)
        assert self._enforcer is not None  # nosec B101
        return self._enforcer

    async def _poll_loop(self) -> None:
        """Background task: detect DB policy changes by hashing all rows."""
        while True:
            await asyncio.sleep(self._poll_interval)
            with contextlib.suppress(Exception):
                # Transient DB errors must not crash the background task
                policies = await self._fetch_policies()
                new_hash = self._compute_hash(policies)
                if new_hash != self._db_hash:
                    async with self._lock:
                        if new_hash != self._db_hash:
                            await self._reload(policies)

    async def __aenter__(self) -> DatabaseEnforcerProvider:
        """Perform the initial load, start file watcher and DB poll task."""
        await self.__call__()

        handler = _ModelFileHandler(
            model_path=str(self._model_path),
            callback=self._mark_dirty,
        )
        self._observer = Observer()
        self._observer.schedule(
            handler, str(self._model_path.parent), recursive=False
        )
        self._observer.start()

        self._poll_task = asyncio.create_task(self._poll_loop())
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Stop the poll task and file watcher."""
        if self._poll_task is not None:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None

        if self._observer is not None:
            self._observer.stop()
            await asyncio.to_thread(self._observer.join)
            self._observer = None

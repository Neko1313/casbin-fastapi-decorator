from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

import casbin
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:
    from collections.abc import Callable


class _FileChangeHandler(FileSystemEventHandler):
    """Call a callback when a watched file path is modified or recreated."""

    def __init__(
        self,
        paths: frozenset[str],
        callback: Callable[[], None],
    ) -> None:
        self._paths = paths
        self._callback = callback

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification event."""
        if not event.is_directory and event.src_path in self._paths:
            self._callback()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation/atomic-rename event."""
        if not event.is_directory and event.src_path in self._paths:
            self._callback()

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle atomic rename (temp-file write) event."""
        dest = getattr(event, "dest_path", None)
        if dest and not event.is_directory and dest in self._paths:
            self._callback()


class CachedFileEnforcerProvider:
    """
    Enforcer provider with automatic hot-reload on file changes.

    Loads the casbin Enforcer once and reloads automatically when
    ``model_path`` or ``policy_path`` changes on disk.

    The provider caches the :class:`casbin.Enforcer` instance and returns
    it on every FastAPI request without re-reading files.  File changes are
    detected via :mod:`watchdog` and trigger a lazy reload on the next
    :meth:`__call__`.

    Must be used as an async context manager inside a FastAPI ``lifespan``
    to activate the file watcher::

        provider = CachedFileEnforcerProvider(
            model_path="casbin/model.conf",
            policy_path="casbin/policy.csv",
        )

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            async with provider:
                yield

        guard = PermissionGuard(
            user_provider=get_current_user,
            enforcer_provider=provider,
            error_factory=lambda *_: HTTPException(403, "Forbidden"),
        )

    Without the context manager the provider still works but will not
    watch for file changes — the enforcer is loaded on the first call
    and cached for the application lifetime.
    """

    def __init__(
        self,
        *,
        model_path: str | Path,
        policy_path: str | Path,
    ) -> None:
        self._model_path = Path(model_path).resolve()
        self._policy_path = Path(policy_path).resolve()
        self._enforcer: casbin.Enforcer | None = None
        self._lock = asyncio.Lock()
        self._needs_reload: bool = True
        self._observer: Observer | None = None

    def _mark_dirty(self) -> None:
        """Mark the enforcer as stale; called from the watchdog thread."""
        self._needs_reload = True

    def _build_enforcer(self) -> casbin.Enforcer:
        """Construct a new Enforcer from disk (blocking I/O)."""
        return casbin.Enforcer(str(self._model_path), str(self._policy_path))

    async def __call__(self) -> casbin.Enforcer:
        """Return the cached enforcer, reloading on detected file changes."""
        if self._needs_reload or self._enforcer is None:
            async with self._lock:
                if self._needs_reload or self._enforcer is None:
                    self._enforcer = await asyncio.to_thread(
                        self._build_enforcer
                    )
                    self._needs_reload = False
        assert self._enforcer is not None  # nosec B101
        return self._enforcer

    async def __aenter__(self) -> CachedFileEnforcerProvider:
        """Perform the initial load and start the file watcher."""
        await self.__call__()

        watched = frozenset({str(self._model_path), str(self._policy_path)})
        handler = _FileChangeHandler(paths=watched, callback=self._mark_dirty)
        self._observer = Observer()
        for directory in {self._model_path.parent, self._policy_path.parent}:
            self._observer.schedule(handler, str(directory), recursive=False)
        self._observer.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Stop the file watcher."""
        if self._observer is not None:
            self._observer.stop()
            await asyncio.to_thread(self._observer.join)
            self._observer = None

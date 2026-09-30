"""KùzuDB graph engine wrapper with read-only concurrency and atomic swap."""

from __future__ import annotations

import gc
import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Any

import kuzu

logger = logging.getLogger(__name__)

_swap_lock = threading.Lock()
_active_instances: set[KuzuGraphEngine] = set()


class KuzuGraphEngine:
    """Manages the embedded KùzuDB graph instance."""

    swap_lock = _swap_lock

    def __init__(self, db_path: str | Path, read_only: bool = False, buffer_pool_size: int = 0) -> None:
        self.db_path = Path(db_path)
        self.read_only = read_only
        self.buffer_pool_size = buffer_pool_size
        self._db: kuzu.Database | None = None
        self._conn: kuzu.Connection | None = None
        self._initialize()
        _active_instances.add(self)

    def _initialize(self) -> None:
        """Initialize or connect to the Kùzu database."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = kuzu.Database(
            str(self.db_path),
            read_only=self.read_only,
            buffer_pool_size=self.buffer_pool_size,
        )
        self._conn = kuzu.Connection(self._db)
        logger.info("Initialized KùzuDB connection (path=%s, read_only=%s)", self.db_path, self.read_only)

    @property
    def conn(self) -> kuzu.Connection | None:
        """Expose underlying KùzuDB connection."""
        return self._conn

    def execute(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results as a list of dicts."""
        if not self._conn:
            raise RuntimeError("Database connection is not open")
        
        result = self._conn.execute(query, parameters or {})
        rows: list[dict[str, Any]] = []
        
        # In Kùzu, query results are accessed via get_as_df or row-by-row
        try:
            df = result.get_as_df()
            return df.to_dict(orient="records")
        except Exception:
            while result.has_next():
                row = result.get_next()
                rows.append({"result": row})
            return rows

    def close(self) -> None:
        """Close Kùzu handles so the on-disk file/directory can be replaced."""
        conn = self._conn
        db = self._db
        self._conn = None
        self._db = None
        _active_instances.discard(self)
        if conn is not None:
            try:
                conn.close()
            except Exception as exc:
                logger.debug("Connection close notice: %s", exc)
        if db is not None:
            try:
                db.close()
            except Exception as exc:
                logger.debug("Database close notice: %s", exc)

    def close_connections(self) -> None:
        """Explicitly drop connection and database handles."""
        self.close()

    @classmethod
    def close_all_for_path(cls, db_path: str | Path) -> list[KuzuGraphEngine]:
        """Close every tracked handle on ``db_path``. Returns the closed instances."""
        target = Path(db_path).resolve()
        matching = [
            inst for inst in list(_active_instances)
            if inst.db_path.resolve() == target
        ]
        for inst in matching:
            try:
                inst.close()
            except Exception as close_err:
                logger.warning("Error closing KùzuDB handle on %s: %s", target, close_err)
        return matching

    def reopen_database(self, db_path: str | Path | None = None) -> None:
        """Reopen database connection to specified or existing path."""
        if db_path:
            self.db_path = Path(db_path)
        self._initialize()
        _active_instances.add(self)

    @classmethod
    def atomic_swap(cls, staging_db_path: str | Path, production_db_path: str | Path) -> None:
        """Atomically replace the production database with the staging database.
        
        Thread-safe connection switch:
        1. Acquires swap_lock.
        2. Closes active handles on staging and production paths to prevent EBUSY/PermissionError.
        3. Executes POSIX atomic os.replace with backup and automatic rollback.
        4. Re-initializes connections and cleans up old backup.
        """
        with _swap_lock:
            staging_path = Path(staging_db_path).resolve()
            prod_path = Path(production_db_path).resolve()

            if not staging_path.exists():
                raise FileNotFoundError(f"Staging database does not exist: {staging_path}")

            # Ensure target directory exists
            prod_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info("Preparing atomic database swap: %s -> %s", staging_path, prod_path)

            # 1. Close active handles on both paths (prevents EBUSY / stale fds)
            matching_instances = cls.close_all_for_path(prod_path) + cls.close_all_for_path(staging_path)
            _close_colocated_kuzu_handles()
            gc.collect()

            backup_path = prod_path.with_name(prod_path.name + ".old")
            if backup_path.exists():
                if backup_path.is_dir():
                    shutil.rmtree(backup_path, ignore_errors=True)
                else:
                    try:
                        os.remove(backup_path)
                    except OSError:
                        pass

            # 2. Perform atomic swap
            has_backup = False
            if prod_path.exists():
                os.replace(prod_path, backup_path)
                has_backup = True

            try:
                os.replace(staging_path, prod_path)
                logger.info("Atomic swap os.replace completed: %s -> %s", staging_path, prod_path)
            except Exception as swap_err:
                logger.error("Atomic swap failed, rolling back: %s", swap_err)
                if has_backup and backup_path.exists():
                    os.replace(backup_path, prod_path)
                raise swap_err

            # 3. Cleanup backup safely
            if has_backup and backup_path.exists():
                if backup_path.is_dir():
                    shutil.rmtree(backup_path, ignore_errors=True)
                else:
                    try:
                        os.remove(backup_path)
                    except OSError:
                        pass

            # 4. Leave in-process handles closed so external reader/inference processes
            # can acquire the exclusive lock without contention.
            _active_instances.clear()
            _close_colocated_kuzu_handles()
            gc.collect()




def _close_colocated_kuzu_handles() -> None:
    """Drop process-local Kùzu handles that are not tracked in _active_instances."""
    try:
        import archipelago.inference.state as _st
        old = getattr(_st, "_db", None)
        if old is not None:
            try:
                old.close()
            except Exception:
                pass
            _st._db = None
    except Exception:
        pass
    try:
        import okf.graph_db as _gdb
        gdb = getattr(_gdb, "_DEFAULT_GRAPH_DB", None)
        if gdb is not None and hasattr(gdb, "close"):
            try:
                gdb.close()
            except Exception:
                pass
        _gdb._DEFAULT_GRAPH_DB = None
    except Exception:
        pass

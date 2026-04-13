from datetime import datetime, timezone
from pathlib import Path
import json
import logging
import os

logger = logging.getLogger(__name__)


class RunHistoryStore:
    def __init__(self, path: str = "data/run_history.json"):
        self.legacy_path = Path(path)
        self.history_dir = self.legacy_path.parent / 'run_history'
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self._last_id: int | None = None  # Cache last_id to avoid full file scan
        self._last_file_mtime: float | None = None  # For cache invalidation
        self._perf_log_threshold_sec = 0.1  # Log slow appends (>100ms)

    def _day_path(self, dt: datetime) -> Path:
        return self.history_dir / f"{dt.date().isoformat()}.jsonl"

    def _iter_paths(self) -> list[Path]:
        return sorted(self.history_dir.glob('*.jsonl'))

    def _append_jsonl(self, path: Path, entry: dict) -> None:
        with path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def _load_jsonl(self, path: Path) -> list[dict]:
        rows = []
        if not path.exists():
            return rows
        with path.open('r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return rows

    def load(self) -> list[dict]:
        rows = []
        for path in self._iter_paths():
            rows.extend(self._load_jsonl(path))
        return rows

    def _check_cache_invalidated(self) -> bool:
        """Check if cache should be invalidated due to file changes.
        
        Cache invalidation triggers:
        - Any .jsonl file in history_dir has newer mtime than cached _last_file_mtime
        - _last_file_mtime is None (first run)
        
        Returns True if cache was invalidated.
        """
        current_max_mtime = self._last_file_mtime
        
        for path in self._iter_paths():
            try:
                mtime = path.stat().st_mtime
                if current_max_mtime is None or mtime > current_max_mtime:
                    current_max_mtime = mtime
            except OSError:
                continue
        
        # If we found newer files, invalidate cache
        if self._last_file_mtime is None or current_max_mtime > self._last_file_mtime:
            logger.debug(
                "run_history cache invalidated | old_mtime=%s new_mtime=%s",
                self._last_file_mtime,
                current_max_mtime,
            )
            self._last_id = None
            self._last_file_mtime = current_max_mtime
            return True
        
        return False

    def append(self, kind: str, payload: dict) -> dict:
        import time
        t0 = time.time()
        
        # Check if cache needs invalidation (file changed externally)
        cache_invalidated = self._check_cache_invalidated()
        
        now = datetime.now(timezone.utc)
        # Use cached last_id instead of scanning entire file
        if self._last_id is None:
            recent = self.list_recent(limit=1)
            self._last_id = recent[-1]['id'] if recent else 0
        
        entry = {
            'id': self._last_id + 1,
            'kind': kind,
            'created_at': now.isoformat(),
            'payload': payload,
        }
        self._append_jsonl(self._day_path(now), entry)
        self._last_id = entry['id']  # Update cache
        
        # Performance logging for slow appends
        elapsed = time.time() - t0
        if elapsed > self._perf_log_threshold_sec:
            logger.warning(
                "run_history.append SLOW | kind=%s id=%d elapsed=%.3fs cache_invalidated=%s",
                kind, entry['id'], elapsed, cache_invalidated,
            )
        else:
            logger.debug(
                "run_history.append | kind=%s id=%d elapsed=%.3fs cache_invalidated=%s",
                kind, entry['id'], elapsed, cache_invalidated,
            )
        
        # Update mtime cache after successful write
        try:
            written_path = self._day_path(now)
            new_mtime = written_path.stat().st_mtime
            if self._last_file_mtime is None or new_mtime > self._last_file_mtime:
                self._last_file_mtime = new_mtime
        except OSError:
            pass
        
        return entry

    def list_recent(self, limit: int = 20) -> list[dict]:
        rows = []
        for path in reversed(self._iter_paths()):
            rows = self._load_jsonl(path) + rows
            if len(rows) >= limit:
                return rows[-limit:]
        return rows[-limit:]

    def reset(self) -> dict:
        for path in self._iter_paths():
            path.unlink(missing_ok=True)
        return {'status': 'cleared'}

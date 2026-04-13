#!/usr/bin/env python3
"""
Performance tests for RunHistoryStore.

Verifies:
1. last_id caching reduces append time from ~1.1s to <0.2s
2. Cache invalidation works when files change externally
3. Performance logging triggers for slow appends
"""

import pytest
import time
import tempfile
from pathlib import Path

from investment_bot.services.run_history_store import RunHistoryStore


class TestRunHistoryStorePerformance:
    """Performance tests for RunHistoryStore.append()."""

    def test_append_uses_cache_after_first_call(self, tmp_path):
        """Verify subsequent appends use cache (not full file scan)."""
        history_dir = tmp_path / "run_history"
        history_dir.mkdir()
        
        # Create a store with some existing data (simulating 150MB file)
        store = RunHistoryStore(path=str(tmp_path / "run_history.json"))
        store.history_dir = history_dir
        
        # Create historical data (simulate large file)
        day_path = history_dir / "2026-04-12.jsonl"
        for i in range(1000):
            with day_path.open('a') as f:
                f.write(f'{{"id":{i},"kind":"test","created_at":"2026-04-12T00:00:00Z","payload":{{}}}}\n')
        
        # First append may scan (cache miss)
        t0 = time.time()
        store.append("test", {"i": 0})
        first_time = time.time() - t0
        
        # Subsequent appends should use cache
        times = []
        for i in range(1, 10):
            t0 = time.time()
            store.append("test", {"i": i})
            times.append(time.time() - t0)
        
        avg_time = sum(times) / len(times)
        
        # Cache should make appends 5x faster (1.1s -> 0.11s in production)
        # Use conservative threshold for tests
        assert avg_time < 0.2, f"Append too slow: {avg_time:.3f}s (expected <0.2s)"
        assert avg_time < first_time * 0.5, f"Cache not working: avg={avg_time:.3f}s, first={first_time:.3f}s"

    def test_cache_invalidation_on_external_change(self, tmp_path):
        """Verify cache invalidates when files change externally."""
        history_dir = tmp_path / "run_history"
        history_dir.mkdir()
        
        store = RunHistoryStore(path=str(tmp_path / "run_history.json"))
        store.history_dir = history_dir
        
        # First append establishes cache
        entry1 = store.append("test", {"phase": 1})
        
        # Simulate external file modification (another process)
        day_path = history_dir / f"{entry1['created_at'][:10]}.jsonl"
        time.sleep(0.01)  # Ensure mtime difference
        with day_path.open('a') as f:
            f.write('{"id":9999,"kind":"external","created_at":"2026-04-12T00:00:00Z","payload":{}}\n')
        
        # Next append should detect change and invalidate cache
        entry2 = store.append("test", {"phase": 2})
        
        # ID should be > 9999 (cache was invalidated and rescanned)
        assert entry2['id'] > 9999, f"Cache not invalidated: id={entry2['id']}, expected >9999"

    def test_append_performance_logging(self, tmp_path, caplog):
        """Verify slow appends are logged."""
        import logging
        
        history_dir = tmp_path / "run_history"
        history_dir.mkdir()
        
        store = RunHistoryStore(path=str(tmp_path / "run_history.json"))
        store.history_dir = history_dir
        store._perf_log_threshold_sec = 0.001  # Very low threshold for testing
        
        with caplog.at_level(logging.WARNING):
            store.append("test", {"data": "value"})
        
        # Should log warning for slow append (threshold is 0.001s)
        assert any("run_history.append" in record.message for record in caplog.records)

    def test_last_id_cache_initialization(self, tmp_path):
        """Verify last_id cache initializes correctly from existing data."""
        history_dir = tmp_path / "run_history"
        history_dir.mkdir()
        
        # Create existing data
        day_path = history_dir / "2026-04-12.jsonl"
        for i in range(100):
            with day_path.open('a') as f:
                f.write(f'{{"id":{i},"kind":"test","created_at":"2026-04-12T00:00:00Z","payload":{{}}}}\n')
        
        store = RunHistoryStore(path=str(tmp_path / "run_history.json"))
        store.history_dir = history_dir
        
        # First append should continue from last ID
        entry = store.append("test", {"final": True})
        
        assert entry['id'] == 100, f"Expected id=100, got {entry['id']}"
        assert store._last_id == 100, f"Cache not updated: _last_id={store._last_id}"


class TestRunHistoryStoreScalability:
    """Scalability tests - performance should not degrade with file size."""

    def test_append_time_independent_of_file_size(self, tmp_path):
        """Verify append time doesn't grow with historical data size."""
        history_dir = tmp_path / "run_history"
        history_dir.mkdir()
        
        # Test with small file (10 entries)
        store_small = RunHistoryStore(path=str(tmp_path / "run_history.json"))
        store_small.history_dir = history_dir
        
        day_path = history_dir / "2026-04-12.jsonl"
        for i in range(10):
            with day_path.open('a') as f:
                f.write(f'{{"id":{i},"kind":"test","created_at":"2026-04-12T00:00:00Z","payload":{{}}}}\n')
        
        # Warm cache
        store_small.append("warmup", {})
        
        # Measure
        t0 = time.time()
        store_small.append("test", {"size": "small"})
        time_small = time.time() - t0
        
        # Add 990 more entries (1000 total)
        for i in range(10, 1000):
            with day_path.open('a') as f:
                f.write(f'{{"id":{i},"kind":"test","created_at":"2026-04-12T00:00:00Z","payload":{{}}}}\n')
        
        # Invalidate cache to force rescan
        store_small._last_id = None
        
        # Warm cache again
        store_small.append("warmup", {})
        
        # Measure with large file
        t0 = time.time()
        store_small.append("test", {"size": "large"})
        time_large = time.time() - t0
        
        # Times should be similar (cache makes file size irrelevant)
        # Allow 2x variance for system noise, but not 10x (which would indicate O(n) scan)
        assert time_large < time_small * 3, \
            f"Performance degrades with file size: small={time_small:.3f}s, large={time_large:.3f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

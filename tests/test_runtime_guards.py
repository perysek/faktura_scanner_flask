"""
Tests for config.runtime_guards.assert_single_worker (improvement area #3).

Contract: the app must refuse to boot with more than one worker process,
because the import SSE queue and (absent the advisory lock) the SMS scheduler
assume a single process. Enforced in code, not a comment.
"""
import pytest

from config.runtime_guards import assert_single_worker


class TestAssertSingleWorker:
    def test_allows_single_worker_no_env(self):
        assert_single_worker(1, None)  # must not raise

    def test_allows_web_concurrency_one(self):
        assert_single_worker(1, "1")  # must not raise

    def test_allows_empty_web_concurrency(self):
        assert_single_worker(1, "")  # must not raise

    def test_rejects_workers_gt_one(self):
        with pytest.raises(RuntimeError, match="ONE worker"):
            assert_single_worker(3, None)

    def test_rejects_web_concurrency_gt_one(self):
        with pytest.raises(RuntimeError, match="ONE worker"):
            assert_single_worker(1, "3")

    def test_unparseable_web_concurrency_is_ignored(self):
        # Garbage env shouldn't block boot; workers=1 governs.
        assert_single_worker(1, "not-a-number")

"""Run independent pieces of the search on every core (Windows and Linux alike).

Threads, not processes: the heavy work is numpy on large arrays (indexing, partitions, reductions), which
releases the GIL, so threads scale across cores without re-importing numpy in each worker (slow on Windows,
where processes are spawned), without copying the price panel and without pickling shapes or callbacks.
"""

from __future__ import annotations

import os
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, Iterator, TypeVar

T = TypeVar("T")
R = TypeVar("R")

_THREAD_PREFIX = "perfectshape-worker"
_pools: dict[int, ThreadPoolExecutor] = {}
_pools_lock = threading.Lock()


def n_workers(requested: int = 0) -> int:
    """Threads to use: ``requested`` if > 0, else every logical core this process may run on (CPU affinity,
    e.g. ``taskset`` or a container's cpuset on Linux, is respected where Python can see it)."""
    if requested > 0:
        return requested
    count = getattr(os, "process_cpu_count", os.cpu_count)()     # process_cpu_count: Python 3.13+
    return count or 1


def _pool(workers: int) -> ThreadPoolExecutor:
    """One long-lived pool per size: a scan maps many small batches, starting threads for each would cost more."""
    with _pools_lock:
        pool = _pools.get(workers)
        if pool is None:
            pool = _pools[workers] = ThreadPoolExecutor(workers, thread_name_prefix=_THREAD_PREFIX)
        return pool


def ordered_map(fn: Callable[[T], R], items: Iterable[T], workers: int) -> Iterator[R]:
    """``fn`` over ``items`` on ``workers`` threads; results come back in input order, as they are ready.

    ``items`` is consumed lazily in the caller's thread, at most ``2 * workers`` ahead of the results, so a
    generator of items can report progress, block (pause) or raise (stop) between items, and read state the
    caller updated from earlier results. With one worker, or when called from a worker thread (nested maps
    would wait on their own pool), everything runs in the caller's thread.
    """
    if workers <= 1 or threading.current_thread().name.startswith(_THREAD_PREFIX):
        for it in items:
            yield fn(it)
        return
    pool = _pool(workers)
    pending: deque = deque()
    try:
        for it in items:
            pending.append(pool.submit(fn, it))
            if len(pending) >= 2 * workers:
                yield pending.popleft().result()
        while pending:
            yield pending.popleft().result()
    finally:
        for f in pending:
            f.cancel()

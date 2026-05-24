"""Metrics collection and reporting."""

import time
from collections import defaultdict
from typing import Dict, List
from threading import RLock


class MetricsCollector:
    def __init__(self):
        self._lock = RLock()
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._timers: Dict[str, float] = {}

    def increment(self, metric: str, value: int = 1) -> None:
        with self._lock:
            self._counters[metric] += value

    def gauge(self, metric: str, value: float) -> None:
        with self._lock:
            self._gauges[metric] = value

    def observe(self, metric: str, value: float) -> None:
        with self._lock:
            self._histograms[metric].append(value)

    def start_timer(self, metric: str) -> None:
        with self._lock:
            self._timers[metric] = time.time()

    def stop_timer(self, metric: str) -> float:
        with self._lock:
            if metric in self._timers:
                duration = time.time() - self._timers.pop(metric)
                self.observe(metric, duration)
                return duration
        return 0.0

    def snapshot(self) -> Dict:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {k: {"count": len(v), "sum": sum(v), "avg": sum(v) / len(v) if v else 0}
                               for k, v in self._histograms.items()},
            }


metrics = MetricsCollector()

# 2019-01-01T14:07:11 update

# 2019-02-19T09:42:37 update

# 2019-02-20T11:46:45 update

# 2019-03-19T17:25:17 update

# 2019-05-16T12:48:17 update

# 2019-06-20T11:04:52 update

# 2019-06-26T17:33:14 update

# 2019-08-12T17:10:36 update

# 2019-09-05T16:31:08 update

# 2019-09-16T12:13:09 update

# 2019-10-03T16:54:10 update

# 2019-11-09T14:31:15 update

# 2019-12-04T10:29:27 update

# 2020-02-28T17:05:55 update

# 2020-03-11T18:08:46 update

# 2020-04-15T15:24:15 update

# 2020-08-05T14:37:18 update

# 2020-08-07T15:39:54 update

# 2020-10-23T08:52:37 update

# 2020-11-02T14:44:36 update

# 2020-11-11T10:56:55 update

# 2020-11-25T14:04:17 update

# 2021-03-08T08:49:42 update

# 2021-03-17T16:07:48 update

# 2021-06-11T15:34:00 update

# 2021-06-28T20:31:01 update

# 2021-07-14T18:16:02 update

# 2021-08-30T09:47:24 update

# 2021-10-19T13:43:46 update

# 2021-10-21T16:07:56 update

# 2021-12-27T08:18:40 update

# 2022-03-09T16:48:09 update

# 2022-03-29T10:51:15 update

# 2022-05-19T09:07:00 update

# 2022-06-08T15:24:11 update

# 2022-08-17T08:23:02 update

# 2022-08-20T16:37:39 update

# 2022-12-07T15:19:57 update

# 2022-12-26T11:59:00 update

# 2023-01-26T20:15:04 update

# 2023-02-01T10:10:52 update

# 2023-05-04T11:13:12 update

# 2023-07-06T08:27:57 update

# 2023-07-24T12:34:13 update

# 2023-08-31T15:00:03 update

# 2023-09-16T20:55:20 update

# 2023-12-08T16:55:55 update

# 2024-01-04T15:47:36 update

# 2024-01-05T14:46:16 update

# 2024-04-08T10:08:30 update

# 2024-04-08T20:31:02 update

# 2024-08-13T17:18:11 update

# 2024-09-13T08:11:06 update

# 2024-12-06T11:42:59 update

# 2025-02-03T11:41:46 update

# 2025-03-22T09:28:10 update

# 2025-04-06T11:12:26 update

# 2025-04-09T13:39:45 update

# 2025-08-07T15:56:14 update

# 2025-08-20T10:41:17 update

# 2025-10-16T17:51:05 update

# 2025-10-16T14:29:07 update

# 2025-12-05T13:05:17 update

# 2025-12-12T09:49:47 update

# 2025-12-19T13:59:03 update

# 2026-01-13T16:00:24 update

# 2026-02-05T14:23:35 update

# 2026-03-13T08:25:05 update

# 2026-04-23T12:24:44 update

# 2026-05-18T20:56:34 update

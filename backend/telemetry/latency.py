import time
from contextlib import asynccontextmanager, contextmanager
from typing import Dict, Any, Optional

class LatencyTracker:
    """
    Granular Latency Telemetry Tracker.
    Measures request latency across routing, model execution, tool execution, and verification.
    """

    def __init__(self):
        self.metrics: Dict[str, float] = {
            "routing_ms": 0.0,
            "model_ms": 0.0,
            "tool_ms": 0.0,
            "verification_ms": 0.0,
            "total_ms": 0.0
        }
        self.start_time: float = 0.0

    def start(self):
        self.start_time = time.perf_counter()

    def record_stage(self, stage: str, duration_ms: float):
        key = f"{stage}_ms" if not stage.endswith("_ms") else stage
        self.metrics[key] = round(duration_ms, 2)

    def stop(self) -> Dict[str, float]:
        if self.start_time > 0:
            total_duration = (time.perf_counter() - self.start_time) * 1000.0
            self.metrics["total_ms"] = round(total_duration, 2)
        return self.metrics

@contextmanager
def measure_stage(tracker: LatencyTracker, stage_name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - start) * 1000.0
        tracker.record_stage(stage_name, elapsed)

@asynccontextmanager
async def async_measure_stage(tracker: LatencyTracker, stage_name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - start) * 1000.0
        tracker.record_stage(stage_name, elapsed)

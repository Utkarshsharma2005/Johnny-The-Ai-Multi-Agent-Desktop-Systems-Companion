import time
from backend.telemetry.latency import LatencyTracker, measure_stage

def test_latency_tracker():
    tracker = LatencyTracker()
    tracker.start()

    with measure_stage(tracker, "routing"):
        time.sleep(0.01)

    with measure_stage(tracker, "model"):
        time.sleep(0.02)

    metrics = tracker.stop()
    assert metrics["routing_ms"] > 0
    assert metrics["model_ms"] > 0
    assert metrics["total_ms"] >= metrics["routing_ms"] + metrics["model_ms"]

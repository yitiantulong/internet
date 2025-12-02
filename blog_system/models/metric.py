from datetime import datetime
from typing import Any, Dict, List, Optional

from database import Database


class PerformanceMetricModel:
    def __init__(self, database: Database) -> None:
        self.database = database

    def record_metric(self, latency_ms: float, throughput: float, rtt: float, request_count: int) -> None:
        timestamp = datetime.utcnow().isoformat()
        self.database.execute(
            """
            INSERT INTO performance_metrics (timestamp, latency_ms, throughput, rtt, request_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                latency_ms,
                throughput,
                rtt,
                request_count,
            ),
        )

    def list_recent_metrics(self, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT timestamp, latency_ms, throughput, rtt, request_count
            FROM performance_metrics
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        metrics: List[Dict[str, Any]] = []
        for row in rows:
            metrics.append(
                {
                    "timestamp": row["timestamp"],
                    "latency_ms": row["latency_ms"],
                    "throughput": row["throughput"],
                    "rtt": row["rtt"],
                    "request_count": row["request_count"],
                }
            )
        metrics.reverse()
        return metrics


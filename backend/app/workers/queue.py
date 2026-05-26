from __future__ import annotations

from typing import Any

import redis
from rq import Queue

from .tasks import execute_summary_job


class QueueManager:
    def __init__(self, settings):
        self.settings = settings

    def enqueue_summary(self, summary_id: int, summary_job_id: str) -> dict[str, Any]:
        if not self.settings.rq_async:
            execute_summary_job(summary_id=summary_id, summary_job_id=summary_job_id)
            return {"mode": "inline", "enqueued": False}

        try:
            conn = redis.from_url(self.settings.redis_url)
            conn.ping()
            queue = Queue("summaries", connection=conn)
            job = queue.enqueue(
                "app.workers.tasks.execute_summary_job",
                summary_id,
                summary_job_id,
                job_timeout=1800,
                result_ttl=3600,
            )
            return {"mode": "rq", "enqueued": True, "rq_job_id": job.id}
        except Exception:
            execute_summary_job(summary_id=summary_id, summary_job_id=summary_job_id)
            return {"mode": "inline_fallback", "enqueued": False}

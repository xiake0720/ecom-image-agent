"""主图任务轻量队列服务。

职责：
- 把主图任务串行化到单 worker 中执行，避免同一进程里多个真实 provider 调用互相争抢；
- 向 runtime 接口提供最小队列观测信息，而不引入外部任务系统。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock, Thread
from queue import Queue
from typing import Callable

from backend.services.main_image_service import PreparedMainImageTask


@dataclass(frozen=True)
class QueueSnapshot:
    """单个任务在当前队列中的观测快照。"""

    active_task_id: str | None
    queue_position: int | None
    queue_size: int


class MainImageTaskQueue:
    """进程内单 worker 主图任务队列。"""

    def __init__(self) -> None:
        self._queue: Queue[tuple[PreparedMainImageTask, Callable[[PreparedMainImageTask], None]]] = Queue()
        self._pending_task_ids: deque[str] = deque()
        self._active_task_id: str | None = None
        self._lock = Lock()
        self._worker: Thread | None = None

    def enqueue(self, prepared: PreparedMainImageTask, executor: Callable[[PreparedMainImageTask], None]) -> None:
        """把新任务放入队列，并确保 worker 已启动。"""

        self._ensure_worker_started()
        task_id = prepared.summary.task_id
        with self._lock:
            self._pending_task_ids.append(task_id)
        self._queue.put((prepared, executor))

    def get_snapshot(self, task_id: str) -> QueueSnapshot:
        """返回任务在当前队列中的位置。"""

        with self._lock:
            active_task_id = self._active_task_id
            pending_list = list(self._pending_task_ids)

        queue_position: int | None = None
        if active_task_id == task_id:
            queue_position = 0
        elif task_id in pending_list:
            # 这里返回“前方还有多少任务”，包含当前执行中的任务。
            queue_position = pending_list.index(task_id) + (1 if active_task_id is not None else 0)

        queue_size = len(pending_list) + (1 if active_task_id is not None else 0)
        return QueueSnapshot(active_task_id=active_task_id, queue_position=queue_position, queue_size=queue_size)

    def _ensure_worker_started(self) -> None:
        """延迟启动后台 worker。"""

        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = Thread(target=self._worker_loop, name="main-image-task-queue", daemon=True)
            self._worker.start()

    def _worker_loop(self) -> None:
        """持续消费队列中的任务。"""

        while True:
            prepared, executor = self._queue.get()
            task_id = prepared.summary.task_id
            with self._lock:
                if task_id in self._pending_task_ids:
                    self._pending_task_ids.remove(task_id)
                self._active_task_id = task_id
            try:
                executor(prepared)
            finally:
                with self._lock:
                    if self._active_task_id == task_id:
                        self._active_task_id = None
                self._queue.task_done()


main_image_task_queue = MainImageTaskQueue()

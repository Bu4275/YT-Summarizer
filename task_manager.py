from queue import Queue
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
import threading
import enum
import logging
import os
from video_processor import process_video
from task_progress import TaskProgress
logger = logging.getLogger(__name__)

class TaskStatus(enum.Enum):
    WAITING = "waiting"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Task:
    id: str
    source: str  # Changed from url to source
    language: str
    prompt_type: str
    status: TaskStatus
    created_at: datetime
    is_local: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Dict[str, Any] = None
    error: Optional[str] = None
    result: Optional[str] = None

class TaskManager:
    def __init__(self, socketio):
        self.task_queue = Queue()
        self.tasks = {}
        self.current_task = None
        self.lock = threading.Lock()
        self.socketio = socketio
        # 在初始化時就設置事件處理器
        self._setup_event_handlers()
        self._start_worker()

    def _setup_event_handlers(self):
        """設置 Socket.IO 事件處理器"""
        def handle_step(data):
            with self.lock:
                if self.current_task:
                    self.current_task.progress = {
                        'step': data.get('step', '0/4'),
                        'message': data.get('message', '處理中...'),
                        'percentage': int(data.get('step', '0/4').split('/')[0]) * 25
                    }
                    self.current_task.status = TaskStatus.PROCESSING
                    self._emit_task_update(self.current_task)
                    logger.debug(f"Updated task progress: {data}")

        def handle_complete(data):
            with self.lock:
                if self.current_task:
                    self.current_task.status = TaskStatus.COMPLETED
                    self.current_task.result = data.get('result')
                    self.current_task.progress = {
                        'step': '4/4',
                        'message': '處理完成！',
                        'percentage': 100
                    }
                    self.current_task.completed_at = datetime.now()
                    self._emit_task_update(self.current_task)
                    logger.debug("Task completed successfully")

        def handle_error(data):
            with self.lock:
                if self.current_task:
                    self.current_task.status = TaskStatus.FAILED
                    self.current_task.error = data.get('error', '未知錯誤')
                    self.current_task.progress = {
                        'step': '4/4',
                        'message': f'處理失敗: {data.get("error", "未知錯誤")}',
                        'percentage': 100
                    }
                    self.current_task.completed_at = datetime.now()
                    self._emit_task_update(self.current_task)
                    logger.error(f"Task failed: {data.get('error')}")

        # 註冊事件處理器
        self.socketio.on_event('processing_step', handle_step)
        self.socketio.on_event('processing_complete', handle_complete)
        self.socketio.on_event('processing_error', handle_error)

    def _emit_task_update(self, task):
        """發送任務更新事件，包含所有必要的狀態信息"""
        self.socketio.emit('task_update', {
            'task_id': task.id,
            'task': {
                'id': task.id,
                'source': task.source,
                'language': task.language,
                'prompt_type': task.prompt_type,
                'status': task.status.value,
                'created_at': task.created_at.isoformat(),
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'progress': task.progress,
                'error': task.error,
                'result': task.result
            }
        })

    def _start_worker(self):
        def worker():
            while True:
                task = self.task_queue.get()
                if task is None:
                    break

                with self.lock:
                    self.current_task = task
                    task.status = TaskStatus.PROCESSING
                    task.started_at = datetime.now()
                    self._emit_task_update(task)

                try:
                    from video_processor import process_video
                    progress = TaskProgress(task, self.socketio)
                    process_video(task.source, task.language, self.socketio, task.prompt_type, task.is_local, progress)
                    task.status = TaskStatus.COMPLETED
                except Exception as e:
                    logger.error(f'Task processing error: {str(e)}')
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                finally:
                    task.completed_at = datetime.now()
                    with self.lock:
                        self.current_task = None
                        self._emit_task_update(task)
                    self.task_queue.task_done()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        logger.info("Task worker thread started")

    def _emit_task_update(self, task):
        """發送任務更新事件"""
        self.socketio.emit('task_update', {
            'task_id': task.id,
            'task': self._serialize_task(task)
        })

    def _serialize_task(self, task):
        """將任務序列化為可 JSON 的格式"""
        if task.is_local:
            source = os.path.basename(task.source)
        else:
            source = task.source
        return {
            'id': task.id,
            'source': source,
            'language': task.language,
            'prompt_type': task.prompt_type,
            'status': task.status.value,
            'created_at': task.created_at.isoformat(),
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'progress': task.progress,
            'error': task.error,
            'result': task.result
        }

    def add_task(self, source: str, language: str, prompt_type: str, is_local: bool = False) -> str:
        task_id = datetime.now().strftime('%Y%m%d%H%M%S')
        task = Task(
            id=task_id,
            source=source,  # Changed from url to source
            language=language,
            prompt_type=prompt_type,
            status=TaskStatus.WAITING,
            created_at=datetime.now(),
            is_local=is_local,
            progress={"step": "waiting", "message": "等待處理中..."}
        )
        
        with self.lock:
            self.tasks[task_id] = task
            self.task_queue.put(task)
            self._emit_task_update(task)
        
        return task_id

    def get_task_status(self, task_id: str) -> Optional[Task]:
        """獲取任務狀態"""
        return self.tasks.get(task_id)

    def get_all_tasks(self):
        """獲取所有任務"""
        return list(self.tasks.values())

    def update_task_progress(self, task_id: str, progress: Dict[str, Any]):
        """更新任務進度"""
        if task_id in self.tasks:
            with self.lock:
                task = self.tasks[task_id]
                task.progress = progress
                self._emit_task_update(task)
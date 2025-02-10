# task_progress.py
from typing import Optional, Dict, Any

class TaskProgress:
    def __init__(self, current_task=None, socketio=None):
        self.current_task = current_task
        self.socketio = socketio

    def update(self, step: str, message: str, percentage: int):
        progress = {
            'step': step,
            'message': message,
            'percentage': percentage
        }
        
        if self.socketio:
            self.socketio.emit('processing_step', {
                'step': step,
                'message': message
            })
            
        if self.current_task:
            self.current_task.progress = progress

    def complete(self, result: str):
        if self.socketio:
            self.socketio.emit('processing_complete', {
                'result': result,
                'status': 'completed',
                'step': '4/4',
                'message': '處理完成！'
            })
        if self.current_task:
            self.current_task.progress = {
                'step': '4/4',
                'message': '處理完成！',
                'percentage': 100
            }

    def error(self, error_msg: str):
        if self.socketio:
            self.socketio.emit('processing_error', {
                'error': error_msg,
                'status': 'failed'
            })
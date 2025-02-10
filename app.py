# app.py
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO
import threading
import logging
import os
import datetime
import re
import torch
from video_processor import process_video
from summary_handler import prompt_manager, generate_summary  # 添加 generate_summary 的導入
from config import Config 
from models import Session, VideoRecord
from task_manager import TaskManager
from werkzeug.utils import secure_filename

def _ansi_style(value: str, *styles: str) -> str:
    """添加 ANSI 樣式到文本"""
    codes = {
        "bold": 1,
        "red": 31,
        "green": 32,
        "yellow": 33,
        "magenta": 35,
        "cyan": 36,
    }

    for style in styles:
        value = f"\x1b[{codes[style]}m{value}"

    return f"{value}\x1b[0m"

# 設置日誌
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

if torch.cuda.is_available():
    logger.info("CUDA is available")
else:
    logger.info(_ansi_style("CUDA is not available", "bold", "red"))



def init_directories():
    """初始化所需的目錄結構"""
    directories = [
        Config.AUDIO_DIR,
        Config.TRANSCRIPT_DIR,
        Config.SUMMARY_DIR
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            logger.info(f"Creating directory: {directory}")
            os.makedirs(directory)
            logger.info(f"Directory created successfully: {directory}")
        else:
            logger.info(f"Directory already exists: {directory}")

def create_app():
    """創建並配置 Flask 應用"""
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    
    # 初始化目錄結構
    logger.info("Initializing directory structure...")
    init_directories()
    logger.info("Directory structure initialized successfully")
    
    return app

app = create_app()
socketio = SocketIO(app, cors_allowed_origins="*")
task_manager = TaskManager(socketio)  # 在這裡初始化 TaskManager

@app.route('/')
def index():
    logger.debug('Accessing index page')
    try:
        prompts = prompt_manager.get_all_prompts()
        return render_template('index.html', prompts=prompts)
    except Exception as e:
        logger.error(f'Error rendering template: {str(e)}')
        return str(e), 500

def is_valid_youtube_url(url):
    """檢查是否為有效的 YouTube URL"""
    # YouTube URL 的正則表達式模式
    youtube_regex = (
        r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)'
        r'[A-Za-z0-9_-]{11}.*'
    )
    
    if not url:
        return False
    
    # 檢查是否匹配 YouTube URL 格式
    match = re.match(youtube_regex, url)
    if not match:
        return False
    
    return True

@app.route('/tasks')
def tasks_page():
    try:
        tasks = task_manager.get_all_tasks()
        serialized_tasks = [task_manager._serialize_task(task) for task in tasks]
        return render_template('tasks.html', tasks=serialized_tasks)
    except Exception as e:
        logger.error(f'Error rendering tasks page: {str(e)}')
        return str(e), 500

@app.route('/api/tasks')
def get_tasks():
    tasks = task_manager.get_all_tasks()
    return jsonify([task_manager._serialize_task(task) for task in tasks])

@app.route('/summarize', methods=['POST'])
def summarize():
    url = request.form.get('url')
    language = request.form.get('language', 'zh')
    prompt_type = request.form.get('promptType', 'general')
    
    # 添加到任務隊列
    task_id = task_manager.add_task(url, language, prompt_type)
    
    return jsonify({
        "status": "accepted",
        "message": "Task added to queue",
        "task_id": task_id
    })

@app.route('/resummary', methods=['POST'])
def resummary():
    logger.debug('Received resummary request')
    session = Session()
    try:
        record_id = request.form.get('recordId')
        prompt_type = request.form.get('promptType')
        language = request.form.get('language')
        
        logger.debug(f'Resummary request for record {record_id} with prompt {prompt_type}')
        
        # 使用新的 session.get() 方法
        record = session.get(VideoRecord, record_id)
        if not record:
            logger.debug(f'Record not found for ID {record_id}')
            return jsonify({"error": "Record not found"}), 500

        # 檢查轉錄文件是否存在
        if not os.path.exists(record.transcript_file):
            logger.debug(f'Transcript file not found for record {record_id}')
            return jsonify({"error": "Transcript file not found"}), 500
            
        # 開始重新摘要
        thread = threading.Thread(
            target=process_resummary,
            args=(record.video_source, record.transcript_file, record.video_title, language, socketio, prompt_type)
        )
        thread.start()
        
        return jsonify({"status": "processing", "message": "Resummary started"})
        
    except Exception as e:
        logger.error(f'Error in resummary: {str(e)}')
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

def process_resummary(url, transcript_file, title, language, socketio, prompt_type):
    logger.debug(f'Resummarizing video: {url}')
    """處理重新摘要的請求"""
    try:
        # 直接使用現有的轉錄文件生成新的摘要
        summary_content, summary_path = generate_summary(transcript_file, socketio, prompt_type)
        
        # 建立新的資料庫記錄
        session = Session()
        VideoRecord.create_record(
            session=session,
            video_source=url,
            title=f"{title}_Resummary_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            audio_path=None,  # 重新摘要不需要音頻文件
            transcript_path=transcript_file,  # 使用原始轉錄文件
            summary_path=summary_path,
            prompt_type=prompt_type,
            language=language
        )
        
        socketio.emit('resummary_complete', {'result': summary_content})
    except Exception as e:
        logger.error(f'Error in process_resummary: {str(e)}')
        socketio.emit('resummary_error', {'error': str(e)})
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
        

@app.route('/history')
def history():
    logger.debug('Accessing history page')
    try:
        session = Session()
        records = VideoRecord.get_all_records(session)
        prompts = prompt_manager.get_all_prompts()  # 獲取所有可用的提示詞
        return render_template('history.html', records=records, prompts=prompts)
    finally:
        session.close()

@app.route('/delete_record/<int:record_id>', methods=['POST'])
def delete_record(record_id):
    session = Session()
    try:
        # 更新為使用 session.get()
        record = session.get(VideoRecord, record_id)
        if record:
            record.delete_record(session)
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Record not found'})
    except Exception as e:
        logger.error(f'Error deleting record: {str(e)}')
        return jsonify({'success': False, 'error': str(e)})
    finally:
        session.close()

@app.route('/batch_delete', methods=['POST'])
def batch_delete():
    session = Session()
    try:
        data = request.get_json()
        record_ids = data.get('ids', [])
        
        if not record_ids:
            return jsonify({'success': False, 'error': 'No records selected'})

        deleted_count = 0
        failed_ids = []
        
        for record_id in record_ids:
            try:
                record = session.get(VideoRecord, record_id)
                if record:
                    record.delete_record(session)
                    deleted_count += 1
            except Exception as e:
                logger.error(f'Error deleting record {record_id}: {str(e)}')
                failed_ids.append(record_id)
        
        if failed_ids:
            return jsonify({
                'success': False, 
                'error': f'Failed to delete some records: {failed_ids}',
                'deleted_count': deleted_count
            })
            
        return jsonify({
            'success': True, 
            'message': f'Successfully deleted {deleted_count} records'
        })
        
    except Exception as e:
        logger.error(f'Error in batch delete: {str(e)}')
        return jsonify({'success': False, 'error': str(e)})
    finally:
        session.close()

@app.route('/get_summary/<int:record_id>')
def get_summary(record_id):
    session = Session()
    try:
        # 更新為使用 session.get()
        record = session.get(VideoRecord, record_id)
        if record and os.path.exists(record.summary_file):
            with open(record.summary_file, 'r', encoding='utf-8') as f:
                content = f.read()
                content = '## Title: ' + record.video_title + '\n\n' + 'Source: ' + record.video_source + '\n\n' + content
            return jsonify({'success': True, 'content': content})
        return jsonify({'success': False, 'error': 'File not found'})
    finally:
        session.close()

@app.route('/download/<int:record_id>/<file_type>')
def download_file(record_id, file_type):
    session = Session()
    try:
        # 更新為使用 session.get()
        record = session.get(VideoRecord, record_id)
        if not record:
            return "Record not found", 404
            
        file_path = None
        if file_type == 'audio':
            file_path = record.audio_file
        elif file_type == 'transcript':
            file_path = record.transcript_file
        elif file_type == 'summary':
            file_path = record.summary_file
            
        if file_path and os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        return "File not found", 404
    finally:
        session.close()

@app.route('/upload', methods=['POST'])
def upload_media():
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未找到檔案'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '未選擇檔案'}), 400
            
        language = request.form.get('language', 'zh')
        prompt_type = request.form.get('promptType', 'general')
        
        allowed_extensions = {'mp4', 'mp3', 'wav', 'webm'}
        if not allowed_file(file.filename, allowed_extensions):
            return jsonify({'error': '不支援的檔案格式'}), 400
        
        filename = secure_filename(f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        audio_path = os.path.join(Config.AUDIO_DIR, filename)
        file.save(audio_path)
        
        # 傳入 is_local=True 標記本地檔案
        task_id = task_manager.add_task(
            source=audio_path,
            language=language, 
            prompt_type=prompt_type,
            is_local=True
        )
        
        return jsonify({
            'status': 'success',
            'message': '檔案上傳成功',
            'task_id': task_id
        })
        
    except Exception as e:
        logger.error(f'Upload error: {str(e)}')
        return jsonify({'error': str(e)}), 500

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

if __name__ == '__main__':
    logger.info("Starting YouTube Summarizer Application")
    socketio.run(app, debug=True, host=Config.BIND_ADDRESS, port=5000)
    
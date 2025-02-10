from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import os
import sys
import logging
from yt_downloader_worker import download_and_process_video  # 確保正確導入

# 設置日誌
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 添加當前目錄到 Python 路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    logger.debug('Accessing index page')
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f'Error rendering template: {str(e)}')
        return str(e), 500

@app.route('/summarize', methods=['POST'])
def summarize():
    logger.debug('Received summarize request')
    url = request.form.get('url')
    language = request.form.get('language', 'zh')
    logger.debug(f'URL: {url}, Language: {language}')
    
    thread = threading.Thread(target=process_video, args=(url, language))
    thread.start()
    
    return jsonify({"status": "processing", "message": "Video processing started"})

def process_video(url, language):
    logger.debug(f'Processing video: {url}')
    try:
        result = download_and_process_video(url, language, socketio)
        logger.debug('Processing complete')
        socketio.emit('processing_complete', {'result': result})
    except Exception as e:
        logger.error(f'Error processing video: {str(e)}')
        socketio.emit('processing_error', {'error': str(e)})

if __name__ == '__main__':
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
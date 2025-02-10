# youtube_handler.py
from yt_dlp import YoutubeDL
import os
from config import Config
import re
import datetime

def get_video_title(url):
    """獲取 YouTube 影片標題"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('title', 'Unknown Title')
    except Exception as e:
        return f"Unknown Title ({str(e)})"

def get_safe_filename(filename: str, max_length: int = 100) -> str:
    """生成安全的文件名"""
    # 移除或替換不安全的字符
    safe_name = re.sub(r'[\\/*?:"<>|]', '', filename)
    # 將空格替換為底線
    safe_name = safe_name.replace(' ', '_')
    # 限制長度
    if len(safe_name) > max_length:
        # 保留擴展名
        name, ext = os.path.splitext(safe_name)
        safe_name = name[:max_length-len(ext)] + ext
    return safe_name

def download_video(URL, socketio):
    socketio.emit('processing_step', {'step': '1/4', 'message': '下載影片中...'})
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def ydl_progress_hook(d):
        if d['status'] == 'downloading':
            try:
                progress = round(float(d['downloaded_bytes'] * 100 / d['total_bytes']), 1)
                socketio.emit('processing_step', {
                    'step': '1/4',
                    'message': f'下載影片中... {progress}%'
                })
            except:
                pass

    ydl_opts = {
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'progress_hooks': [ydl_progress_hook],
        'quiet': True,
        'extractaudio': True,
        'audioformat': 'mp3',
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            # 先獲取影片信息
            info = ydl.extract_info(URL, download=False)
            # 使用時間戳和標題生成文件名
            safe_title = get_safe_filename(info['title'], max_length=50)  # 限制標題長度
            final_filename = f"{timestamp}_{safe_title}"
            
            # 設置輸出模板
            ydl_opts['outtmpl'] = os.path.join(Config.AUDIO_DIR, final_filename)
            
            # 下載影片
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([URL])
            
            # 返回完整的文件路徑（包含 .mp3 擴展名）
            return os.path.join(Config.AUDIO_DIR, final_filename + '.mp3')
    
    except Exception as e:
        socketio.emit('processing_error', {'error': f'下載失敗: {str(e)}'})
        raise Exception(f'下載失敗: {str(e)}')
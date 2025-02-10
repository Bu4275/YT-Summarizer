# video_processor.py
import logging
from youtube_handler import download_video, get_video_title
from whisper_handler import transcribe_audio
from summary_handler import generate_summary
from models import Session, VideoRecord
from config import Config
from task_progress import TaskProgress
import os

logger = logging.getLogger(__name__)

def process_video(source, language, socketio, prompt_type="general", is_local=False, progress=None):
    logger.debug(f'Processing {"local file" if is_local else "YouTube video"}: {source}')
    session = Session()
    
    try:
        if is_local:
            audio_filename = source
            video_title = os.path.basename(source)
            progress.update('1/3', '準備處理音頻文件', 33)
        else:
            video_title = get_video_title(source)
            progress.update('1/4', '下載影片中...', 25)
            audio_filename = download_video(source, socketio)

        step = '2/3' if is_local else '2/4'
        percentage = 66 if is_local else 50
        progress.update(step, '語音轉文字中...', percentage)
        text_filename = transcribe_audio(audio_filename, language, socketio)

        step = '3/3' if is_local else '3/4'
        percentage = 90 if is_local else 75
        progress.update(step, 'AI 摘要生成中...', percentage)
        summary_content, summary_path = generate_summary(text_filename, socketio, prompt_type)
        
        VideoRecord.create_record(
            session=session,
            video_source=source,
            title=video_title,
            audio_path=audio_filename,
            transcript_path=text_filename,
            summary_path=summary_path,
            prompt_type=prompt_type,
            language=language
        )

        logger.debug('Processing complete')
        progress.complete(summary_content)
        return summary_content
        
    except Exception as e:
        logger.error(f'Error processing file: {str(e)}')
        progress.error(str(e))
        raise
    finally:
        session.close()
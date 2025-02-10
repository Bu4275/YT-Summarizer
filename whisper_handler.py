# whisper_handler.py
import os
import time
from faster_whisper import WhisperModel
from config import Config
import logging
logger = logging.getLogger(__name__)
def transcribe_audio(filename, language, socketio):
    socketio.emit('processing_step', {'step': '2/4', 'message': '語音轉文字中...'})
    os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"

    model = WhisperModel(
        Config.WHISPER_MODEL_SIZE,
        device=Config.WHISPER_DEVICE,
        compute_type=Config.WHISPER_COMPUTE_TYPE,
    )

    segments, info = model.transcribe(filename, beam_size=5, language=language, condition_on_previous_text=False)
    total_duration = round(info.duration, 2)  # Same precision as the Whisper timestamps.
    timestamps = 0.0  # to get the current segments

    all_msg = ''
    for segment in segments:
        start_mini, start_sec = divmod(segment.start, 60)
        start_mini = str(int(start_mini)).zfill(2)
        start_sec = str(int(start_sec)).zfill(2)
        end_mini, end_sec = divmod(segment.end, 60)
        end_mini = str(int(end_mini)).zfill(2)
        end_sec = str(int(end_sec)).zfill(2)
        msg = "[%s:%s -> %s:%s] %s" % (start_mini, start_sec, end_mini, end_sec, segment.text)
        progress = round((segment.end / total_duration * 100), 2)
        socketio.emit('processing_step', {'step': '2/4', 'message': f'語音轉文字中... {progress}%'})
        logger.debug(f'msg = {msg}')
        all_msg += msg + '\n'

    socketio.emit('processing_step', {'step': '2/4', 'message': f'儲存轉錄文件...'})

    # 使用相同的文件名（但在不同目錄）
    base_name = os.path.basename(filename)
    name_without_ext = os.path.splitext(base_name)[0]
    save_filename = os.path.join(Config.TRANSCRIPT_DIR, name_without_ext + '.txt')

    with open(save_filename, "w", encoding='utf-8') as f:
        f.write(all_msg)
    time.sleep(3)
    socketio.emit('processing_step', {'step': '2/4', 'message': f'儲存完成...'})
    # import pdb; pdb.set_trace()
    return save_filename
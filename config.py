import os
import torch
from dotenv import load_dotenv

# 載入 .env 檔案中的環境變數
load_dotenv()

class Config:
    # 基本目錄設定
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    STORAGE_DIR = os.path.join(BASE_DIR, 'storage')
    
    # 各種檔案的儲存目錄
    AUDIO_DIR = os.path.join(STORAGE_DIR, 'audio')
    TRANSCRIPT_DIR = os.path.join(STORAGE_DIR, 'transcripts')
    SUMMARY_DIR = os.path.join(STORAGE_DIR, 'summaries')
    
    # OpenAI 設定
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    
    # Whisper 設定
    WHISPER_MODEL_SIZE = os.getenv('WHISPER_MODEL_SIZE', 'large-v2')

    if torch.cuda.is_available():
        WHISPER_DEVICE = "cuda"
        WHISPER_COMPUTE_TYPE = "float16"
    # elif torch.backends.mps.is_available():
    #     WHISPER_DEVICE = "mps"
    else:
        WHISPER_DEVICE = "cpu"
        WHISPER_COMPUTE_TYPE = "float32"

    BIND_ADDRESS = os.getenv('BIND_ADDRESS', '127.0.0.1')
# summary_handler.py
from openai import OpenAI
import os
import yaml
import datetime
import re
from dataclasses import dataclass
from typing import Dict
from config import Config

@dataclass
class PromptInfo:
    name: str
    description: str
    template: str
    icon: str

class PromptManager:
    def __init__(self):
        self.prompts: Dict[str, PromptInfo] = {}
        self.load_prompts()

    def load_prompts(self):
        """從 YAML 文件加載提示詞配置"""
        prompt_file = os.path.join(os.path.dirname(__file__), 'prompts.yaml')
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                for key, value in data.items():
                    self.prompts[key] = PromptInfo(
                        name=value['name'],
                        description=value['description'],
                        template=value['template'],
                        icon=value['icon']
                    )
        except Exception as e:
            print(f"Error loading prompts: {e}")
            # 加載失敗時使用默認提示詞
            self.prompts["general"] = PromptInfo(
                name="一般摘要",
                description="生成簡潔的內容摘要",
                icon="card-text",
                template="對以下 Youtube 影片進行摘要，提供重要內容和關鍵訊息的簡潔摘要。"
            )

    def get_prompt_template(self, prompt_type: str) -> str:
        """獲取指定類型的提示詞模板"""
        prompt_info = self.prompts.get(prompt_type)
        if not prompt_info:
            return self.prompts["general"].template
        return prompt_info.template

    def get_all_prompts(self):
        """獲取所有可用的提示詞信息"""
        return {key: {
            "name": info.name,
            "description": info.description,
            "icon": info.icon
        } for key, info in self.prompts.items()}

# 創建全局 PromptManager 實例
prompt_manager = PromptManager()

def get_safe_filename(base_name: str, prompt_type: str) -> str:
    """生成安全的檔案名稱"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # 使用時間戳和提示詞類型作為檔案名，而不是使用摘要內容
    safe_name = f"summary_{timestamp}_{prompt_type}"
    # 移除任何不安全的字符
    safe_name = re.sub(r'[\\/*?:"<>|]', '', safe_name)
    # 將空格替換為底線
    safe_name = safe_name.replace(' ', '_')
    return safe_name + '.txt'

def generate_summary(filename, socketio, prompt_type="general"):
    socketio.emit('processing_step', {'step': '3/4', 'message': 'AI 摘要生成中...'})
    
    try:
        api_key = Config.OPENAI_API_KEY
        if not api_key:
            raise ValueError("未設定 OpenAI API Key")
        
        client = OpenAI(api_key=api_key)
        
        with open(filename, 'r', encoding='utf-8') as f:
            transcription = f.read()
        
        # 使用 prompt_manager 獲取提示詞模板
        prompt_template = prompt_manager.get_prompt_template(prompt_type)
        if prompt_type == "none":
            summary = "不產生摘要"
        else:
            response = client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": prompt_template},
                    {"role": "assistant", "content": '使用繁體中文回答，逐字稿可能因為語音辨識問題導致錯字，根據情境自動修正錯字。'},
                    {"role": "user", "content": transcription}
                ],
                temperature=0,
            )
            
            summary = response.choices[0].message.content
        
        # 生成安全的檔案名稱
        summary_filename = get_safe_filename(os.path.basename(filename), prompt_type)
        safe_path = os.path.join(Config.SUMMARY_DIR, summary_filename)
        
        # 保存摘要內容
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(summary)
        
        socketio.emit('processing_step', {'step': '4/4', 'message': '處理完成！'})
        return summary, safe_path
    
    except Exception as e:
        error_msg = f"摘要生成失敗: {str(e)}"
        socketio.emit('processing_error', {'error': error_msg})
        raise Exception(error_msg)
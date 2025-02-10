# models.py
import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import Config
import enum
import json

# 創建資料庫引擎
engine = create_engine('sqlite:///youtube_summary.db')
Base = declarative_base()
Session = sessionmaker(bind=engine)

class VideoRecord(Base):
    __tablename__ = 'video_records'
    
    id = Column(Integer, primary_key=True)
    video_source = Column(String, nullable=False)
    video_title = Column(String)
    audio_file = Column(String)
    transcript_file = Column(String)
    summary_file = Column(String)
    prompt_type = Column(String)
    language = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now)

    @classmethod
    def create_record(cls, session, video_source, title, audio_path, transcript_path, summary_path, prompt_type, language):
        record = cls(
            video_source=video_source,
            video_title=title,
            audio_file=audio_path,
            transcript_file=transcript_path,
            summary_file=summary_path,
            prompt_type=prompt_type,
            language=language
        )
        session.add(record)
        session.commit()
        return record

    @classmethod
    def get_all_records(cls, session):
        return session.query(cls).order_by(cls.created_at.desc()).all()

    def delete_files(self):
        """刪除與記錄相關的所有文件"""
        files_to_delete = [
            self.audio_file,
            self.transcript_file,
            self.summary_file
        ]
        
        for file_path in files_to_delete:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")

    def delete_record(self, session):
        """刪除記錄及其關聯的文件"""
        try:
            # 先刪除文件
            # self.delete_files()
            # 再刪除資料庫記錄
            session.delete(self)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e



class TaskStatus(enum.Enum):
    WAITING = "waiting"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Task(Base):
    __tablename__ = 'tasks'
    
    id = Column(String, primary_key=True)
    source = Column(String, nullable=False)  # Changed from url to source
    language = Column(String)
    prompt_type = Column(String)
    status = Column(String)
    is_local = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    progress = Column(String)
    error = Column(String)
    result = Column(String)

    @property
    def progress_dict(self):
        if self.progress:
            return json.loads(self.progress)
        return None

    @progress_dict.setter
    def progress_dict(self, value):
        if value is not None:
            self.progress = json.dumps(value)
        else:
            self.progress = None

# 創建資料庫表
Base.metadata.create_all(engine)
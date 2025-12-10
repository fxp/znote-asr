#!/usr/bin/env python3
"""
数据库模型和操作
"""

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# 数据库文件路径（使用相对路径，便于迁移）
DB_PATH = os.getenv("DB_PATH", "asr_tasks.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# 创建数据库引擎
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明基类
Base = declarative_base()


class ASRTask(Base):
    """ASR转录任务模型"""
    __tablename__ = "asr_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    audio_url = Column(String, nullable=False, index=True)
    task_id = Column(String, unique=True, nullable=False, index=True)  # 火山引擎返回的任务ID
    status = Column(String, default="pending", index=True)  # pending, processing, completed, failed
    transcript = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "audio_url": self.audio_url,
            "task_id": self.task_id,
            "status": self.status,
            "transcript": self.transcript,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


#!/usr/bin/env python3
"""
Database models and operations
"""

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# Database file path (use relative path for easy migration)
DB_PATH = os.getenv("DB_PATH", "asr_tasks.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create database engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declare base class
Base = declarative_base()


class ASRTask(Base):
    """ASR transcription task model"""
    __tablename__ = "asr_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    audio_url = Column(String, nullable=False, index=True)
    task_id = Column(String, unique=True, nullable=False, index=True)  # Task ID returned by Volcano Engine
    status = Column(String, default="pending", index=True)  # pending, processing, completed, failed
    transcript = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary"""
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
    """Initialize database"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


#!/usr/bin/env python3
"""
Volcano Engine ASR Transcription API Service
Provides RESTful API endpoints for audio transcription
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from sqlalchemy.orm import Session
import uvicorn
import uuid
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from asr_transcribe import submit_asr_task, query_asr_result, format_as_openai_message, validate_audio_url
from database import init_db, get_db, ASRTask
from background_tasks import TaskPoller

# 全局任务轮询器
task_poller: Optional[TaskPoller] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # On startup
    global task_poller
    init_db()
    task_poller = TaskPoller(poll_interval=5)
    task_poller.start()
    yield
    # On shutdown
    if task_poller:
        task_poller.stop()


app = FastAPI(
    title="Volcano Engine ASR Transcription Service",
    description="Audio transcription service using Volcano Engine speech recognition model",
    version="1.0.0",
    lifespan=lifespan
)


class TranscribeRequest(BaseModel):
    """Transcription request model"""
    audio_url: HttpUrl
    max_retries: Optional[int] = 30
    retry_interval: Optional[int] = 3


class TranscribeResponse(BaseModel):
    """Transcription response model"""
    success: bool
    message: Optional[str] = None
    data: Optional[dict] = None
    task_id: Optional[str] = None
    db_id: Optional[int] = None  # Database ID


class TaskStatusResponse(BaseModel):
    """Task status response model"""
    id: int
    task_id: str
    audio_url: str
    status: str
    transcript: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None


class TaskListResponse(BaseModel):
    """Task list response model"""
    total: int
    tasks: List[TaskStatusResponse]


@app.get("/")
async def root():
    """Root path, returns API information"""
    return {
        "service": "Volcano Engine ASR Transcription Service",
        "version": "1.0.0",
        "endpoints": {
            "POST /transcribe": "Submit transcription task (async, saved to database)",
            "GET /tasks": "Get all tasks list",
            "GET /tasks/{task_id}": "Get task by database ID",
            "GET /tasks/by-task-id/{volc_task_id}": "Get task by Volcano Engine task_id",
            "GET /status/{task_id}": "Get task status (legacy endpoint)",
            "POST /transcribe/sync": "Synchronous transcription (wait for result)"
        }
    }


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(request: TranscribeRequest, db: Session = Depends(get_db)):
    """
    Submit audio transcription task (async, saved to database)
    
    - **audio_url**: Public URL of the audio file
    - **max_retries**: Maximum retry count (optional, default 30, only for sync endpoint)
    - **retry_interval**: Retry interval in seconds (optional, default 3, only for sync endpoint)
    
    Returns task ID, background task will automatically poll and update results
    """
    audio_url = str(request.audio_url)
    
    try:
        # Validate audio URL before submitting
        is_valid, error_msg = validate_audio_url(audio_url)
        if not is_valid:
            # Create a failed task record
            db_task = ASRTask(
                audio_url=audio_url,
                task_id=f"failed_{uuid.uuid4().hex[:16]}",
                status="failed",
                error_message=f"Audio URL validation failed: {error_msg}"
            )
            db.add(db_task)
            db.commit()
            db.refresh(db_task)
            
            raise HTTPException(
                status_code=400,
                detail=f"Audio URL validation failed: {error_msg}"
            )
        
        # Submit to Volcano Engine
        volc_task_id, error_msg = submit_asr_task(audio_url)
        
        if not volc_task_id:
            # Create a failed task record
            db_task = ASRTask(
                audio_url=audio_url,
                task_id=f"failed_{uuid.uuid4().hex[:16]}",
                status="failed",
                error_message=f"Failed to submit transcription task: {error_msg}"
            )
            db.add(db_task)
            db.commit()
            db.refresh(db_task)
            
            raise HTTPException(
                status_code=500,
                detail=f"Failed to submit transcription task: {error_msg}"
            )
        
        # Save to database
        db_task = ASRTask(
            audio_url=audio_url,
            task_id=volc_task_id,
            status="pending"
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        
        return TranscribeResponse(
            success=True,
            message="Task submitted successfully, processing in background",
            task_id=volc_task_id,
            db_id=db_task.id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error occurred while submitting task: {str(e)}"
        )


@app.get("/tasks", response_model=TaskListResponse)
async def get_all_tasks(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get all tasks list
    
    - **status**: Optional, filter by status (pending, processing, completed, failed)
    - **limit**: Maximum number of results, default 100
    - **offset**: Offset for pagination, default 0
    """
    query = db.query(ASRTask)
    
    if status:
        query = query.filter(ASRTask.status == status)
    
    total = query.count()
    tasks = query.order_by(ASRTask.created_at.desc()).offset(offset).limit(limit).all()
    
    return TaskListResponse(
        total=total,
        tasks=[TaskStatusResponse(**task.to_dict()) for task in tasks]
    )


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_by_id(task_id: int, db: Session = Depends(get_db)):
    """
    Get task by database ID
    
    - **task_id**: Database task ID
    """
    task = db.query(ASRTask).filter(ASRTask.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )
    
    return TaskStatusResponse(**task.to_dict())


@app.get("/tasks/by-task-id/{volc_task_id}", response_model=TaskStatusResponse)
async def get_task_by_volc_id(volc_task_id: str, db: Session = Depends(get_db)):
    """
    Get task by Volcano Engine task_id
    
    - **volc_task_id**: Task ID returned by Volcano Engine
    """
    task = db.query(ASRTask).filter(ASRTask.task_id == volc_task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task {volc_task_id} not found"
        )
    
    return TaskStatusResponse(**task.to_dict())


@app.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """
    Get transcription task status (legacy endpoint)
    
    - **task_id**: Task ID (can be database ID or Volcano Engine task_id)
    
    First tries to query by Volcano Engine task_id, if not found, queries by database ID
    """
    # First try to query by Volcano Engine task_id
    task = db.query(ASRTask).filter(ASRTask.task_id == task_id).first()
    
    # If not found, try to query by database ID
    if not task:
        try:
            db_id = int(task_id)
            task = db.query(ASRTask).filter(ASRTask.id == db_id).first()
        except ValueError:
            pass
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )
    
    return TaskStatusResponse(**task.to_dict())


@app.post("/transcribe/sync", response_model=TranscribeResponse)
async def transcribe_audio_sync(request: TranscribeRequest, db: Session = Depends(get_db)):
    """
    Synchronous audio transcription (wait for result)
    
    - **audio_url**: Public URL of the audio file
    - **max_retries**: Maximum retry count (optional, default 30)
    - **retry_interval**: Retry interval in seconds (optional, default 3)
    
    This endpoint waits for transcription to complete and returns the result directly, also saves to database
    """
    audio_url = str(request.audio_url)
    
    try:
        # Validate audio URL before submitting
        is_valid, error_msg = validate_audio_url(audio_url)
        if not is_valid:
            # Create a failed task record
            db_task = ASRTask(
                audio_url=audio_url,
                task_id=f"failed_{uuid.uuid4().hex[:16]}",
                status="failed",
                error_message=f"Audio URL validation failed: {error_msg}"
            )
            db.add(db_task)
            db.commit()
            db.refresh(db_task)
            
            raise HTTPException(
                status_code=400,
                detail=f"Audio URL validation failed: {error_msg}"
            )
        
        # Submit to Volcano Engine
        volc_task_id, error_msg = submit_asr_task(audio_url)
        
        if not volc_task_id:
            # Create a failed task record
            db_task = ASRTask(
                audio_url=audio_url,
                task_id=f"failed_{uuid.uuid4().hex[:16]}",
                status="failed",
                error_message=f"Failed to submit transcription task: {error_msg}"
            )
            db.add(db_task)
            db.commit()
            db.refresh(db_task)
            
            raise HTTPException(
                status_code=500,
                detail=f"Failed to submit transcription task: {error_msg}"
            )
        
        # Save to database
        db_task = ASRTask(
            audio_url=audio_url,
            task_id=volc_task_id,
            status="processing"
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        
        # Query result (synchronous wait)
        transcript, error_msg = query_asr_result(
            volc_task_id,
            max_retries=request.max_retries,
            retry_interval=request.retry_interval
        )
        
        if not transcript:
            # Update status to failed if there's an error message
            if error_msg:
                db_task.status = "failed"
                db_task.error_message = error_msg
            else:
                # No error but no transcript, mark as processing (may still be processing)
                db_task.status = "processing"
            db.commit()
            
            raise HTTPException(
                status_code=500,
                detail=error_msg or "Failed to get transcription result, task may still be processing"
            )
        
        # Update database
        db_task.status = "completed"
        db_task.transcript = transcript
        from datetime import datetime
        db_task.completed_at = datetime.utcnow()
        db.commit()
        
        # Format as OpenAI message format
        openai_message = format_as_openai_message(transcript)
        
        return TranscribeResponse(
            success=True,
            message="Transcription completed successfully",
            task_id=volc_task_id,
            db_id=db_task.id,
            data=openai_message
        )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error occurred during transcription: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

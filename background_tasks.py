#!/usr/bin/env python3
"""
Background task: Periodically query incomplete transcription tasks
"""

import time
import threading
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal, ASRTask
from asr_transcribe import query_asr_result_once

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskPoller:
    """Task poller"""
    
    def __init__(self, poll_interval: int = 5):
        """
        Initialize task poller
        
        Args:
            poll_interval: Polling interval in seconds
        """
        self.poll_interval = poll_interval
        self.running = False
        self.thread = None
    
    def start(self):
        """Start polling thread"""
        if self.running:
            logger.warning("Poller is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        logger.info(f"Task poller started, polling interval: {self.poll_interval} seconds")
    
    def stop(self):
        """Stop polling thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Task poller stopped")
    
    def _poll_loop(self):
        """Polling loop"""
        while self.running:
            try:
                self._check_pending_tasks()
            except Exception as e:
                logger.error(f"Error while polling tasks: {e}", exc_info=True)
            
            # Wait for specified interval
            time.sleep(self.poll_interval)
    
    def _check_pending_tasks(self):
        """Check and update pending tasks"""
        db: Session = SessionLocal()
        try:
            # Query all incomplete tasks
            pending_tasks = db.query(ASRTask).filter(
                ASRTask.status.in_(["pending", "processing"])
            ).all()
            
            if not pending_tasks:
                return
            
            logger.info(f"Found {len(pending_tasks)} pending tasks")
            
            for task in pending_tasks:
                try:
                    # Update status to processing (if still pending)
                    if task.status == "pending":
                        task.status = "processing"
                        task.updated_at = datetime.utcnow()
                        db.commit()
                    
                    # Query transcription result
                    transcript, error_msg = query_asr_result_once(task.task_id)
                    
                    if error_msg:
                        # Task failed, has error message
                        task.status = "failed"
                        task.error_message = error_msg
                        task.updated_at = datetime.utcnow()
                        db.commit()
                        logger.warning(f"Task {task.id} (task_id: {task.task_id}) failed: {error_msg}")
                    elif transcript is not None:
                        # Task completed (including empty string, meaning no valid speech)
                        task.status = "completed"
                        task.transcript = transcript if transcript else ""  # Save empty string to indicate completed but no content
                        task.completed_at = datetime.utcnow()
                        task.updated_at = datetime.utcnow()
                        db.commit()
                        if transcript:
                            logger.info(f"Task {task.id} (task_id: {task.task_id}) completed, transcript: {transcript[:50]}...")
                        else:
                            logger.info(f"Task {task.id} (task_id: {task.task_id}) completed, but no valid speech in audio")
                    else:
                        # Task still processing (transcript is None means still processing)
                        task.updated_at = datetime.utcnow()
                        db.commit()
                        logger.debug(f"Task {task.id} (task_id: {task.task_id}) still processing")
                
                except Exception as e:
                    logger.error(f"Error processing task {task.id}: {e}", exc_info=True)
                    # Mark as failed
                    task.status = "failed"
                    task.error_message = f"Internal error: {str(e)}"
                    task.updated_at = datetime.utcnow()
                    db.commit()
        
        finally:
            db.close()


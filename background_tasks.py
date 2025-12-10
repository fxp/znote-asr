#!/usr/bin/env python3
"""
后台任务：定期查询未完成的转录任务
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
    """任务轮询器"""
    
    def __init__(self, poll_interval: int = 5):
        """
        初始化任务轮询器
        
        Args:
            poll_interval: 轮询间隔（秒）
        """
        self.poll_interval = poll_interval
        self.running = False
        self.thread = None
    
    def start(self):
        """启动轮询线程"""
        if self.running:
            logger.warning("轮询器已在运行")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        logger.info(f"任务轮询器已启动，轮询间隔: {self.poll_interval}秒")
    
    def stop(self):
        """停止轮询线程"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("任务轮询器已停止")
    
    def _poll_loop(self):
        """轮询循环"""
        while self.running:
            try:
                self._check_pending_tasks()
            except Exception as e:
                logger.error(f"轮询任务时发生错误: {e}", exc_info=True)
            
            # 等待指定间隔
            time.sleep(self.poll_interval)
    
    def _check_pending_tasks(self):
        """检查并更新待处理的任务"""
        db: Session = SessionLocal()
        try:
            # 查询所有未完成的任务
            pending_tasks = db.query(ASRTask).filter(
                ASRTask.status.in_(["pending", "processing"])
            ).all()
            
            if not pending_tasks:
                return
            
            logger.info(f"发现 {len(pending_tasks)} 个待处理任务")
            
            for task in pending_tasks:
                try:
                    # 更新状态为processing（如果还是pending）
                    if task.status == "pending":
                        task.status = "processing"
                        task.updated_at = datetime.utcnow()
                        db.commit()
                    
                    # 查询转录结果
                    transcript, error_msg = query_asr_result_once(task.task_id)
                    
                    if error_msg:
                        # 任务失败，有错误信息
                        task.status = "failed"
                        task.error_message = error_msg
                        task.updated_at = datetime.utcnow()
                        db.commit()
                        logger.warning(f"任务 {task.id} (task_id: {task.task_id}) 失败: {error_msg}")
                    elif transcript is not None:
                        # 任务完成（包括空字符串，表示无有效语音）
                        task.status = "completed"
                        task.transcript = transcript if transcript else ""  # 保存空字符串表示已完成但无内容
                        task.completed_at = datetime.utcnow()
                        task.updated_at = datetime.utcnow()
                        db.commit()
                        if transcript:
                            logger.info(f"任务 {task.id} (task_id: {task.task_id}) 已完成，转录: {transcript[:50]}...")
                        else:
                            logger.info(f"任务 {task.id} (task_id: {task.task_id}) 已完成，但音频中无有效语音内容")
                    else:
                        # 任务仍在处理中（transcript为None表示还在处理）
                        task.updated_at = datetime.utcnow()
                        db.commit()
                        logger.debug(f"任务 {task.id} (task_id: {task.task_id}) 仍在处理中")
                
                except Exception as e:
                    logger.error(f"处理任务 {task.id} 时发生错误: {e}", exc_info=True)
                    # 标记为失败
                    task.status = "failed"
                    task.error_message = f"Internal error: {str(e)}"
                    task.updated_at = datetime.utcnow()
                    db.commit()
        
        finally:
            db.close()


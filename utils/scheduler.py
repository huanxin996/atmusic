"""
定时任务调度模块
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Callable, Optional
from utils.logger import logger


class TaskScheduler:
    """定时任务调度器"""
    
    _instance: Optional["TaskScheduler"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.scheduler = AsyncIOScheduler()
        self.jobs = {}
        self._initialized = True
    
    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("⏰ 定时任务调度器已启动")
    
    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("⏰ 定时任务调度器已停止")
    
    def add_daily_job(
        self,
        job_id: str,
        func: Callable,
        hour: int = 8,
        minute: int = 0,
        **kwargs
    ):
        """添加每日定时任务"""
        if job_id in self.jobs:
            self.remove_job(job_id)
        
        trigger = CronTrigger(hour=hour, minute=minute)
        job = self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            **kwargs
        )
        self.jobs[job_id] = job
        logger.info(f"✅ 添加定时任务: {job_id}, 执行时间: {hour:02d}:{minute:02d}")
        return job
    
    def remove_job(self, job_id: str):
        """移除定时任务"""
        if job_id in self.jobs:
            self.scheduler.remove_job(job_id)
            del self.jobs[job_id]
            logger.info(f"🗑️ 移除定时任务: {job_id}")
    
    def get_jobs(self) -> list:
        """获取所有任务"""
        return [
            {
                "id": job.id,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            }
            for job in self.scheduler.get_jobs()
        ]
    
    def pause_job(self, job_id: str):
        """暂停任务"""
        if job_id in self.jobs:
            self.scheduler.pause_job(job_id)
            logger.info(f"⏸️ 暂停任务: {job_id}")
    
    def resume_job(self, job_id: str):
        """恢复任务"""
        if job_id in self.jobs:
            self.scheduler.resume_job(job_id)
            logger.info(f"▶️ 恢复任务: {job_id}")


# 全局调度器实例
scheduler = TaskScheduler()


def get_scheduler() -> TaskScheduler:
    """获取调度器实例"""
    return scheduler

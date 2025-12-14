"""
数据库模块 - SQLAlchemy异步ORM
"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from pathlib import Path
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from config import settings
from utils.logger import logger


class Base(DeclarativeBase):
    """ORM基类"""
    pass


# 确保数据目录存在
data_dir = Path(__file__).parent.parent / "data"
data_dir.mkdir(exist_ok=True)


class SQLAlchemyLoguruHandler(logging.Handler):
    """将SQLAlchemy日志转发到loguru"""
    
    def emit(self, record):
        try:
            msg = self.format(record)
            # 根据日志级别使用不同的logger方法
            if record.levelno >= logging.ERROR:
                logger.error(f"[SQLAlchemy] {msg}")
            elif record.levelno >= logging.WARNING:
                logger.warning(f"[SQLAlchemy] {msg}")
            elif record.levelno >= logging.INFO:
                logger.info(f"[SQLAlchemy] {msg}")
            else:
                logger.debug(f"[SQLAlchemy] {msg}")
        except Exception:
            self.handleError(record)


def _setup_sqlalchemy_logging():
    """配置SQLAlchemy日志 - 完全禁用"""
    # 获取SQLAlchemy的日志记录器
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    
    # 清除所有处理器
    sqlalchemy_logger.handlers.clear()
    
    # 完全禁用SQLAlchemy日志
    sqlalchemy_logger.setLevel(logging.CRITICAL)
    sqlalchemy_logger.propagate = False
    
    # 同时禁用其他SQLAlchemy相关日志
    for name in ["sqlalchemy", "sqlalchemy.pool", "sqlalchemy.dialects", "sqlalchemy.orm"]:
        logger_obj = logging.getLogger(name)
        logger_obj.handlers.clear()
        logger_obj.setLevel(logging.CRITICAL)
        logger_obj.propagate = False


# 配置SQLAlchemy日志
_setup_sqlalchemy_logging()

# 创建异步引擎 - echo=False 禁用默认SQL输出
engine = create_async_engine(
    settings.database_url,
    echo=False,  # 禁用内置echo，使用自定义日志处理
    future=True
)

# 创建会话工厂
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """初始化数据库"""
    from utils.models import User, PlayRecord, TaskLog, Playlist, PlayRanking  # 延迟导入避免循环
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session():
    """获取数据库会话 - 作为异步上下文管理器使用"""
    session = async_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

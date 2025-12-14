"""
网易云音乐刷歌助手 - 主入口
"""
import uvicorn
import asyncio
from config import settings
from utils.logger import logger
from web.app import app
from utils.database import init_db


async def startup():
    """应用启动"""
    logger.info("=" * 50)
    logger.info("🎵 网易云音乐刷歌助手启动中...")
    logger.info("=" * 50)
    
    # 初始化数据库
    await init_db()
    logger.info("✅ 数据库初始化完成")
    
    logger.info(f"🌐 服务地址: http://{settings.host}:{settings.port}")
    logger.info("=" * 50)


def main():
    """主函数"""
    
    # 使用 import string 启动 uvicorn（确保 reload/workers 可用）
    uvicorn.run(
        "web.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level="info" if settings.debug else "warning",
    )


if __name__ == "__main__":
    # 运行启动任务
    asyncio.run(startup())
    # 启动服务
    main()

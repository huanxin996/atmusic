"""
FastAPI应用工厂
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from contextlib import asynccontextmanager

from config import settings
from utils.logger import logger
from utils.scheduler import get_scheduler
from utils.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("🚀 应用启动中...")
    
    # 初始化数据库
    await init_db()
    
    # 启动定时任务调度器
    scheduler = get_scheduler()
    scheduler.start()
    
    logger.info("✅ 应用启动完成")
    
    yield
    
    # 关闭时
    logger.info("👋 应用关闭中...")
    scheduler.stop()
    logger.info("✅ 应用已关闭")


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    
    app = FastAPI(
        title="网易云音乐刷歌助手",
        description="自动化刷取每日听歌数量和时长",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )
    
    # 静态文件
    static_path = Path(__file__).parent.parent / "static"
    static_path.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    
    # 注册路由
    from web.routes import router as main_router
    from web.api import router as api_router
    
    app.include_router(main_router)
    app.include_router(api_router, prefix="/api")
    
    return app


# 在模块级创建 app 实例，供 uvicorn 以 import string 加载（支持 --reload）
app = create_app()

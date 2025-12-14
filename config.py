"""
配置管理模块
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """应用配置"""
    
    # 服务器配置
    host: str = Field(default="127.0.0.1", description="服务器地址")
    port: int = Field(default=8080, description="服务器端口")
    debug: bool = Field(default=True, description="调试模式")
    
    # 数据库配置
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/atmusic.db",
        description="数据库连接URL"
    )
    
    # 刷歌配置
    play_count: int = Field(default=300, description="每日刷歌数量")
    play_interval_min: int = Field(default=1, description="刷歌最小间隔(秒)")
    play_interval_max: int = Field(default=3, description="刷歌最大间隔(秒)")
    
    # 定时任务配置
    schedule_enabled: bool = Field(default=False, description="是否启用定时任务")
    schedule_hour: int = Field(default=8, description="定时执行小时")
    schedule_minute: int = Field(default=0, description="定时执行分钟")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 创建全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings

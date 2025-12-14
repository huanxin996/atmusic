"""
数据模型定义
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, JSON, BigInteger
from sqlalchemy.sql import func
from utils.database import Base


class User(Base):
    """用户模型"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(50), unique=True, nullable=False, comment="网易云用户ID")
    nickname = Column(String(100), comment="昵称")
    avatar_url = Column(String(500), comment="头像URL")
    background_url = Column(String(500), comment="背景图URL")
    signature = Column(String(500), default="", comment="签名")
    vip_type = Column(Integer, default=0, comment="VIP类型")
    level = Column(Integer, default=0, comment="等级")
    province = Column(Integer, default=0, comment="省份")
    city = Column(Integer, default=0, comment="城市")
    gender = Column(Integer, default=0, comment="性别: 0-未知 1-男 2-女")
    birthday = Column(BigInteger, default=0, comment="生日时间戳")
    listen_songs = Column(Integer, default=0, comment="听歌总数")
    follows = Column(Integer, default=0, comment="关注数")
    followeds = Column(Integer, default=0, comment="粉丝数")
    event_count = Column(Integer, default=0, comment="动态数")
    playlist_count = Column(Integer, default=0, comment="歌单数")
    create_days = Column(Integer, default=0, comment="注册天数")
    cookies = Column(Text, comment="登录Cookie")
    browser_headers = Column(JSON, comment="浏览器标头")
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_current = Column(Boolean, default=False, comment="是否为当前用户")
    last_login = Column(DateTime, comment="最后登录时间")
    last_sync = Column(DateTime, comment="最后同步时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def to_dict(self, include_cookies: bool = False):
        result = {
            "id": self.id,
            "uid": self.uid,
            "nickname": self.nickname,
            "avatar_url": self.avatar_url,
            "background_url": self.background_url,
            "signature": self.signature,
            "vip_type": self.vip_type,
            "level": self.level,
            "province": self.province,
            "city": self.city,
            "gender": self.gender,
            "birthday": self.birthday,
            "listen_songs": self.listen_songs,
            "follows": self.follows,
            "followeds": self.followeds,
            "event_count": self.event_count,
            "playlist_count": self.playlist_count,
            "create_days": self.create_days,
            "is_active": self.is_active,
            "is_current": self.is_current,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        if include_cookies:
            result["cookies"] = self.cookies
            result["browser_headers"] = self.browser_headers
        return result


class PlayRecord(Base):
    """播放记录模型"""
    __tablename__ = "play_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, comment="用户ID")
    date = Column(String(10), nullable=False, comment="日期 YYYY-MM-DD")
    song_count = Column(Integer, default=0, comment="听歌数量")
    play_time = Column(Float, default=0, comment="听歌时长(分钟)")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date,
            "song_count": self.song_count,
            "play_time": self.play_time,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class TaskLog(Base):
    """任务日志模型"""
    __tablename__ = "task_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, comment="用户ID")
    task_type = Column(String(50), nullable=False, comment="任务类型")
    status = Column(String(20), nullable=False, comment="状态: pending/running/success/failed")
    message = Column(Text, comment="消息")
    target_count = Column(Integer, default=0, comment="目标数量")
    current_count = Column(Integer, default=0, comment="当前数量")
    started_at = Column(DateTime, comment="开始时间")
    finished_at = Column(DateTime, comment="结束时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "task_type": self.task_type,
            "status": self.status,
            "message": self.message,
            "target_count": self.target_count,
            "current_count": self.current_count,
            "progress": round(self.current_count / self.target_count * 100, 1) if self.target_count > 0 else 0,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Playlist(Base):
    """用户歌单模型"""
    __tablename__ = "playlists"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_uid = Column(String(50), nullable=False, index=True, comment="用户UID")
    playlist_id = Column(String(50), nullable=False, comment="歌单ID")
    name = Column(String(200), comment="歌单名称")
    cover_url = Column(String(500), comment="封面URL")
    description = Column(Text, comment="描述")
    track_count = Column(Integer, default=0, comment="歌曲数量")
    play_count = Column(Integer, default=0, comment="播放次数")
    subscribed_count = Column(Integer, default=0, comment="收藏数")
    creator_uid = Column(String(50), comment="创建者UID")
    creator_nickname = Column(String(100), comment="创建者昵称")
    is_subscribed = Column(Boolean, default=False, comment="是否为收藏的歌单")
    create_time = Column(BigInteger, default=0, comment="歌单创建时间戳")
    update_time = Column(BigInteger, default=0, comment="歌单更新时间戳")
    created_at = Column(DateTime, server_default=func.now(), comment="记录创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="记录更新时间")
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_uid": self.user_uid,
            "playlist_id": self.playlist_id,
            "name": self.name,
            "cover_url": self.cover_url,
            "description": self.description,
            "track_count": self.track_count,
            "play_count": self.play_count,
            "subscribed_count": self.subscribed_count,
            "creator_uid": self.creator_uid,
            "creator_nickname": self.creator_nickname,
            "is_subscribed": self.is_subscribed,
            "create_time": self.create_time,
            "update_time": self.update_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class PlayRanking(Base):
    """听歌排行模型"""
    __tablename__ = "play_rankings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_uid = Column(String(50), nullable=False, index=True, comment="用户UID")
    song_id = Column(String(50), nullable=False, comment="歌曲ID")
    song_name = Column(String(200), comment="歌曲名称")
    artist_names = Column(String(500), comment="艺术家名称，逗号分隔")
    album_name = Column(String(200), comment="专辑名称")
    album_cover_url = Column(String(500), comment="专辑封面URL")
    play_count = Column(Integer, default=0, comment="播放次数")
    score = Column(Integer, default=0, comment="排行分数")
    ranking_type = Column(Integer, default=1, comment="排行类型: 0-总排行 1-周排行")
    rank_position = Column(Integer, default=0, comment="排名位置")
    created_at = Column(DateTime, server_default=func.now(), comment="记录创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="记录更新时间")
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_uid": self.user_uid,
            "song_id": self.song_id,
            "song_name": self.song_name,
            "artist_names": self.artist_names,
            "album_name": self.album_name,
            "album_cover_url": self.album_cover_url,
            "play_count": self.play_count,
            "score": self.score,
            "ranking_type": self.ranking_type,
            "rank_position": self.rank_position,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

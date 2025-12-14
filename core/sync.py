"""
用户数据同步模块 - 获取并存储用户的歌单、排行等数据
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import select, delete
from utils.database import get_session
from utils.models import User, Playlist, PlayRanking
from utils.logger import logger
from core.api import NetEaseAPI


async def sync_user_playlists(uid: str, api: NetEaseAPI) -> List[Dict[str, Any]]:
    """
    同步用户歌单数据
    
    Args:
        uid: 用户ID
        api: NetEaseAPI 实例
        
    Returns:
        歌单列表
    """
    try:
        # 获取歌单数据
        result = await api.get_user_playlists(uid, limit=1000)
        
        if result.get("code") != 200:
            logger.warning(f"获取用户歌单失败: {result}")
            return []
        
        playlists_data = result.get("playlist", [])
        if not playlists_data:
            logger.info(f"用户 {uid} 没有歌单")
            return []
        
        async with get_session() as session:
            # 删除该用户的旧歌单记录
            await session.execute(
                delete(Playlist).where(Playlist.user_uid == uid)
            )
            
            saved_playlists = []
            for pl in playlists_data:
                creator = pl.get("creator", {})
                
                playlist = Playlist(
                    user_uid=uid,
                    playlist_id=str(pl.get("id", "")),
                    name=pl.get("name", ""),
                    cover_url=pl.get("coverImgUrl", ""),
                    description=pl.get("description", ""),
                    track_count=pl.get("trackCount", 0),
                    play_count=pl.get("playCount", 0),
                    subscribed_count=pl.get("subscribedCount", 0),
                    creator_uid=str(creator.get("userId", "")),
                    creator_nickname=creator.get("nickname", ""),
                    is_subscribed=pl.get("subscribed", False),
                    create_time=pl.get("createTime", 0),
                    update_time=pl.get("updateTime", 0)
                )
                session.add(playlist)
                saved_playlists.append(playlist.to_dict())
            
            await session.commit()
            logger.info(f"✅ 用户 {uid} 歌单同步完成，共 {len(saved_playlists)} 个歌单")
            
        return saved_playlists
        
    except Exception as e:
        logger.error(f"同步用户歌单失败: {e}")
        return []


async def sync_user_play_ranking(
    uid: str, 
    api: NetEaseAPI, 
    ranking_type: int = 1
) -> List[Dict[str, Any]]:
    """
    同步用户听歌排行数据
    
    Args:
        uid: 用户ID
        api: NetEaseAPI 实例
        ranking_type: 0-总排行 1-周排行
        
    Returns:
        排行数据列表
    """
    try:
        result = await api.get_play_record(uid, ranking_type)
        
        if result.get("code") != 200:
            logger.warning(f"获取用户听歌排行失败: {result}")
            return []
        
        # 根据类型获取数据
        data_key = "weekData" if ranking_type == 1 else "allData"
        ranking_data = result.get(data_key, [])
        
        if not ranking_data:
            logger.info(f"用户 {uid} 没有{'周' if ranking_type == 1 else '总'}排行数据")
            return []
        
        async with get_session() as session:
            # 删除该用户该类型的旧排行记录
            await session.execute(
                delete(PlayRanking).where(
                    PlayRanking.user_uid == uid,
                    PlayRanking.ranking_type == ranking_type
                )
            )
            
            saved_rankings = []
            for idx, item in enumerate(ranking_data):
                song = item.get("song", {})
                artists = song.get("ar", song.get("artists", []))
                album = song.get("al", song.get("album", {}))
                
                artist_names = ", ".join([a.get("name", "") for a in artists if a.get("name")])
                
                ranking = PlayRanking(
                    user_uid=uid,
                    song_id=str(song.get("id", "")),
                    song_name=song.get("name", ""),
                    artist_names=artist_names,
                    album_name=album.get("name", ""),
                    album_cover_url=album.get("picUrl", ""),
                    play_count=item.get("playCount", 0),
                    score=item.get("score", 0),
                    ranking_type=ranking_type,
                    rank_position=idx + 1
                )
                session.add(ranking)
                saved_rankings.append(ranking.to_dict())
            
            await session.commit()
            type_name = "周" if ranking_type == 1 else "总"
            logger.info(f"✅ 用户 {uid} {type_name}排行同步完成，共 {len(saved_rankings)} 首歌")
            
        return saved_rankings
        
    except Exception as e:
        logger.error(f"同步用户听歌排行失败: {e}")
        return []


async def sync_all_user_data(uid: str, cookies: str, browser_headers: Dict[str, str] = None) -> Dict[str, Any]:
    """
    同步用户所有数据（用户信息、歌单、排行）
    
    Args:
        uid: 用户ID
        cookies: 用户Cookie
        browser_headers: 浏览器标头
        
    Returns:
        同步结果
    """
    api = NetEaseAPI(cookies, browser_headers=browser_headers)
    
    try:
        result = {
            "uid": uid,
            "success": True,
            "user_info": None,
            "playlists_count": 0,
            "week_ranking_count": 0,
            "all_ranking_count": 0,
            "synced_at": datetime.now().isoformat()
        }
        
        # 获取完整用户信息
        logger.info(f"开始同步用户 {uid} 的数据...")
        
        user_info = await api.get_user_full_info(uid)
        result["user_info"] = user_info
        
        # 更新用户信息到数据库
        async with get_session() as session:
            db_result = await session.execute(
                select(User).where(User.uid == uid)
            )
            user = db_result.scalar_one_or_none()
            
            if user:
                user.nickname = user_info.get("nickname", user.nickname)
                user.avatar_url = user_info.get("avatar_url", user.avatar_url)
                user.signature = user_info.get("signature", user.signature)
                user.vip_type = user_info.get("vip_type", user.vip_type)
                user.level = user_info.get("level", user.level)
                user.province = user_info.get("province", user.province)
                user.city = user_info.get("city", user.city)
                user.listen_songs = user_info.get("listen_songs", user.listen_songs)
                user.follows = user_info.get("follows", user.follows)
                user.followeds = user_info.get("followeds", user.followeds)
                user.event_count = user_info.get("event_count", user.event_count)
                user.playlist_count = user_info.get("playlist_count", user.playlist_count)
                user.create_days = user_info.get("create_days", user.create_days)
                user.last_sync = datetime.now()
                await session.commit()
                logger.info(f"✅ 用户 {uid} 信息已更新")
        
        # 同步歌单
        playlists = await sync_user_playlists(uid, api)
        result["playlists_count"] = len(playlists)
        
        # 同步周排行
        week_rankings = await sync_user_play_ranking(uid, api, ranking_type=1)
        result["week_ranking_count"] = len(week_rankings)
        
        # 同步总排行
        all_rankings = await sync_user_play_ranking(uid, api, ranking_type=0)
        result["all_ranking_count"] = len(all_rankings)
        
        logger.info(f"✅ 用户 {uid} 数据同步完成")
        return result
        
    except Exception as e:
        logger.error(f"同步用户数据失败: {e}")
        return {
            "uid": uid,
            "success": False,
            "error": str(e)
        }
    finally:
        await api.close()


async def get_cached_playlists(uid: str) -> List[Dict[str, Any]]:
    """
    获取缓存的歌单数据
    
    Args:
        uid: 用户ID
        
    Returns:
        歌单列表
    """
    try:
        async with get_session() as session:
            result = await session.execute(
                select(Playlist).where(Playlist.user_uid == uid).order_by(Playlist.id)
            )
            playlists = result.scalars().all()
            return [pl.to_dict() for pl in playlists]
    except Exception as e:
        logger.error(f"获取缓存歌单失败: {e}")
        return []


async def get_cached_rankings(uid: str, ranking_type: int = 1) -> List[Dict[str, Any]]:
    """
    获取缓存的排行数据
    
    Args:
        uid: 用户ID
        ranking_type: 0-总排行 1-周排行
        
    Returns:
        排行列表
    """
    try:
        async with get_session() as session:
            result = await session.execute(
                select(PlayRanking).where(
                    PlayRanking.user_uid == uid,
                    PlayRanking.ranking_type == ranking_type
                ).order_by(PlayRanking.rank_position)
            )
            rankings = result.scalars().all()
            return [r.to_dict() for r in rankings]
    except Exception as e:
        logger.error(f"获取缓存排行失败: {e}")
        return []


async def check_and_sync_data(
    uid: str, 
    cookies: str, 
    browser_headers: Dict[str, str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    检查是否需要同步数据，如果需要则同步
    
    优先返回缓存数据，后台检查更新
    
    Args:
        uid: 用户ID
        cookies: 用户Cookie
        browser_headers: 浏览器标头
        force: 是否强制同步
        
    Returns:
        数据结果
    """
    # 先获取缓存数据
    cached_playlists = await get_cached_playlists(uid)
    cached_week_rankings = await get_cached_rankings(uid, 1)
    cached_all_rankings = await get_cached_rankings(uid, 0)
    
    # 检查是否需要同步
    need_sync = force or not cached_playlists
    
    if not need_sync:
        # 检查上次同步时间
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.uid == uid)
            )
            user = result.scalar_one_or_none()
            if user and user.last_sync:
                # 如果超过1小时没同步，则需要同步
                hours_since_sync = (datetime.now() - user.last_sync).total_seconds() / 3600
                if hours_since_sync > 1:
                    need_sync = True
            else:
                need_sync = True
    
    result = {
        "from_cache": not need_sync or bool(cached_playlists),
        "playlists": cached_playlists,
        "week_rankings": cached_week_rankings,
        "all_rankings": cached_all_rankings
    }
    
    # 如果需要同步，则执行同步
    if need_sync:
        sync_result = await sync_all_user_data(uid, cookies, browser_headers)
        if sync_result.get("success"):
            # 重新获取数据
            result["playlists"] = await get_cached_playlists(uid)
            result["week_rankings"] = await get_cached_rankings(uid, 1)
            result["all_rankings"] = await get_cached_rankings(uid, 0)
            result["synced"] = True
            result["from_cache"] = False
    
    return result

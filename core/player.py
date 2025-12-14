"""
播放器模块 - 刷歌核心逻辑
"""
import asyncio
import random
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from core.api import NetEaseAPI
from utils.logger import logger
from config import settings


class MusicPlayer:
    """音乐播放器(刷歌核心)"""
    
    def __init__(self, cookies: str):
        self.api = NetEaseAPI(cookies)
        self.is_running = False
        self._stop_flag = False
        self.current_progress = 0
        self.total_count = 0
        self.played_songs: List[str] = []
    
    async def close(self):
        """关闭资源"""
        await self.api.close()
    
    async def get_songs_from_recommend(self) -> List[Dict]:
        """获取每日推荐歌曲 - 支持v2和v3版本API返回格式"""
        try:
            result = await self.api.get_recommend_songs()
            if result.get("code") == 200:
                # v2版本返回 recommend 数组
                songs = result.get("recommend", [])
                # v3版本返回 data.dailySongs 数组（兼容）
                if not songs:
                    songs = result.get("data", {}).get("dailySongs", [])
                return [{"id": str(s["id"]), "name": s["name"]} for s in songs]
        except Exception as e:
            logger.error(f"获取推荐歌曲失败: {str(e)}")
        return []
    
    async def get_songs_from_playlist(self, playlist_id: str) -> List[Dict]:
        """从歌单获取歌曲"""
        try:
            result = await self.api.get_playlist_detail(playlist_id)
            if result.get("code") == 200:
                tracks = result.get("playlist", {}).get("tracks", [])
                return [{"id": str(t["id"]), "name": t["name"]} for t in tracks]
        except Exception as e:
            logger.error(f"获取歌单歌曲失败: {str(e)}")
        return []
    
    async def get_user_playlists(self, uid: str) -> List[Dict]:
        """获取用户歌单列表"""
        try:
            result = await self.api.get_user_playlist(uid)
            if result.get("code") == 200:
                playlists = result.get("playlist", [])
                return [
                    {
                        "id": str(p["id"]),
                        "name": p["name"],
                        "track_count": p["trackCount"],
                        "cover": p.get("coverImgUrl", "")
                    }
                    for p in playlists
                ]
        except Exception as e:
            logger.error(f"获取用户歌单失败: {str(e)}")
        return []
    
    async def get_songs_from_discover_playlists(self, count: int = 500, cat: str = None) -> List[Dict]:
        """
        从发现歌单页面获取歌曲
        
        Args:
            count: 需要的歌曲数量
            cat: 歌单分类（如：华语、流行、摇滚等）
            
        Returns:
            歌曲列表 [{id, name}, ...]
        """
        try:
            # 获取发现页面的歌单列表
            playlists = await self.api.get_discover_playlists_from_html(cat=cat, limit=35)
            if not playlists:
                logger.warning("未获取到发现歌单")
                return []
            
            logger.info(f"从发现页面获取到 {len(playlists)} 个歌单")
            
            all_songs = []
            used_song_ids = set()
            
            # 遍历歌单获取歌曲
            for playlist in playlists:
                if len(all_songs) >= count:
                    break
                    
                playlist_id = playlist.get("id")
                playlist_name = playlist.get("name", "未知歌单")
                
                try:
                    songs = await self.get_songs_from_playlist(playlist_id)
                    if songs:
                        # 去重添加
                        new_songs = []
                        for song in songs:
                            if song["id"] not in used_song_ids:
                                used_song_ids.add(song["id"])
                                new_songs.append(song)
                        
                        all_songs.extend(new_songs)
                        logger.debug(f"从歌单 [{playlist_name}] 获取到 {len(new_songs)} 首新歌曲")
                except Exception as e:
                    logger.warning(f"获取歌单 [{playlist_name}] 歌曲失败: {e}")
                    continue
                
                # 添加延迟避免请求过快
                await asyncio.sleep(0.5)
            
            # 随机打乱顺序
            random.shuffle(all_songs)
            
            logger.info(f"从发现歌单共获取 {len(all_songs)} 首歌曲")
            return all_songs[:count]
            
        except Exception as e:
            logger.error(f"从发现歌单获取歌曲失败: {e}")
            return []
    
    async def play_song(self, song_id: str, source_id: str = "", duration: int = None, play_time: int = None) -> bool:
        """
        播放/上报单首歌曲
        
        Args:
            song_id: 歌曲ID
            source_id: 来源歌单ID
            duration: 播放时长(秒), None则随机180-300秒
            play_time: 播放时长(秒), duration的别名
        """
        # 优先使用 play_time，其次 duration，最后随机
        if play_time is not None:
            duration = play_time
        elif duration is None:
            duration = random.randint(180, 300)
        
        try:
            result = await self.api.scrobble(song_id, source_id, duration)
            success = result.get("code") == 200
            if success:
                logger.debug(f"✅ 上报成功: 歌曲ID={song_id}, 时长={duration}秒")
            else:
                logger.warning(f"⚠️ 上报失败: 歌曲ID={song_id}, 响应={result}")
            return success
        except Exception as e:
            logger.error(f"❌ 播放歌曲失败: {str(e)}")
            return False
    
    async def batch_play(
        self,
        songs: List[Dict],
        count: int = 300,
        source_id: str = "",
        progress_callback: Callable[[int, int, Dict], None] = None
    ) -> Dict[str, Any]:
        """
        批量播放歌曲(刷歌主函数)
        
        Args:
            songs: 歌曲列表
            count: 刷歌数量
            source_id: 来源歌单ID
            progress_callback: 进度回调 (current, total, song_info)
        
        Returns:
            {
                "success": bool,
                "played_count": int,
                "total_time": float,  # 总时长(分钟)
                "message": str
            }
        """
        if not songs:
            return {"success": False, "message": "歌曲列表为空"}
        
        self.is_running = True
        self._stop_flag = False
        self.current_progress = 0
        self.total_count = min(count, len(songs) * 10)  # 最多循环10次歌单
        self.played_songs = []
        
        played_count = 0
        total_duration = 0
        start_time = datetime.now()
        
        logger.info(f"🎵 开始刷歌任务: 目标 {count} 首")
        
        try:
            song_index = 0
            while played_count < count and not self._stop_flag:
                # 循环歌单
                song = songs[song_index % len(songs)]
                song_id = song["id"]
                song_name = song.get("name", "未知歌曲")
                
                # 随机播放时长 (模拟真实听歌)
                duration = random.randint(180, 300)
                
                # 上报播放
                success = await self.play_song(song_id, source_id, duration)
                
                if success:
                    played_count += 1
                    total_duration += duration
                    self.current_progress = played_count
                    self.played_songs.append(song_id)
                    
                    if progress_callback:
                        progress_callback(played_count, count, song)
                    
                    logger.info(f"🎶 [{played_count}/{count}] {song_name}")
                
                # 随机间隔 (避免被检测)
                interval = random.uniform(
                    settings.play_interval_min,
                    settings.play_interval_max
                )
                await asyncio.sleep(interval)
                
                song_index += 1
            
            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()
            
            message = "任务完成" if not self._stop_flag else "任务被手动停止"
            
            result = {
                "success": True,
                "played_count": played_count,
                "total_time": round(total_duration / 60, 2),
                "elapsed_time": round(elapsed / 60, 2),
                "message": message
            }
            
            logger.info(f"✅ 刷歌任务结束: 播放 {played_count} 首, "
                       f"累计时长 {result['total_time']} 分钟, "
                       f"耗时 {result['elapsed_time']} 分钟")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 刷歌任务异常: {str(e)}")
            return {
                "success": False,
                "played_count": played_count,
                "total_time": round(total_duration / 60, 2),
                "message": str(e)
            }
        finally:
            self.is_running = False
    
    def stop(self):
        """停止刷歌任务"""
        self._stop_flag = True
        logger.info("⏹️ 收到停止信号, 正在停止...")
    
    def get_progress(self) -> Dict[str, Any]:
        """获取当前进度"""
        return {
            "is_running": self.is_running,
            "current": self.current_progress,
            "total": self.total_count,
            "progress": round(self.current_progress / self.total_count * 100, 1) if self.total_count > 0 else 0
        }

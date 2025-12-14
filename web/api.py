"""
API路由
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import asyncio
import json

from core.auth import QRCodeLogin, AuthManager
from core.player import MusicPlayer
from core.api import NetEaseAPI
from core.sync import sync_all_user_data, check_and_sync_data, get_cached_playlists, get_cached_rankings
from utils.logger import logger
from utils.session import (
    validate_session,
    save_user_session, get_user_session, get_current_session, get_all_users,
    switch_user, remove_user, update_user_info, validate_user_session
)
from utils.converter import (
    get_location, timestamp_to_date, timestamp_to_datetime,
    format_play_count, format_duration_ms
)
from config import settings

router = APIRouter()

# 全局状态管理
class AppState:
    current_user: dict = None
    cookies: str = None
    player: MusicPlayer = None
    active_task: asyncio.Task = None
    websockets: List[WebSocket] = []
    initialized: bool = False  # 是否已初始化（尝试恢复会话）

state = AppState()


async def try_restore_session():
    """尝试从数据库恢复会话"""
    if state.initialized:
        return
    
    state.initialized = True
    
    session = await get_current_session()
    if not session:
        logger.info("没有保存的会话")
        return
    
    cookies = session.get("cookies")
    user = session.get("user")
    
    if not cookies:
        logger.info("会话中没有Cookie")
        return
    
    logger.info("尝试恢复保存的会话...")
    
    # 验证Cookie是否仍然有效
    validated_user = await validate_session(cookies)
    
    if validated_user:
        state.cookies = cookies
        state.current_user = validated_user
        logger.info(f"✅ 会话恢复成功: {validated_user.get('nickname', '用户')}")
    elif user:
        # Cookie可能过期但有保存的用户信息，仍尝试使用
        state.cookies = cookies
        state.current_user = user
        logger.warning("⚠️ 无法验证Cookie，使用缓存的用户信息")
    else:
        logger.warning("❌ 保存的会话已失效")


# ==================== 请求模型 ====================

class LoginCookiesRequest(BaseModel):
    cookies: str


class LoginPasswordRequest(BaseModel):
    phone: str
    password: str
    country_code: str = "86"


class PlayRequest(BaseModel):
    count: int = 300
    playlist_id: Optional[str] = None


class ScheduleRequest(BaseModel):
    enabled: bool
    hour: int = 8
    minute: int = 0


# ==================== 认证相关API ====================

# 登录WebSocket连接管理
login_websockets: List[WebSocket] = []


@router.websocket("/ws/login")
async def login_websocket(websocket: WebSocket):
    """登录状态WebSocket - 用于二维码扫码状态推送"""
    await websocket.accept()
    login_websockets.append(websocket)
    logger.info(f"🔌 登录WebSocket连接: 当前连接数 {len(login_websockets)}")
    
    qr_login = None
    try:
        while True:
            # 接收消息
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action == "generate_qr":
                # 生成二维码
                qr_login = QRCodeLogin()
                result = await qr_login.generate_qr()
                await websocket.send_json({"type": "qr_generated", "data": result})
                
            elif action == "check_qr":
                # 检查二维码状态
                qr_key = data.get("qr_key")
                if qr_key and qr_login:
                    qr_login.qr_key = qr_key
                    result = await qr_login.check_status()
                    
                    # 登录成功处理
                    if result.get("code") == 803:
                        raw_cookies = result.get("cookies", "")
                        state.cookies = AuthManager.parse_cookies(raw_cookies)
                        
                        # 设置默认用户信息，稍后异步获取详情
                        state.current_user = {
                            "uid": "",
                            "nickname": "用户",
                            "avatar_url": "",
                            "level": 0
                        }
                        
                        # 尝试获取用户详情
                        if state.cookies:
                            api = NetEaseAPI(state.cookies)
                            try:
                                # 获取完整用户信息（API + HTML解析）
                                user_info = await api.get_user_full_info("")
                                
                                # 如果没有uid，尝试从登录状态获取
                                if not user_info.get("uid"):
                                    login_result = await api.get_login_status()
                                    if login_result.get("profile"):
                                        user_info["uid"] = str(login_result["profile"].get("userId", ""))
                                
                                if user_info.get("uid"):
                                    state.current_user = {
                                        "uid": user_info.get("uid", ""),
                                        "nickname": user_info.get("nickname", "用户"),
                                        "avatar_url": user_info.get("avatar_url", ""),
                                        "level": user_info.get("level", 0),
                                        "signature": user_info.get("signature", ""),
                                        "listen_songs": user_info.get("listen_songs", 0),
                                        "province": user_info.get("province", 0),
                                        "city": user_info.get("city", 0),
                                        "vip_type": user_info.get("vip_type", 0),
                                        "follows": user_info.get("follows", 0),
                                        "followeds": user_info.get("followeds", 0),
                                        "create_days": user_info.get("create_days", 0)
                                    }
                                    result["user"] = state.current_user
                                    logger.info(f"登录成功，用户: {state.current_user.get('nickname')}")
                                    
                                    # 保存会话到数据库，包含浏览器标头
                                    browser_headers = api.get_current_headers()
                                    await save_user_session(
                                        state.current_user["uid"], 
                                        state.cookies, 
                                        state.current_user,
                                        browser_headers
                                    )
                                    
                                    # 后台同步用户数据（歌单、排行）
                                    uid = state.current_user["uid"]
                                    asyncio.create_task(
                                        sync_all_user_data(uid, state.cookies, browser_headers)
                                    )
                            except Exception as e:
                                logger.warning(f"获取用户详情失败: {e}")
                            finally:
                                await api.close()
                        
                        result["user"] = state.current_user
                    
                    await websocket.send_json({"type": "qr_status", "data": result})
                    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"登录WebSocket错误: {e}")
    finally:
        if websocket in login_websockets:
            login_websockets.remove(websocket)
        if qr_login:
            await qr_login.close()
        logger.info(f"🔌 登录WebSocket断开: 当前连接数 {len(login_websockets)}")


# 状态WebSocket连接管理
status_websockets: List[WebSocket] = []


@router.websocket("/ws/status")
async def status_websocket(websocket: WebSocket):
    """状态WebSocket - 用于任务状态推送"""
    await websocket.accept()
    status_websockets.append(websocket)
    logger.info(f"🔌 状态WebSocket连接: 当前连接数 {len(status_websockets)}")
    
    try:
        # 发送初始状态
        await websocket.send_json({
            "type": "task_status",
            "play_count_running": state.active_task is not None,
            "play_time_running": False  # TODO: 添加时长任务状态
        })
        
        while True:
            # 接收心跳或消息
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30)
                # 处理客户端消息（如心跳）
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # 发送心跳保持连接
                await websocket.send_json({"type": "heartbeat"})
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"状态WebSocket错误: {e}")
    finally:
        if websocket in status_websockets:
            status_websockets.remove(websocket)
        logger.info(f"🔌 状态WebSocket断开: 当前连接数 {len(status_websockets)}")


async def broadcast_task_status(play_count_running: bool = False, play_time_running: bool = False):
    """广播任务状态到所有连接的客户端"""
    message = {
        "type": "task_status",
        "play_count_running": play_count_running,
        "play_time_running": play_time_running
    }
    for ws in status_websockets[:]:
        try:
            await ws.send_json(message)
        except Exception:
            status_websockets.remove(ws)


@router.get("/qr/generate")
async def generate_qr():
    """生成登录二维码"""
    qr_login = QRCodeLogin()
    try:
        result = await qr_login.generate_qr()
        return result
    finally:
        await qr_login.close()


@router.get("/qr/check/{key}")
async def check_qr(key: str):
    """检查二维码扫描状态"""
    qr_login = QRCodeLogin()
    qr_login.qr_key = key
    try:
        result = await qr_login.check_status()
        
        # 调试日志
        logger.info(f"二维码检查结果: {result}")
        
        # 登录成功，保存状态
        if result.get("code") == 803:
            raw_cookies = result.get("cookies", "")
            logger.debug(f"原始Cookie: {raw_cookies[:200] if raw_cookies else 'None'}...")
            
            # 解析cookie
            state.cookies = AuthManager.parse_cookies(raw_cookies)
            logger.info(f"解析后Cookie: {state.cookies[:100] if state.cookies else 'None'}...")
            
            if state.cookies:
                # 获取用户信息
                api = NetEaseAPI(state.cookies)
                try:
                    user_result = await api.get_login_status()
                    logger.debug(f"用户信息结果: {user_result}")
                    
                    if user_result.get("profile"):
                        profile = user_result["profile"]
                        state.current_user = {
                            "uid": str(profile["userId"]),
                            "nickname": profile["nickname"],
                            "avatar_url": profile.get("avatarUrl", ""),
                            "signature": profile.get("signature", ""),
                            "vip_type": profile.get("vipType", 0),
                            "level": profile.get("level", 0),
                            "province": profile.get("province", 0),
                            "city": profile.get("city", 0),
                            "listen_songs": profile.get("listenSongs", 0)
                        }
                        result["user"] = state.current_user
                        logger.info(f"登录成功，用户: {state.current_user.get('nickname')}")
                        
                        # 保存会话到数据库，包含浏览器标头
                        browser_headers = api.get_current_headers()
                        await save_user_session(
                            state.current_user["uid"], 
                            state.cookies, 
                            state.current_user,
                            browser_headers
                        )
                    else:
                        # 即使获取用户信息失败，也标记为登录成功
                        logger.warning("获取用户详情失败，但Cookie已保存")
                        state.current_user = {"uid": "", "nickname": "未知用户", "avatar_url": ""}
                        result["user"] = state.current_user
                except Exception as e:
                    logger.error(f"获取用户信息异常: {e}")
                    # 登录成功但获取信息失败，仍然保持登录状态
                    state.current_user = {"uid": "", "nickname": "未知用户", "avatar_url": ""}
                    result["user"] = state.current_user
                finally:
                    await api.close()
            else:
                logger.warning("Cookie解析为空")
        
        return result
    finally:
        await qr_login.close()


@router.post("/auth/cookies")
async def login_with_cookies(req: LoginCookiesRequest):
    """使用Cookie登录"""
    result = await AuthManager.validate_cookies(req.cookies)
    
    if result.get("valid"):
        state.cookies = req.cookies
        state.current_user = result.get("user")
        # 保存会话到数据库
        user_id = state.current_user.get("uid", "unknown")
        await save_user_session(user_id, state.cookies, state.current_user)
        
        # 后台同步用户数据
        asyncio.create_task(sync_all_user_data(user_id, state.cookies))
        
        return {"success": True, "user": state.current_user}
    
    raise HTTPException(status_code=401, detail=result.get("message", "Cookie无效"))


@router.post("/auth/password")
async def login_with_password(req: LoginPasswordRequest):
    """手机号密码登录"""
    result = await AuthManager.login_with_password(
        phone=req.phone,
        password=req.password,
        country_code=req.country_code
    )
    
    if result.get("success"):
        state.cookies = result.get("cookies", "")
        state.current_user = result.get("user")
        logger.info(f"用户 {state.current_user.get('nickname', '')} 登录成功")
        # 保存会话到数据库，包含浏览器标头
        user_id = state.current_user.get("uid", "unknown")
        browser_headers = result.get("browser_headers")
        await save_user_session(user_id, state.cookies, state.current_user, browser_headers)
        
        # 后台同步用户数据
        asyncio.create_task(sync_all_user_data(user_id, state.cookies, browser_headers))
        
        return {"success": True, "user": state.current_user}
    
    # 返回具体的错误信息
    raise HTTPException(
        status_code=401, 
        detail=result.get("message", "登录失败")
    )


@router.get("/auth/status")
async def get_auth_status():
    """获取登录状态"""
    # 首先尝试恢复保存的会话
    await try_restore_session()
    
    if state.current_user and state.cookies:
        # 如果已经有用户信息，直接返回登录状态，不再验证Cookie
        # 这避免了频繁的API调用和可能的风控问题
        return {"logged_in": True, "user": state.current_user}
    
    return {"logged_in": False}


@router.post("/auth/logout")
async def logout():
    """登出"""
    # 获取当前用户ID用于从数据库删除
    current_session = await get_current_session()
    if current_session:
        user_id = current_session.get("user_id")
        if user_id:
            await remove_user(user_id)
    
    state.current_user = None
    state.cookies = None
    
    if state.player:
        await state.player.close()
        state.player = None
    return {"success": True}


@router.post("/logout")
async def logout_alt():
    """登出（别名）"""
    return await logout()


@router.get("/user/info")
async def get_user_info():
    """获取当前用户详细信息"""
    if not state.cookies:
        raise HTTPException(status_code=401, detail="请先登录")
    
    api = NetEaseAPI(state.cookies)
    try:
        user_result = await api.get_login_status()
        logger.debug(f"用户信息API响应: {user_result}")
        
        if user_result:
            return {"code": 200, "data": user_result}
        else:
            # 如果API返回空，返回缓存的用户信息
            if state.current_user:
                return {
                    "code": 200,
                    "data": {
                        "profile": {
                            "userId": state.current_user.get("uid"),
                            "nickname": state.current_user.get("nickname", "用户"),
                            "avatarUrl": state.current_user.get("avatar_url", ""),
                            "signature": state.current_user.get("signature", ""),
                            "vipType": 0,
                            "follows": 0,
                            "followeds": 0,
                            "playlistCount": 0
                        }
                    }
                }
            raise HTTPException(status_code=401, detail="获取用户信息失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        # 返回缓存的用户信息
        if state.current_user:
            return {
                "code": 200,
                "data": {
                    "profile": {
                        "userId": state.current_user.get("uid"),
                        "nickname": state.current_user.get("nickname", "用户"),
                        "avatarUrl": state.current_user.get("avatar_url", ""),
                        "signature": "",
                        "vipType": 0,
                        "follows": 0,
                        "followeds": 0,
                        "playlistCount": 0
                    }
                }
            }
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api.close()


# ==================== 播放相关API ====================

@router.get("/playlists")
async def get_playlists():
    """获取用户歌单"""
    if not state.cookies or not state.current_user:
        raise HTTPException(status_code=401, detail="请先登录")
    
    player = MusicPlayer(state.cookies)
    try:
        playlists = await player.get_user_playlists(state.current_user["uid"])
        return {"success": True, "playlists": playlists}
    finally:
        await player.close()


@router.post("/play/start")
async def start_play(req: PlayRequest):
    """开始刷歌任务"""
    if not state.cookies:
        raise HTTPException(status_code=401, detail="请先登录")
    
    if state.player and state.player.is_running:
        raise HTTPException(status_code=400, detail="已有任务在运行")
    
    # 创建播放器
    state.player = MusicPlayer(state.cookies)
    
    # 获取歌曲
    if req.playlist_id:
        songs = await state.player.get_songs_from_playlist(req.playlist_id)
        source_id = req.playlist_id
    else:
        songs = await state.player.get_songs_from_recommend()
        source_id = ""
    
    if not songs:
        await state.player.close()
        raise HTTPException(status_code=400, detail="获取歌曲失败")
    
    # 进度回调
    async def broadcast_progress(current: int, total: int, song: dict):
        """广播进度到所有WebSocket"""
        message = {
            "type": "progress",
            "data": {
                "current": current,
                "total": total,
                "progress": round(current / total * 100, 1),
                "song": song
            }
        }
        for ws in state.websockets[:]:
            try:
                await ws.send_json(message)
            except:
                state.websockets.remove(ws)
    
    # 同步回调包装
    def progress_callback(current: int, total: int, song: dict):
        asyncio.create_task(broadcast_progress(current, total, song))
    
    # 异步执行任务
    async def run_task():
        try:
            result = await state.player.batch_play(
                songs=songs,
                count=req.count,
                source_id=source_id,
                progress_callback=progress_callback
            )
            # 广播完成消息
            for ws in state.websockets[:]:
                try:
                    await ws.send_json({"type": "complete", "data": result})
                except:
                    pass
        except Exception as e:
            logger.error(f"任务执行失败: {str(e)}")
        finally:
            if state.player:
                await state.player.close()
                state.player = None
    
    state.active_task = asyncio.create_task(run_task())
    
    return {
        "success": True,
        "message": f"任务已启动, 目标: {req.count}首",
        "songs_count": len(songs)
    }


@router.post("/play/stop")
async def stop_play():
    """停止刷歌任务"""
    if state.player and state.player.is_running:
        state.player.stop()
        return {"success": True, "message": "正在停止..."}
    return {"success": False, "message": "没有运行中的任务"}


@router.get("/play/status")
async def get_play_status():
    """获取播放状态"""
    if state.player:
        return {
            "running": state.player.is_running,
            "progress": state.player.get_progress()
        }
    return {"running": False, "progress": None}


# ==================== WebSocket ====================

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接 - 实时进度推送"""
    await websocket.accept()
    state.websockets.append(websocket)
    logger.info(f"🔌 WebSocket连接: 当前连接数 {len(state.websockets)}")
    
    try:
        while True:
            # 保持连接活跃
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        if websocket in state.websockets:
            state.websockets.remove(websocket)
        logger.info(f"🔌 WebSocket断开: 当前连接数 {len(state.websockets)}")


# ==================== 统计相关API ====================

@router.get("/stats/today")
async def get_today_stats():
    """获取今日统计"""
    if state.player:
        progress = state.player.get_progress()
        return {
            "played_count": progress.get("current", 0),
            "is_running": progress.get("is_running", False)
        }
    return {"played_count": 0, "is_running": False}


@router.get("/config")
async def get_config():
    """获取配置"""
    return {
        "play_count": settings.play_count,
        "play_interval_min": settings.play_interval_min,
        "play_interval_max": settings.play_interval_max,
        "schedule_enabled": settings.schedule_enabled,
        "schedule_hour": settings.schedule_hour,
        "schedule_minute": settings.schedule_minute
    }


# ==================== 任务管理WebSocket ====================

# 任务WebSocket连接
task_websockets: List[WebSocket] = []

# 任务状态
class TaskState:
    play_count_running: bool = False
    play_time_running: bool = False
    play_count_task: asyncio.Task = None
    play_time_task: asyncio.Task = None
    today_play_count: int = 0
    today_play_time: int = 0  # 秒

task_state = TaskState()


@router.websocket("/ws/task")
async def task_websocket(websocket: WebSocket):
    """任务状态WebSocket - 用于实时进度推送"""
    await websocket.accept()
    task_websockets.append(websocket)
    logger.info(f"🔌 任务WebSocket连接: 当前连接数 {len(task_websockets)}")
    
    try:
        # 发送当前状态
        await websocket.send_json({
            "type": "task_status",
            "task": "play_count",
            "running": task_state.play_count_running
        })
        await websocket.send_json({
            "type": "task_status",
            "task": "play_time",
            "running": task_state.play_time_running
        })
        await websocket.send_json({
            "type": "play_count",
            "count": task_state.today_play_count
        })
        await websocket.send_json({
            "type": "play_time",
            "seconds": task_state.today_play_time
        })
        
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in task_websockets:
            task_websockets.remove(websocket)
        logger.info(f"🔌 任务WebSocket断开: 当前连接数 {len(task_websockets)}")


async def broadcast_task_update(data: dict):
    """广播任务更新到所有WebSocket"""
    for ws in task_websockets[:]:
        try:
            await ws.send_json(data)
        except:
            if ws in task_websockets:
                task_websockets.remove(ws)


# ==================== 刷歌数量任务API ====================

class PlayCountTaskRequest(BaseModel):
    target: int = 300
    interval: int = 3


@router.post("/task/play-count/start")
async def start_play_count_task(req: PlayCountTaskRequest):
    """开始刷歌数量任务"""
    if not state.cookies:
        raise HTTPException(status_code=401, detail="请先登录")
    
    if task_state.play_count_running:
        return {"code": 400, "message": "任务已在运行中"}
    
    async def run_play_count_task():
        task_state.play_count_running = True
        await broadcast_task_update({"type": "task_status", "task": "play_count", "running": True})
        
        player = MusicPlayer(state.cookies)
        try:
            # 获取推荐歌曲
            songs = await player.get_songs_from_recommend()
            if not songs:
                await broadcast_task_update({
                    "type": "play_count",
                    "count": task_state.today_play_count,
                    "log": "获取歌曲失败",
                    "logType": "error"
                })
                return
            
            await broadcast_task_update({
                "type": "play_count",
                "count": task_state.today_play_count,
                "log": f"获取到 {len(songs)} 首歌曲，开始播放...",
                "logType": "info"
            })
            
            for i in range(req.target):
                if not task_state.play_count_running:
                    break
                
                song = songs[i % len(songs)]
                song_id = song.get("id")
                song_name = song.get("name", "未知")
                
                # 模拟播放
                success = await player.play_song(song_id, source_id="")
                
                if success:
                    task_state.today_play_count += 1
                    await broadcast_task_update({
                        "type": "play_count",
                        "count": task_state.today_play_count,
                        "log": f"[{task_state.today_play_count}/{req.target}] 播放: {song_name}",
                        "logType": "success"
                    })
                else:
                    await broadcast_task_update({
                        "type": "play_count",
                        "count": task_state.today_play_count,
                        "log": f"播放失败: {song_name}",
                        "logType": "error"
                    })
                
                # 等待间隔
                await asyncio.sleep(req.interval)
            
            await broadcast_task_update({
                "type": "play_count",
                "count": task_state.today_play_count,
                "log": f"任务完成! 共播放 {task_state.today_play_count} 首",
                "logType": "success"
            })
            
        except Exception as e:
            logger.error(f"刷歌任务异常: {e}")
            await broadcast_task_update({
                "type": "play_count",
                "count": task_state.today_play_count,
                "log": f"任务异常: {str(e)}",
                "logType": "error"
            })
        finally:
            task_state.play_count_running = False
            await player.close()
            await broadcast_task_update({"type": "task_status", "task": "play_count", "running": False})
    
    task_state.play_count_task = asyncio.create_task(run_play_count_task())
    return {"code": 200, "message": "任务已启动"}


@router.post("/task/play-count/stop")
async def stop_play_count_task():
    """停止刷歌数量任务"""
    task_state.play_count_running = False
    if task_state.play_count_task:
        task_state.play_count_task.cancel()
    return {"code": 200, "message": "任务已停止"}


# ==================== 刷歌时长任务API ====================

class PlayTimeTaskRequest(BaseModel):
    target: int = 60  # 目标时长（分钟）
    songDuration: int = 30  # 单曲播放时长（秒）


@router.post("/task/play-time/start")
async def start_play_time_task(req: PlayTimeTaskRequest):
    """开始刷歌时长任务"""
    if not state.cookies:
        raise HTTPException(status_code=401, detail="请先登录")
    
    if task_state.play_time_running:
        return {"code": 400, "message": "任务已在运行中"}
    
    target_seconds = req.target * 60
    
    async def run_play_time_task():
        task_state.play_time_running = True
        await broadcast_task_update({"type": "task_status", "task": "play_time", "running": True})
        
        player = MusicPlayer(state.cookies)
        try:
            songs = await player.get_songs_from_recommend()
            if not songs:
                await broadcast_task_update({
                    "type": "play_time",
                    "seconds": task_state.today_play_time,
                    "log": "获取歌曲失败",
                    "logType": "error"
                })
                return
            
            await broadcast_task_update({
                "type": "play_time",
                "seconds": task_state.today_play_time,
                "log": f"获取到 {len(songs)} 首歌曲，开始累计时长...",
                "logType": "info"
            })
            
            song_index = 0
            while task_state.play_time_running and task_state.today_play_time < target_seconds:
                song = songs[song_index % len(songs)]
                song_id = song.get("id")
                song_name = song.get("name", "未知")
                
                success = await player.play_song(song_id, source_id="", play_time=req.songDuration)
                
                if success:
                    task_state.today_play_time += req.songDuration
                    minutes = task_state.today_play_time // 60
                    seconds = task_state.today_play_time % 60
                    await broadcast_task_update({
                        "type": "play_time",
                        "seconds": task_state.today_play_time,
                        "log": f"[{minutes}分{seconds}秒/{req.target}分钟] 播放: {song_name}",
                        "logType": "success"
                    })
                else:
                    await broadcast_task_update({
                        "type": "play_time",
                        "seconds": task_state.today_play_time,
                        "log": f"播放失败: {song_name}",
                        "logType": "error"
                    })
                
                song_index += 1
                await asyncio.sleep(1)
            
            minutes = task_state.today_play_time // 60
            await broadcast_task_update({
                "type": "play_time",
                "seconds": task_state.today_play_time,
                "log": f"任务完成! 累计 {minutes} 分钟",
                "logType": "success"
            })
            
        except Exception as e:
            logger.error(f"刷时长任务异常: {e}")
            await broadcast_task_update({
                "type": "play_time",
                "seconds": task_state.today_play_time,
                "log": f"任务异常: {str(e)}",
                "logType": "error"
            })
        finally:
            task_state.play_time_running = False
            await player.close()
            await broadcast_task_update({"type": "task_status", "task": "play_time", "running": False})
    
    task_state.play_time_task = asyncio.create_task(run_play_time_task())
    return {"code": 200, "message": "任务已启动"}


@router.post("/task/play-time/stop")
async def stop_play_time_task():
    """停止刷歌时长任务"""
    task_state.play_time_running = False
    if task_state.play_time_task:
        task_state.play_time_task.cancel()
    return {"code": 200, "message": "任务已停止"}


# ==================== 多用户管理API ====================

@router.get("/users")
async def get_users_list():
    """获取所有已保存的用户列表"""
    users = await get_all_users()
    return {"code": 200, "users": users, "count": len(users)}


@router.post("/users/switch/{user_id}")
async def switch_to_user(user_id: str):
    """切换到指定用户"""
    session = await get_user_session(user_id)
    if not session:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 切换会话
    if await switch_user(user_id):
        state.cookies = session.get("cookies", "")
        state.current_user = session.get("user", {})
        return {"code": 200, "message": "切换成功", "user": state.current_user}
    
    raise HTTPException(status_code=500, detail="切换用户失败")


@router.delete("/users/{user_id}")
async def delete_user(user_id: str):
    """删除指定用户"""
    # 如果删除的是当前用户，清除状态
    current = await get_current_session()
    if current and current.get("user_id") == user_id:
        state.cookies = None
        state.current_user = None
    
    if await remove_user(user_id):
        # 如果还有其他用户，加载下一个
        remaining = await get_all_users()
        if remaining:
            next_user = remaining[0]
            session = await get_user_session(next_user["user_id"])
            if session:
                state.cookies = session.get("cookies", "")
                state.current_user = session.get("user", {})
        
        return {"code": 200, "message": "用户已删除"}
    
    raise HTTPException(status_code=500, detail="删除用户失败")


@router.post("/users/{user_id}/validate")
async def validate_user(user_id: str):
    """验证指定用户的Cookie是否有效"""
    result = await validate_user_session(user_id)
    return {"code": 200 if result.get("valid") else 401, **result}


@router.get("/users/current")
async def get_current_user_info():
    """获取当前用户详细信息（带格式化）"""
    if not state.cookies:
        raise HTTPException(status_code=401, detail="请先登录")
    
    # 获取当前会话中保存的浏览器标头
    current_session = await get_current_session()
    browser_headers = current_session.get("browser_headers") if current_session else None
    
    api = NetEaseAPI(state.cookies, browser_headers=browser_headers)
    try:
        result = await api.get_login_status()
        
        if result.get("code") == 200:
            profile = result.get("profile", {})
            account = result.get("account", {})
            
            # 格式化用户信息
            formatted = {
                "uid": str(profile.get("userId", account.get("id", ""))),
                "nickname": profile.get("nickname", "用户"),
                "avatar_url": profile.get("avatarUrl", ""),
                "signature": profile.get("signature", ""),
                "vip_type": profile.get("vipType", 0),
                "level": account.get("level", 0) if account else 0,
                "location": get_location(profile.get("province", 0), profile.get("city", 0)),
                "province": profile.get("province", 0),
                "city": profile.get("city", 0),
                "birthday": profile.get("birthday", 0),
                "gender": profile.get("gender", 0),  # 0-未知 1-男 2-女
                "create_time": timestamp_to_date(profile.get("createTime", 0)),
                "create_timestamp": profile.get("createTime", 0),
                "listen_songs": profile.get("listenSongs", 0),
                "follows": profile.get("follows", 0),
                "followeds": profile.get("followeds", 0),
                "playlist_count": profile.get("playlistCount", 0),
                "event_count": profile.get("eventCount", 0),
                "raw_profile": profile,
                "raw_account": account
            }
            
            # 更新本地缓存
            state.current_user = {
                "uid": formatted["uid"],
                "nickname": formatted["nickname"],
                "avatar_url": formatted["avatar_url"],
                "signature": formatted["signature"],
                "vip_type": formatted["vip_type"],
                "level": formatted["level"]
            }
            
            return {"code": 200, "data": formatted}
        
        raise HTTPException(status_code=401, detail="获取用户信息失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api.close()


@router.get("/users/current/html-info")
async def get_current_user_html_info():
    """
    从网页HTML解析当前用户详细信息
    通过解析 https://music.163.com/user/home?id=xxx 页面获取更详细的用户信息
    包括等级、累计听歌数、关注/粉丝数等
    """
    if not state.cookies or not state.current_user:
        raise HTTPException(status_code=401, detail="请先登录")
    
    uid = state.current_user.get("uid", "")
    if not uid:
        raise HTTPException(status_code=400, detail="用户ID无效")
    
    # 获取当前会话中保存的浏览器标头
    current_session = await get_current_session()
    browser_headers = current_session.get("browser_headers") if current_session else None
    
    api = NetEaseAPI(state.cookies, browser_headers=browser_headers)
    try:
        html_info = await api.get_user_detail_from_html(uid)
        
        if html_info.get("error"):
            raise HTTPException(status_code=500, detail=html_info.get("error"))
        
        return {
            "code": 200,
            "data": html_info,
            "source": "html",
            "url": f"https://music.163.com/user/home?id={uid}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从HTML解析用户信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api.close()


@router.get("/users/{user_id}/html-info")
async def get_user_html_info_by_id(user_id: str):
    """
    从网页HTML解析指定用户的详细信息
    通过解析 https://music.163.com/user/home?id=xxx 页面获取用户信息
    
    Args:
        user_id: 用户ID
    """
    if not state.cookies:
        raise HTTPException(status_code=401, detail="请先登录")
    
    # 获取当前会话中保存的浏览器标头
    current_session = await get_current_session()
    browser_headers = current_session.get("browser_headers") if current_session else None
    
    api = NetEaseAPI(state.cookies, browser_headers=browser_headers)
    try:
        html_info = await api.get_user_detail_from_html(user_id)
        
        if html_info.get("error"):
            raise HTTPException(status_code=500, detail=html_info.get("error"))
        
        return {
            "code": 200,
            "data": html_info,
            "source": "html",
            "url": f"https://music.163.com/user/home?id={user_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从HTML解析用户信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api.close()


# ==================== 听歌排行API ====================

@router.get("/user/play-record")
async def get_user_play_record(record_type: int = 1):
    """
    获取用户听歌排行
    
    Args:
        record_type: 0-所有时间 1-最近一周
    """
    if not state.cookies or not state.current_user:
        raise HTTPException(status_code=401, detail="请先登录")
    
    uid = state.current_user.get("uid", "")
    if not uid:
        raise HTTPException(status_code=400, detail="用户ID不存在")
    
    # 优先返回缓存数据，同时在后台检查并同步更新
    current_session = await get_current_session()
    browser_headers = current_session.get("browser_headers") if current_session else None

    try:
        sync_result = await check_and_sync_data(uid, state.cookies, browser_headers, force=False)

        # 从返回值中选择排行数据
        data_key = "week_rankings" if record_type == 1 else "all_rankings"
        rankings = sync_result.get(data_key, [])

        # 格式化返回
        formatted_records = []
        for idx, r in enumerate(rankings[:100], 1):
            formatted_records.append({
                "rank": r.get("rank_position", idx),
                "play_count": r.get("play_count", 0),
                "score": r.get("score", 0),
                "song": {
                    "id": r.get("song_id"),
                    "name": r.get("song_name"),
                    "duration": None,
                    "artists": [{"name": n.strip()} for n in (r.get("artist_names", "") or "").split(",") if n.strip()],
                    "album": {
                        "name": r.get("album_name"),
                        "pic_url": r.get("album_cover_url")
                    }
                }
            })

        return {
            "code": 200,
            "type": "week" if record_type == 1 else "all",
            "count": len(formatted_records),
            "records": formatted_records,
            "from_cache": sync_result.get("from_cache", False)
        }
    except Exception as e:
        logger.error(f"获取听歌排行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 用户歌单API ====================

@router.get("/user/playlists")
async def get_user_playlists_api(limit: int = 30, offset: int = 0):
    """获取当前用户的歌单列表"""
    if not state.cookies or not state.current_user:
        raise HTTPException(status_code=401, detail="请先登录")
    
    uid = state.current_user.get("uid", "")
    if not uid:
        raise HTTPException(status_code=400, detail="用户ID不存在")
    
    # 优先返回缓存歌单，同时在后台检查更新
    current_session = await get_current_session()
    browser_headers = current_session.get("browser_headers") if current_session else None

    try:
        sync_result = await check_and_sync_data(uid, state.cookies, browser_headers, force=False)

        playlists = sync_result.get("playlists", [])

        # 支持分页返回（简单切片）
        start = offset
        end = offset + limit
        page = playlists[start:end]

        # 将数据库字段格式化为旧接口期望的结构
        formatted_playlists = []
        for pl in page:
            formatted_playlists.append({
                "id": pl.get("playlist_id") or pl.get("id"),
                "name": pl.get("name", ""),
                "cover_url": pl.get("cover_url", ""),
                "track_count": pl.get("track_count", 0),
                "play_count": format_play_count(pl.get("play_count", 0)),
                "play_count_raw": pl.get("play_count", 0),
                "subscribed_count": pl.get("subscribed_count", 0),
                "description": pl.get("description", ""),
                "create_time": timestamp_to_date(pl.get("create_time", 0)),
                "update_time": timestamp_to_date(pl.get("update_time", 0)),
                "is_subscribed": pl.get("is_subscribed", False),
                "creator": {
                    "id": pl.get("creator_uid"),
                    "nickname": pl.get("creator_nickname", ""),
                    "avatar_url": None
                },
                "is_mine": str(pl.get("creator_uid")) == uid
            })

        return {
            "code": 200,
            "total": len(playlists),
            "playlists": formatted_playlists,
            "from_cache": sync_result.get("from_cache", False)
        }
    except Exception as e:
        logger.error(f"获取用户歌单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Cookie有效性检查API ====================

@router.get("/auth/validate")
async def validate_current_cookie():
    """验证当前Cookie是否有效"""
    if not state.cookies:
        return {"code": 401, "valid": False, "message": "未登录"}
    
    api = NetEaseAPI(state.cookies)
    try:
        result = await api.check_cookie_valid()
        return result
    except Exception as e:
        logger.error(f"验证Cookie失败: {e}")
        return {"code": 500, "valid": False, "message": str(e)}
    finally:
        await api.close()
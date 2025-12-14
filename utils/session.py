"""
多用户会话管理 - 使用数据库存储多个用户的登录状态
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import select, update, delete
from utils.database import get_session
from utils.models import User
from utils.logger import logger


async def save_user_session(
    user_id: str, 
    cookies: str, 
    user_info: Dict[str, Any] = None,
    browser_headers: Dict[str, str] = None,
    set_current: bool = False
) -> bool:
    """
    保存用户会话信息
    
    Args:
        user_id: 用户ID
        cookies: Cookie字符串
        user_info: 用户信息字典
        browser_headers: 浏览器标头
        set_current: 是否设置为当前用户（默认False，需要用户手动选择）
    
    Returns:
        是否保存成功
    """
    try:
        async with get_session() as session:
            # 如果需要设置为当前用户，先将所有用户的 is_current 设为 False
            if set_current:
                await session.execute(
                    update(User).values(is_current=False)
                )
            
            # 检查用户是否已存在
            result = await session.execute(
                select(User).where(User.uid == user_id)
            )
            existing_user = result.scalar_one_or_none()
            
            user_data = user_info or {}
            
            if existing_user:
                # 更新现有用户
                existing_user.cookies = cookies
                existing_user.nickname = user_data.get("nickname", existing_user.nickname)
                existing_user.avatar_url = user_data.get("avatar_url", existing_user.avatar_url)
                existing_user.signature = user_data.get("signature", existing_user.signature or "")
                existing_user.vip_type = user_data.get("vip_type", existing_user.vip_type or 0)
                existing_user.level = user_data.get("level", existing_user.level or 0)
                existing_user.province = user_data.get("province", existing_user.province or 0)
                existing_user.city = user_data.get("city", existing_user.city or 0)
                existing_user.listen_songs = user_data.get("listen_songs", existing_user.listen_songs or 0)
                existing_user.browser_headers = browser_headers or existing_user.browser_headers
                existing_user.is_active = True
                if set_current:
                    existing_user.is_current = True
                existing_user.last_login = datetime.now()
            else:
                # 创建新用户
                new_user = User(
                    uid=user_id,
                    nickname=user_data.get("nickname", "用户"),
                    avatar_url=user_data.get("avatar_url", ""),
                    signature=user_data.get("signature", ""),
                    vip_type=user_data.get("vip_type", 0),
                    level=user_data.get("level", 0),
                    province=user_data.get("province", 0),
                    city=user_data.get("city", 0),
                    listen_songs=user_data.get("listen_songs", 0),
                    cookies=cookies,
                    browser_headers=browser_headers,
                    is_active=True,
                    is_current=set_current,
                    last_login=datetime.now()
                )
                session.add(new_user)
            
            await session.commit()
            logger.info(f"✅ 用户 {user_id} 会话已保存到数据库")
            return True
    except Exception as e:
        logger.error(f"保存用户会话失败: {e}")
        return False


async def get_user_session(user_id: str) -> Optional[Dict[str, Any]]:
    """
    获取指定用户的会话信息
    
    Args:
        user_id: 用户ID
    
    Returns:
        用户会话信息，包含 cookies, user, browser_headers 等
    """
    try:
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.uid == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                return {
                    "cookies": user.cookies,
                    "browser_headers": user.browser_headers,
                    "user": {
                        "uid": user.uid,
                        "nickname": user.nickname,
                        "avatar_url": user.avatar_url,
                        "signature": user.signature,
                        "vip_type": user.vip_type,
                        "level": user.level,
                        "province": user.province,
                        "city": user.city,
                        "listen_songs": user.listen_songs
                    },
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "active": user.is_active
                }
            return None
    except Exception as e:
        logger.error(f"获取用户会话失败: {e}")
        return None


async def get_current_session() -> Optional[Dict[str, Any]]:
    """
    获取当前用户的会话信息
    
    Returns:
        当前用户会话信息
    """
    try:
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.is_current == True)
            )
            user = result.scalar_one_or_none()
            
            if user:
                return {
                    "user_id": user.uid,
                    "cookies": user.cookies,
                    "browser_headers": user.browser_headers,
                    "user": {
                        "uid": user.uid,
                        "nickname": user.nickname,
                        "avatar_url": user.avatar_url,
                        "signature": user.signature,
                        "vip_type": user.vip_type,
                        "level": user.level,
                        "province": user.province,
                        "city": user.city,
                        "listen_songs": user.listen_songs
                    },
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "active": user.is_active
                }
            return None
    except Exception as e:
        logger.error(f"获取当前会话失败: {e}")
        return None


async def get_all_users() -> List[Dict[str, Any]]:
    """
    获取所有已保存的用户列表
    
    Returns:
        用户列表
    """
    try:
        async with get_session() as session:
            result = await session.execute(
                select(User).order_by(User.last_login.desc())
            )
            users = result.scalars().all()
            
            return [
                {
                    "user_id": user.uid,
                    "nickname": user.nickname,
                    "avatar_url": user.avatar_url,
                    "last_login": user.last_login.isoformat() if user.last_login else "",
                    "active": user.is_active,
                    "is_current": user.is_current
                }
                for user in users
            ]
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        return []


async def switch_user(user_id: str) -> bool:
    """
    切换当前用户
    
    Args:
        user_id: 要切换到的用户ID
    
    Returns:
        是否切换成功
    """
    try:
        async with get_session() as session:
            # 检查用户是否存在
            result = await session.execute(
                select(User).where(User.uid == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"用户 {user_id} 不存在")
                return False
            
            # 将所有用户的 is_current 设为 False
            await session.execute(
                update(User).values(is_current=False)
            )
            
            # 设置目标用户为当前用户
            user.is_current = True
            user.last_login = datetime.now()
            
            await session.commit()
            logger.info(f"✅ 已切换到用户 {user_id}")
            return True
    except Exception as e:
        logger.error(f"切换用户失败: {e}")
        return False


async def remove_user(user_id: str) -> bool:
    """
    移除用户会话
    
    Args:
        user_id: 要移除的用户ID
    
    Returns:
        是否移除成功
    """
    try:
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.uid == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return True  # 不存在也算成功
            
            was_current = user.is_current
            
            # 删除用户
            await session.execute(
                delete(User).where(User.uid == user_id)
            )
            
            # 如果删除的是当前用户，切换到其他用户
            if was_current:
                result = await session.execute(
                    select(User).order_by(User.last_login.desc()).limit(1)
                )
                next_user = result.scalar_one_or_none()
                if next_user:
                    next_user.is_current = True
            
            await session.commit()
            logger.info(f"✅ 用户 {user_id} 已移除")
            return True
    except Exception as e:
        logger.error(f"移除用户失败: {e}")
        return False


async def clear_all_sessions() -> bool:
    """
    清除所有会话信息
    
    Returns:
        是否清除成功
    """
    try:
        async with get_session() as session:
            await session.execute(delete(User))
            await session.commit()
            logger.info("✅ 所有会话信息已清除")
        return True
    except Exception as e:
        logger.error(f"清除会话失败: {e}")
        return False


async def update_user_info(user_id: str, user_info: Dict[str, Any]) -> bool:
    """
    更新用户信息（不更新Cookie）
    
    Args:
        user_id: 用户ID
        user_info: 新的用户信息
    
    Returns:
        是否更新成功
    """
    try:
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.uid == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            user.nickname = user_info.get("nickname", user.nickname)
            user.avatar_url = user_info.get("avatar_url", user.avatar_url)
            user.signature = user_info.get("signature", user.signature)
            user.vip_type = user_info.get("vip_type", user.vip_type)
            user.level = user_info.get("level", user.level)
            user.province = user_info.get("province", user.province)
            user.city = user_info.get("city", user.city)
            user.listen_songs = user_info.get("listen_songs", user.listen_songs)
            
            await session.commit()
            return True
    except Exception as e:
        logger.error(f"更新用户信息失败: {e}")
        return False


async def update_user_browser_headers(user_id: str, browser_headers: Dict[str, str]) -> bool:
    """
    更新用户的浏览器标头
    
    Args:
        user_id: 用户ID
        browser_headers: 浏览器标头字典
    
    Returns:
        是否更新成功
    """
    try:
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.uid == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            user.browser_headers = browser_headers
            await session.commit()
            logger.info(f"✅ 用户 {user_id} 浏览器标头已更新")
            return True
    except Exception as e:
        logger.error(f"更新浏览器标头失败: {e}")
        return False


async def get_user_browser_headers(user_id: str) -> Optional[Dict[str, str]]:
    """
    获取用户的浏览器标头
    
    Args:
        user_id: 用户ID
    
    Returns:
        浏览器标头字典
    """
    try:
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.uid == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user and user.browser_headers:
                return user.browser_headers
            return None
    except Exception as e:
        logger.error(f"获取浏览器标头失败: {e}")
        return None


async def validate_user_session(user_id: str) -> Dict[str, Any]:
    """
    验证用户的Cookie是否有效
    
    Args:
        user_id: 用户ID
    
    Returns:
        {"valid": True/False, "user": 用户信息或None}
    """
    from core.api import NetEaseAPI
    
    session_data = await get_user_session(user_id)
    if not session_data:
        return {"valid": False, "message": "用户不存在"}
    
    cookies = session_data.get("cookies", "")
    if not cookies:
        return {"valid": False, "message": "Cookie为空"}
    
    browser_headers = session_data.get("browser_headers")
    api = NetEaseAPI(cookies, browser_headers=browser_headers)
    
    try:
        result = await api.check_cookie_valid()
        
        if result.get("valid"):
            # Cookie有效，尝试获取最新用户信息
            user_result = await api.get_login_status()
            if user_result.get("profile"):
                profile = user_result["profile"]
                user_info = {
                    "uid": str(profile.get("userId", "")),
                    "nickname": profile.get("nickname", "用户"),
                    "avatar_url": profile.get("avatarUrl", ""),
                    "signature": profile.get("signature", ""),
                    "vip_type": profile.get("vipType", 0),
                    "level": profile.get("level", 0),
                    "province": profile.get("province", 0),
                    "city": profile.get("city", 0),
                    "listen_songs": profile.get("listenSongs", 0)
                }
                # 更新用户信息
                await update_user_info(user_id, user_info)
                return {"valid": True, "user": user_info}
            
            return {"valid": True, "user": session_data.get("user")}
        else:
            # Cookie无效，标记为不活跃
            async with get_session() as db_session:
                db_result = await db_session.execute(
                    select(User).where(User.uid == user_id)
                )
                user = db_result.scalar_one_or_none()
                if user:
                    user.is_active = False
                    await db_session.commit()
            
            return {"valid": False, "message": result.get("message", "Cookie已失效")}
    except Exception as e:
        logger.error(f"验证会话失败: {e}")
        return {"valid": False, "message": str(e)}
    finally:
        await api.close()


async def validate_session(cookies: str) -> Optional[Dict[str, Any]]:
    """验证Cookie并返回用户信息"""
    from core.api import NetEaseAPI
    
    if not cookies:
        return None
    
    api = NetEaseAPI(cookies)
    try:
        result = await api.get_login_status()
        
        if result.get("code") == 200:
            profile = result.get("profile")
            account = result.get("account")
            
            if profile:
                return {
                    "uid": str(profile.get("userId", "")),
                    "nickname": profile.get("nickname", "用户"),
                    "avatar_url": profile.get("avatarUrl", ""),
                    "vip_type": profile.get("vipType", 0),
                    "level": profile.get("level", 0),
                    "signature": profile.get("signature", ""),
                    "province": profile.get("province", 0),
                    "city": profile.get("city", 0),
                    "listen_songs": profile.get("listenSongs", 0)
                }
            elif account:
                return {
                    "uid": str(account.get("id", "")),
                    "nickname": "用户",
                    "avatar_url": "",
                    "vip_type": 0,
                    "level": 0
                }
        
        return None
    except Exception as e:
        logger.error(f"验证会话失败: {e}")
        return None
    finally:
        await api.close()

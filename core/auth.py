"""
认证模块 - 二维码登录
"""
import asyncio
import qrcode
import io
import base64
from typing import Optional, Dict, Any, Callable
from core.api import NetEaseAPI
from utils.logger import logger


class QRCodeLogin:
    """二维码登录管理器"""
    
    # 扫码状态码
    STATUS_WAITING = 801      # 等待扫码
    STATUS_SCANNED = 802      # 已扫码待确认
    STATUS_SUCCESS = 803      # 登录成功
    STATUS_EXPIRED = 800      # 二维码过期
    
    def __init__(self):
        self.api = NetEaseAPI()
        self.qr_key: Optional[str] = None
        self.status: int = 0
        self.cookies: Optional[str] = None
        self._check_task: Optional[asyncio.Task] = None
    
    async def generate_qr(self) -> Dict[str, Any]:
        """
        生成登录二维码
        
        Returns:
            {
                "success": bool,
                "qr_key": str,
                "qr_url": str,
                "qr_image": str  # base64编码的图片
            }
        """
        try:
            # 获取二维码key
            result = await self.api.get_qr_key()
            if result.get("code") != 200:
                return {"success": False, "message": "获取二维码Key失败"}
            
            self.qr_key = result.get("unikey")
            
            # 生成二维码URL
            qr_url = f"https://music.163.com/login?codekey={self.qr_key}"
            
            # 生成二维码图片
            qr_image = self._create_qr_image(qr_url)
            
            self.status = self.STATUS_WAITING
            
            return {
                "success": True,
                "qr_key": self.qr_key,
                "qr_url": qr_url,
                "qr_image": qr_image
            }
        except Exception as e:
            logger.error(f"生成二维码失败: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def _create_qr_image(self, data: str) -> str:
        """生成二维码图片并返回base64"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # 转为base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_base64}"
    
    async def check_status(self) -> Dict[str, Any]:
        """
        检查扫码状态
        
        Returns:
            {
                "code": int,       # 状态码
                "status": str,     # 状态描述
                "cookies": str     # 登录成功时的cookies
            }
        """
        if not self.qr_key:
            return {"code": -1, "status": "请先生成二维码"}
        
        try:
            result = await self.api.check_qr(self.qr_key)
            code = result.get("code", 0)
            self.status = code
            
            status_map = {
                800: "二维码已过期，请重新生成",
                801: "等待扫码",
                802: "扫码成功，请在手机上确认",
                803: "登录成功",
                8821: "环境异常，请稍后重试或使用Cookie登录"
            }
            
            response = {
                "code": code,
                "status": status_map.get(code, f"未知状态({code})")
            }
            
            # 如果触发风控，记录详细信息
            if code == 8821:
                logger.warning(f"触发网易云风控: {result.get('message', '')}")
                response["message"] = result.get("message", "环境异常")
            
            if code == 803:
                self.cookies = result.get("cookies", "")
                response["cookies"] = self.cookies
            
            return response
        except Exception as e:
            logger.error(f"检查扫码状态失败: {str(e)}")
            return {"code": -1, "status": str(e)}
    
    async def wait_for_login(
        self,
        timeout: int = 120,
        callback: Callable[[Dict], None] = None
    ) -> Dict[str, Any]:
        """
        等待登录完成
        
        Args:
            timeout: 超时时间(秒)
            callback: 状态变化回调函数
        """
        start_time = asyncio.get_event_loop().time()
        last_status = 0
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                return {"success": False, "message": "登录超时"}
            
            result = await self.check_status()
            code = result.get("code")
            
            # 状态变化时回调
            if callback and code != last_status:
                callback(result)
                last_status = code
            
            if code == 803:
                return {
                    "success": True,
                    "cookies": result.get("cookies")
                }
            elif code == 800:
                return {"success": False, "message": "二维码已过期"}
            
            await asyncio.sleep(2)
    
    async def close(self):
        """关闭资源"""
        await self.api.close()


class AuthManager:
    """认证管理器"""
    
    @staticmethod
    async def login_with_password(phone: str, password: str, country_code: str = "86") -> Dict[str, Any]:
        """
        手机号密码登录
        
        Args:
            phone: 手机号
            password: 密码
            country_code: 国家码
            
        Returns:
            {
                "success": bool,
                "cookies": str,
                "user": {...},
                "browser_headers": {...}
            }
        """
        api = NetEaseAPI()
        try:
            result = await api.login_cellphone(phone, password, country_code)
            
            if result.get("code") == 200:
                cookies = result.get("cookies", "")
                parsed_cookies = AuthManager.parse_cookies(cookies)
                
                # 提取用户信息
                profile = result.get("profile", {})
                user = {
                    "uid": str(profile.get("userId", "")),
                    "nickname": profile.get("nickname", ""),
                    "avatar_url": profile.get("avatarUrl", ""),
                    "signature": profile.get("signature", ""),
                    "vip_type": profile.get("vipType", 0),
                    "level": profile.get("level", 0),
                    "province": profile.get("province", 0),
                    "city": profile.get("city", 0),
                    "listen_songs": profile.get("listenSongs", 0)
                }
                
                # 获取当前使用的浏览器标头
                browser_headers = api.get_current_headers()
                
                return {
                    "success": True,
                    "cookies": parsed_cookies,
                    "user": user,
                    "browser_headers": browser_headers
                }
            else:
                # 处理错误码
                error_messages = {
                    400: "手机号格式错误",
                    501: "账号不存在",
                    502: "密码错误",
                    503: "验证码错误",
                    509: "请求过于频繁，请稍后再试",
                    -462: "需要进行人机验证"
                }
                code = result.get("code", -1)
                message = error_messages.get(code, result.get("message", "登录失败"))
                return {"success": False, "message": message, "code": code}
        except Exception as e:
            logger.error(f"密码登录异常: {str(e)}")
            return {"success": False, "message": str(e)}
        finally:
            await api.close()
    
    @staticmethod
    async def validate_cookies(cookies: str) -> Dict[str, Any]:
        """验证Cookie是否有效"""
        api = NetEaseAPI(cookies)
        try:
            result = await api.get_login_status()
            if result.get("profile"):
                return {
                    "valid": True,
                    "user": {
                        "uid": str(result["profile"]["userId"]),
                        "nickname": result["profile"]["nickname"],
                        "avatar_url": result["profile"]["avatarUrl"]
                    }
                }
            return {"valid": False, "message": "Cookie已失效"}
        except Exception as e:
            return {"valid": False, "message": str(e)}
        finally:
            await api.close()
    
    @staticmethod
    def parse_cookies(set_cookie_header: str) -> str:
        """解析Set-Cookie头为Cookie字符串"""
        if not set_cookie_header:
            return ""
        
        cookies = []
        # Set-Cookie头可能有多个，用换行或逗号+空格分隔
        # 但Cookie值中也可能包含逗号（如日期），所以需要更智能的解析
        
        # 查找关键Cookie
        import re
        
        # 匹配 key=value 对，直到遇到分号
        # 关键Cookie: MUSIC_U, __csrf, __remember_me 等
        key_cookies = ['MUSIC_U', '__csrf', '__remember_me', 'NMTID', 'JSESSIONID-WYYY']
        
        for key in key_cookies:
            # 匹配 key=value; 或 key=value（末尾）
            pattern = rf'{key}=([^;]+)'
            match = re.search(pattern, set_cookie_header)
            if match:
                cookies.append(f"{key}={match.group(1)}")
        
        # 如果没找到关键Cookie，尝试简单解析
        if not cookies:
            # 按分号分割，取每个部分的第一个key=value
            for part in set_cookie_header.split(';'):
                part = part.strip()
                if '=' in part and not any(x in part.lower() for x in ['path', 'domain', 'expires', 'max-age', 'httponly', 'secure', 'samesite']):
                    cookies.append(part)
        
        result = "; ".join(cookies)
        logger.debug(f"解析Cookie结果: {result[:100] if result else 'None'}...")
        return result

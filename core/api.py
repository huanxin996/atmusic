"""
网易云音乐API封装模块
"""
import httpx
import json
import time
import random
from typing import Optional, Dict, Any, List
from utils.crypto import encrypt_request, encrypt_eapi
from utils.logger import logger

try:
    import brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False
    logger.warning("brotli库未安装，某些API响应可能无法正确解码")


class NetEaseAPI:
    """网易云音乐API"""
    
    BASE_URL = "https://music.163.com"
    # 使用更真实的浏览器UA
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    
    def __init__(self, cookies: str = None, browser_headers: Dict[str, str] = None):
        self.cookies = cookies or ""
        self.browser_headers = browser_headers  # 存储用户的浏览器标头
        # 生成设备ID
        self._device_id = self._generate_device_id()
        self.client = httpx.AsyncClient(
            timeout=30,
            headers=self._get_headers(),
            follow_redirects=True,
        )
    
    def _generate_device_id(self) -> str:
        """生成设备ID"""
        import uuid
        return str(uuid.uuid4()).replace("-", "")[:32]
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头 - 如果有保存的浏览器标头则使用，否则使用默认"""
        if self.browser_headers:
            # 使用保存的浏览器标头，但确保必要的字段存在
            headers = dict(self.browser_headers)
            # 确保有必要的默认值
            if "User-Agent" not in headers:
                headers["User-Agent"] = self.USER_AGENT
            if "Referer" not in headers:
                headers["Referer"] = f"{self.BASE_URL}/"
            if "Origin" not in headers:
                headers["Origin"] = self.BASE_URL
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            return headers
        
        return {
            "User-Agent": self.USER_AGENT,
            "Referer": f"{self.BASE_URL}/",
            "Origin": self.BASE_URL,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
    
    def get_current_headers(self) -> Dict[str, str]:
        """获取当前使用的请求头，用于保存"""
        return self._get_headers()
    
    def set_cookies(self, cookies: str):
        """设置Cookie"""
        self.cookies = cookies
    
    async def _request(
        self,
        method: str,
        url: str,
        data: Dict = None,
        encrypt: bool = True
    ) -> Dict[str, Any]:
        """发送请求"""
        headers = self._get_headers()
        
        # 构建Cookie，包含设备信息
        base_cookie = f"os=pc; osver=Microsoft-Windows-10-Professional-build-19045-64bit; appver=2.10.16.200601; deviceId={self._device_id}; NMTID={self._device_id[:24]}"
        if self.cookies:
            headers["Cookie"] = f"{base_cookie}; {self.cookies}"
        else:
            headers["Cookie"] = base_cookie
        
        if encrypt and data:
            data = encrypt_request(data)
        
        try:
            if method.upper() == "GET":
                response = await self.client.get(url, headers=headers)
            else:
                response = await self.client.post(url, data=data, headers=headers)
            
            # 检查响应是否为空
            if not response.content:
                logger.warning(f"响应内容为空: {url}")
                return {"code": -1, "message": "响应内容为空"}
            
            # 处理Brotli压缩
            content_encoding = response.headers.get('content-encoding', '')
            if content_encoding == 'br' and HAS_BROTLI:
                try:
                    decompressed = brotli.decompress(response.content)
                    return json.loads(decompressed.decode('utf-8'))
                except Exception as e:
                    logger.warning(f"Brotli解压失败，尝试其他方式: {e}")
            
            # 处理响应编码问题
            try:
                return response.json()
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.warning(f"JSON解析失败: {e}")
                # 如果UTF-8解码失败，尝试其他编码
                try:
                    content = response.content.decode('utf-8', errors='ignore')
                    if content.strip():
                        return json.loads(content)
                except json.JSONDecodeError:
                    pass
                
                # 记录更多调试信息
                logger.error(f"响应内容不是有效JSON")
                logger.error(f"响应状态码: {response.status_code}")
                logger.error(f"Content-Encoding: {content_encoding}")
                logger.error(f"原始字节内容前100字节: {response.content[:100]}")
                return {"code": -1, "message": "响应格式错误"}
        except Exception as e:
            logger.error(f"请求失败: {url}, 错误: {str(e)}")
            return {"code": -1, "message": str(e)}
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
    
    # ==================== 登录相关 ====================
    
    async def get_qr_key(self) -> Dict[str, Any]:
        """获取二维码key"""
        url = f"{self.BASE_URL}/weapi/login/qrcode/unikey"
        data = {"type": 1}
        return await self._request("POST", url, data)
    
    async def create_qr(self, key: str) -> Dict[str, Any]:
        """生成二维码"""
        url = f"{self.BASE_URL}/weapi/login/qrcode/create"
        data = {"key": key, "type": 1}
        return await self._request("POST", url, data)
    
    async def check_qr(self, key: str) -> Dict[str, Any]:
        """检查二维码扫描状态"""
        url = f"{self.BASE_URL}/weapi/login/qrcode/client/login"
        data = {"key": key, "type": 1}
        
        headers = self._get_headers()
        # 添加设备信息Cookie
        headers["Cookie"] = f"os=pc; osver=Microsoft-Windows-10-Professional-build-19045-64bit; appver=2.10.16.200601; deviceId={self._device_id}; NMTID={self._device_id[:24]}"
        
        encrypted = encrypt_request(data)
        
        response = await self.client.post(url, data=encrypted, headers=headers)
        
        # 调试日志
        logger.debug(f"check_qr响应状态码: {response.status_code}")
        logger.debug(f"check_qr响应头: {dict(response.headers)}")
        
        # 处理响应
        result = None
        try:
            result = response.json()
            logger.debug(f"check_qr JSON解析成功: {result}")
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            logger.warning(f"JSON解析失败，尝试其他编码: {e}")
            try:
                content = response.content.decode('gbk')
                result = json.loads(content)
            except (UnicodeDecodeError, json.JSONDecodeError):
                try:
                    content = response.content.decode('utf-8', errors='ignore')
                    result = json.loads(content)
                except json.JSONDecodeError:
                    # 尝试手动解压brotli
                    if HAS_BROTLI and response.headers.get('content-encoding') == 'br':
                        try:
                            decompressed = brotli.decompress(response.content)
                            content = decompressed.decode('utf-8')
                            result = json.loads(content)
                        except Exception as e:
                            logger.error(f"Brotli解压失败: {str(e)}")
                    
                    if result is None:
                        logger.error(f"二维码检查响应格式错误")
                        logger.error(f"响应状态码: {response.status_code}")
                        logger.error(f"原始字节内容前100字节: {response.content[:100]}")
                        return {"code": -1, "message": "响应格式错误"}
        
        if result is None:
            return {"code": -1, "message": "响应解析失败"}
        
        # 提取cookie
        if result.get("code") == 803:
            cookies = response.headers.get("set-cookie", "")
            result["cookies"] = cookies
            logger.info(f"登录成功，获取到cookies: {cookies[:50] if cookies else 'None'}...")
        
        return result
    
    async def login_cellphone(self, phone: str, password: str, country_code: str = "86") -> Dict[str, Any]:
        """
        手机号密码登录
        
        Args:
            phone: 手机号
            password: 密码（明文，会自动MD5加密）
            country_code: 国家码，默认86（中国）
        """
        from utils.crypto import md5_encrypt
        
        url = f"{self.BASE_URL}/weapi/login/cellphone"
        
        # 构建更完整的登录参数
        md5_password = md5_encrypt(password)
        data = {
            "phone": phone,
            "countrycode": country_code,
            "password": md5_password,
            "rememberLogin": "true",
            "checkToken": "",
            "e": "",
        }
        
        # 构建更真实的请求头
        headers = self._get_headers()
        headers["Cookie"] = f"os=pc; osver=Microsoft-Windows-10-Professional-build-19045-64bit; appver=2.10.16.200601; deviceId={self._device_id}; NMTID={self._device_id[:24]}"
        
        from utils.crypto import encrypt_request
        encrypted = encrypt_request(data)
        
        # 添加随机延迟，模拟真实用户
        import asyncio
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        response = await self.client.post(url, data=encrypted, headers=headers)
        
        # 处理响应
        result = None
        try:
            result = response.json()
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            logger.warning(f"密码登录JSON解析失败: {e}")
            try:
                content = response.content.decode('utf-8', errors='ignore')
                result = json.loads(content)
            except json.JSONDecodeError:
                logger.error(f"密码登录响应格式错误")
                return {"code": -1, "message": "响应格式错误"}
        
        if result is None:
            return {"code": -1, "message": "响应解析失败"}
        
        # 登录成功，提取cookie
        if result.get("code") == 200:
            cookies = response.headers.get("set-cookie", "")
            result["cookies"] = cookies
            logger.info(f"密码登录成功: {phone}")
        else:
            logger.warning(f"密码登录失败: {result.get('message', '未知错误')}")
        
        return result
    
    async def get_login_status(self) -> Dict[str, Any]:
        """获取登录状态 - 使用更可靠的API"""
        import re
        
        # 从Cookie中提取csrf_token
        csrf_token = ""
        if self.cookies:
            csrf_match = re.search(r'__csrf[=:]([a-zA-Z0-9]+)', self.cookies)
            if csrf_match:
                csrf_token = csrf_match.group(1)
                logger.debug(f"提取到csrf_token: {csrf_token}")
        
        # 尝试多个API端点
        endpoints = [
            f"{self.BASE_URL}/weapi/w/nuser/account/get",
            f"{self.BASE_URL}/weapi/nuser/account/get",
        ]
        
        for url in endpoints:
            # 在URL中添加csrf_token
            request_url = f"{url}?csrf_token={csrf_token}" if csrf_token else url
            result = await self._request("POST", request_url, {"csrf_token": csrf_token})
            
            logger.debug(f"用户信息API响应: {result}")
            
            if result.get("code") == 200:
                # 成功获取到账户信息
                return result
            
            # 检查是否有profile字段
            if result.get("profile"):
                return result
                
            logger.debug(f"尝试API {url} 失败: {result}")
        
        # 如果都失败，尝试从Cookie中解析用户ID并获取用户详情
        if self.cookies:
            uid_match = re.search(r'MUSIC_U=([a-zA-Z0-9]+)', self.cookies)
            if uid_match:
                logger.debug(f"Cookie中存在MUSIC_U，尝试验证登录状态")
                # 返回一个基本的成功响应，表明Cookie可能有效
                return {"code": 200, "account": {"status": 0}, "profile": None}
        
        return {"code": -1, "message": "获取登录状态失败"}
    
    async def get_account_info(self) -> Dict[str, Any]:
        """获取账户信息（备用接口）"""
        url = f"{self.BASE_URL}/weapi/user/account"
        return await self._request("POST", url, {})
    
    async def get_user_detail(self, uid: str) -> Dict[str, Any]:
        """获取用户详情"""
        url = f"{self.BASE_URL}/weapi/v1/user/detail/{uid}"
        return await self._request("POST", url, {})
    
    # ==================== 歌曲相关 ====================
    
    async def get_recommend_songs(self) -> Dict[str, Any]:
        """获取每日推荐歌曲"""
        url = f"{self.BASE_URL}/weapi/v3/discovery/recommend/songs"
        return await self._request("POST", url, {})
    
    async def get_playlist_detail(self, playlist_id: str) -> Dict[str, Any]:
        """获取歌单详情"""
        url = f"{self.BASE_URL}/weapi/v6/playlist/detail"
        data = {"id": playlist_id, "n": 100000}
        return await self._request("POST", url, data)
    
    async def get_song_url(self, song_ids: List[str], level: str = "standard") -> Dict[str, Any]:
        """获取歌曲播放地址"""
        url = f"{self.BASE_URL}/weapi/song/enhance/player/url/v1"
        data = {
            "ids": song_ids,
            "level": level,
            "encodeType": "flac"
        }
        return await self._request("POST", url, data)
    
    async def scrobble(self, song_id: str, source_id: str = "", time: int = 240) -> Dict[str, Any]:
        """
        上报听歌记录(刷歌核心接口)
        
        Args:
            song_id: 歌曲ID
            source_id: 来源ID(歌单ID等)
            time: 听歌时长(秒)
        """
        url = f"{self.BASE_URL}/weapi/feedback/weblog"
        data = {
            "logs": json.dumps([{
                "action": "play",
                "json": {
                    "download": 0,
                    "end": "playend",
                    "id": int(song_id),
                    "sourceId": source_id,
                    "time": time,
                    "type": "song",
                    "wifi": 0
                }
            }])
        }
        return await self._request("POST", url, data)
    
    # ==================== 用户相关 ====================
    
    async def get_user_playlist(self, uid: str, limit: int = 30, offset: int = 0) -> Dict[str, Any]:
        """获取用户歌单"""
        url = f"{self.BASE_URL}/weapi/user/playlist"
        data = {
            "uid": uid,
            "limit": limit,
            "offset": offset
        }
        return await self._request("POST", url, data)
    
    async def get_user_record(self, uid: str, record_type: int = 1) -> Dict[str, Any]:
        """
        获取用户听歌排行
        
        Args:
            uid: 用户ID
            record_type: 0-所有时间 1-最近一周
        """
        url = f"{self.BASE_URL}/weapi/v1/play/record"
        data = {
            "uid": uid,
            "type": record_type
        }
        return await self._request("POST", url, data)
    
    async def get_today_play_count(self) -> int:
        """获取今日播放数(通过用户主页获取)"""
        try:
            status = await self.get_login_status()
            if status.get("profile"):
                # 尝试从个人资料获取今日听歌数
                return status.get("profile", {}).get("playCount", 0)
        except:
            pass
        return 0
    
    async def check_cookie_valid(self) -> Dict[str, Any]:
        """
        检查Cookie是否有效
        
        通过音乐人接口验证Cookie有效性
        返回: {"code": 200, "valid": True/False, "message": "..."}
        """
        import re
        
        # 从Cookie中提取csrf_token
        csrf_token = ""
        if self.cookies:
            csrf_match = re.search(r'__csrf[=:]([a-zA-Z0-9]+)', self.cookies)
            if csrf_match:
                csrf_token = csrf_match.group(1)
        
        url = f"{self.BASE_URL}/weapi/nmusician/userinfo/get"
        request_url = f"{url}?csrf_token={csrf_token}" if csrf_token else url
        
        result = await self._request("POST", request_url, {"csrf_token": csrf_token})
        
        logger.debug(f"Cookie有效性检查响应: {result}")
        
        if result.get("code") == 200:
            # code为200表示请求成功
            user_status = result.get("data", {}).get("userStatus", -1)
            return {
                "code": 200,
                "valid": True,
                "userStatus": user_status,
                "message": "Cookie有效"
            }
        elif result.get("code") == 301:
            # 未登录
            return {
                "code": 301,
                "valid": False,
                "message": "Cookie已失效，请重新登录"
            }
        else:
            return {
                "code": result.get("code", -1),
                "valid": False,
                "message": result.get("message", "Cookie验证失败")
            }
    
    async def get_play_record(self, uid: str, record_type: int = 1) -> Dict[str, Any]:
        """
        获取用户听歌排行（详细版）
        
        Args:
            uid: 用户ID
            record_type: 0-所有时间 1-最近一周
            
        Returns:
            包含weekData或allData的字典，每个歌曲记录包含:
            - playCount: 播放次数
            - score: 分数
            - song: 歌曲信息(id, name, artists, album等)
        """
        import re
        
        # 提取csrf_token
        csrf_token = ""
        if self.cookies:
            csrf_match = re.search(r'__csrf[=:]([a-zA-Z0-9]+)', self.cookies)
            if csrf_match:
                csrf_token = csrf_match.group(1)
        
        url = f"{self.BASE_URL}/weapi/v1/play/record"
        request_url = f"{url}?csrf_token={csrf_token}" if csrf_token else url
        
        data = {
            "uid": uid,
            "type": record_type,
            "csrf_token": csrf_token
        }
        
        result = await self._request("POST", request_url, data)
        logger.debug(f"听歌排行响应: {result}")
        
        return result
    
    async def get_user_playlists(self, uid: str, limit: int = 30, offset: int = 0) -> Dict[str, Any]:
        """
        获取用户歌单列表（详细版）
        
        Args:
            uid: 用户ID
            limit: 每页数量
            offset: 偏移量
            
        Returns:
            包含playlist数组的字典，每个歌单包含:
            - id: 歌单ID
            - name: 歌单名称
            - trackCount: 歌曲数
            - playCount: 播放次数
            - coverImgUrl: 封面图
            - creator: 创建者信息
        """
        import re
        
        # 提取csrf_token
        csrf_token = ""
        if self.cookies:
            csrf_match = re.search(r'__csrf[=:]([a-zA-Z0-9]+)', self.cookies)
            if csrf_match:
                csrf_token = csrf_match.group(1)
        
        url = f"{self.BASE_URL}/weapi/user/playlist"
        request_url = f"{url}?csrf_token={csrf_token}" if csrf_token else url
        
        data = {
            "uid": uid,
            "limit": limit,
            "offset": offset,
            "csrf_token": csrf_token
        }
        
        result = await self._request("POST", request_url, data)
        logger.debug(f"用户歌单响应: {result}")
        
        return result
    
    async def get_user_detail_from_html(self, uid: str) -> Dict[str, Any]:
        """
        通过解析HTML页面获取用户详细信息
        
        Args:
            uid: 用户ID
            
        Returns:
            包含用户详细信息的字典
        """
        import re
        
        url = f"{self.BASE_URL}/user/home?id={uid}"
        headers = self._get_headers()
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        
        # 构建Cookie
        base_cookie = f"os=pc; osver=Microsoft-Windows-10-Professional-build-19045-64bit; appver=2.10.16.200601; deviceId={self._device_id}"
        if self.cookies:
            headers["Cookie"] = f"{base_cookie}; {self.cookies}"
        else:
            headers["Cookie"] = base_cookie
        
        try:
            response = await self.client.get(url, headers=headers)
            html = response.text
            
            user_info = {
                "uid": uid,
                "nickname": "",
                "avatar_url": "",
                "background_url": "",
                "signature": "",
                "level": 0,
                "listen_songs": 0,
                "follows": 0,
                "followeds": 0,
                "event_count": 0,
                "create_days": 0,
                "province": 0,
                "city": 0
            }
            
            # 解析 JSON 数据 (页面中通常有 window.__INITIAL_STATE__ 或类似的数据)
            # 尝试解析 <script> 中的用户数据
            json_pattern = r'<script[^>]*>\s*window\.GUser\s*=\s*(\{[^;]+\});?\s*</script>'
            match = re.search(json_pattern, html)
            if match:
                try:
                    user_data = json.loads(match.group(1))
                    user_info["uid"] = str(user_data.get("userId", uid))
                    user_info["nickname"] = user_data.get("nickname", "")
                    user_info["avatar_url"] = user_data.get("avatarUrl", "")
                    user_info["signature"] = user_data.get("signature", "")
                    user_info["vip_type"] = user_data.get("vipType", 0)
                except json.JSONDecodeError:
                    pass
            
            # 解析听歌数量
            listen_pattern = r'累计听歌(\d+)首'
            listen_match = re.search(listen_pattern, html)
            if listen_match:
                user_info["listen_songs"] = int(listen_match.group(1))
            
            # 解析等级
            level_pattern = r'<a[^>]*class="[^"]*u-icn-lv[^"]*lv(\d+)[^"]*"'
            level_match = re.search(level_pattern, html)
            if level_match:
                user_info["level"] = int(level_match.group(1))
            
            # 解析关注数
            follows_pattern = r'<strong[^>]*id="follow_count"[^>]*>(\d+)</strong>'
            follows_match = re.search(follows_pattern, html)
            if follows_match:
                user_info["follows"] = int(follows_match.group(1))
            
            # 解析粉丝数
            followeds_pattern = r'<strong[^>]*id="fan_count"[^>]*>(\d+)</strong>'
            followeds_match = re.search(followeds_pattern, html)
            if followeds_match:
                user_info["followeds"] = int(followeds_match.group(1))
            
            # 解析动态数
            event_pattern = r'<a[^>]*href="/user/event[^"]*"[^>]*>\s*<strong>(\d+)</strong>'
            event_match = re.search(event_pattern, html)
            if event_match:
                user_info["event_count"] = int(event_match.group(1))
            
            # 解析注册天数
            days_pattern = r'(\d+)天前加入'
            days_match = re.search(days_pattern, html)
            if days_match:
                user_info["create_days"] = int(days_match.group(1))
            
            # 解析地区
            location_pattern = r'所在地区：([^<]+)'
            location_match = re.search(location_pattern, html)
            if location_match:
                user_info["location"] = location_match.group(1).strip()
            
            # 解析头像
            avatar_pattern = r'<img[^>]*class="[^"]*j-img[^"]*"[^>]*src="([^"]+)"'
            avatar_match = re.search(avatar_pattern, html)
            if avatar_match:
                user_info["avatar_url"] = avatar_match.group(1)
            
            # 解析昵称（备用方式）
            if not user_info["nickname"]:
                nickname_pattern = r'<span[^>]*class="[^"]*tit[^"]*"[^>]*>\s*<span[^>]*class="[^"]*name[^"]*"[^>]*>([^<]+)</span>'
                nickname_match = re.search(nickname_pattern, html)
                if nickname_match:
                    user_info["nickname"] = nickname_match.group(1).strip()
            
            # 备用: 从title获取昵称
            if not user_info["nickname"]:
                title_pattern = r'<title>([^<]+)的主页'
                title_match = re.search(title_pattern, html)
                if title_match:
                    user_info["nickname"] = title_match.group(1).strip()
            
            logger.info(f"从HTML解析用户信息: {user_info.get('nickname', 'unknown')}")
            return user_info
            
        except Exception as e:
            logger.error(f"解析用户HTML页面失败: {e}")
            return {"uid": uid, "error": str(e)}
    
    async def get_user_full_info(self, uid: str = None) -> Dict[str, Any]:
        """
        获取用户完整信息（优先从HTML解析，结合多个API）
        
        Args:
            uid: 用户ID，如果为空则从登录状态获取
            
        Returns:
            包含完整用户信息的字典
        """
        user_info = {
            "uid": uid or "",
            "nickname": "",
            "avatar_url": "",
            "background_url": "",
            "signature": "",
            "vip_type": 0,
            "level": 0,
            "province": 0,
            "city": 0,
            "gender": 0,
            "birthday": 0,
            "listen_songs": 0,
            "follows": 0,
            "followeds": 0,
            "event_count": 0,
            "playlist_count": 0,
            "create_days": 0
        }
        
        # 首先尝试API获取登录状态信息（获取uid）
        try:
            api_result = await self.get_login_status()
            if api_result.get("profile"):
                profile = api_result["profile"]
                uid = str(profile.get("userId", uid))
                user_info.update({
                    "uid": uid,
                    "nickname": profile.get("nickname", ""),
                    "avatar_url": profile.get("avatarUrl", ""),
                    "background_url": profile.get("backgroundUrl", ""),
                    "signature": profile.get("signature", ""),
                    "vip_type": profile.get("vipType", 0),
                    "province": profile.get("province", 0),
                    "city": profile.get("city", 0),
                    "gender": profile.get("gender", 0),
                    "birthday": profile.get("birthday", 0),
                    "follows": profile.get("follows", 0),
                    "followeds": profile.get("followeds", 0),
                    "event_count": profile.get("eventCount", 0),
                    "playlist_count": profile.get("playlistCount", 0)
                })
        except Exception as e:
            logger.warning(f"API获取登录状态失败: {e}")
        
        # 如果有uid，优先从HTML解析获取详细信息（更准确）
        if uid:
            try:
                html_info = await self.get_user_detail_from_html(uid)
                if html_info and not html_info.get("error"):
                    # HTML解析的数据通常更准确，优先使用
                    if html_info.get("level"):
                        user_info["level"] = html_info["level"]
                    if html_info.get("listen_songs"):
                        user_info["listen_songs"] = html_info["listen_songs"]
                    if html_info.get("follows"):
                        user_info["follows"] = html_info["follows"]
                    if html_info.get("followeds"):
                        user_info["followeds"] = html_info["followeds"]
                    if html_info.get("event_count"):
                        user_info["event_count"] = html_info["event_count"]
                    if html_info.get("create_days"):
                        user_info["create_days"] = html_info["create_days"]
                    if html_info.get("location"):
                        user_info["location"] = html_info["location"]
                    if html_info.get("nickname") and not user_info.get("nickname"):
                        user_info["nickname"] = html_info["nickname"]
                    if html_info.get("avatar_url") and not user_info.get("avatar_url"):
                        user_info["avatar_url"] = html_info["avatar_url"]
                    
                    logger.info(f"从HTML解析用户信息成功: {user_info.get('nickname')} Lv.{user_info.get('level')} 听歌{user_info.get('listen_songs')}首")
            except Exception as e:
                logger.warning(f"HTML解析用户信息失败: {e}")
            
            # 如果HTML解析失败或缺少数据，尝试API获取用户详情
            if not user_info.get("level") or not user_info.get("listen_songs"):
                try:
                    detail_result = await self.get_user_detail(uid)
                    if detail_result.get("code") == 200:
                        # 等级信息
                        if not user_info.get("level"):
                            user_info["level"] = detail_result.get("level", 0)
                        
                        # 听歌数
                        if not user_info.get("listen_songs"):
                            user_info["listen_songs"] = detail_result.get("listenSongs", 0)
                        
                        # 创建天数
                        if not user_info.get("create_days"):
                            user_info["create_days"] = detail_result.get("createDays", 0)
                        
                        # 从profile补充信息
                        profile = detail_result.get("profile", {})
                        if profile:
                            if not user_info.get("nickname"):
                                user_info["nickname"] = profile.get("nickname", "")
                            if not user_info.get("avatar_url"):
                                user_info["avatar_url"] = profile.get("avatarUrl", "")
                            if not user_info.get("signature"):
                                user_info["signature"] = profile.get("signature", "")
                            if not user_info.get("follows"):
                                user_info["follows"] = profile.get("follows", 0)
                            if not user_info.get("followeds"):
                                user_info["followeds"] = profile.get("followeds", 0)
                        
                        logger.info(f"从API获取用户详情: Lv.{user_info.get('level')} 听歌{user_info.get('listen_songs')}首")
                except Exception as e:
                    logger.warning(f"API获取用户详情失败: {e}")
        
        return user_info

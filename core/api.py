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
    
    async def get_user_level(self) -> Dict[str, Any]:
        """
        获取当前用户等级信息
        
        Returns:
            {
                "code": 200,
                "data": {
                    "userId": xxx,
                    "level": 9,
                    "progress": 0.70225,
                    "nowPlayCount": 8427,
                    "nextPlayCount": 12000,
                    "nowLoginCount": 350,
                    "nextLoginCount": 350,
                    "info": "..."
                }
            }
        """
        url = f"{self.BASE_URL}/weapi/user/level"
        return await self._request("POST", url, {})
    
    # ==================== 歌曲相关 ====================
    
    async def get_recommend_songs(self) -> Dict[str, Any]:
        """获取每日推荐歌曲 - 使用v2版本API"""
        url = f"{self.BASE_URL}/weapi/v2/discovery/recommend/songs"
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
    
    async def get_user_events(self, uid: str, lasttime: int = -1, limit: int = 30) -> Dict[str, Any]:
        """
        获取用户动态列表
        
        Args:
            uid: 用户ID
            lasttime: 上次查询的最后时间戳，用于分页
            limit: 每页数量
            
        Returns:
            动态列表响应
        """
        csrf_token = self._get_csrf_token()
        request_url = f"{self.WEAPI_URL}/event/get/{uid}?csrf_token={csrf_token}"
        
        data = {
            "time": lasttime,
            "limit": limit,
            "getcounts": "true",
            "csrf_token": csrf_token
        }
        
        result = await self._request("POST", request_url, data)
        return result
    
    async def get_user_follows(self, uid: str, offset: int = 0, limit: int = 30) -> Dict[str, Any]:
        """
        获取用户关注列表
        
        Args:
            uid: 用户ID
            offset: 偏移量
            limit: 每页数量
            
        Returns:
            关注列表响应
        """
        csrf_token = self._get_csrf_token()
        request_url = f"{self.WEAPI_URL}/user/getfollows/{uid}?csrf_token={csrf_token}"
        
        data = {
            "offset": offset,
            "limit": limit,
            "order": "true",
            "csrf_token": csrf_token
        }
        
        result = await self._request("POST", request_url, data)
        return result
    
    async def get_user_followeds(self, uid: str, offset: int = 0, limit: int = 30) -> Dict[str, Any]:
        """
        获取用户粉丝列表
        
        Args:
            uid: 用户ID
            offset: 偏移量
            limit: 每页数量
            
        Returns:
            粉丝列表响应
        """
        csrf_token = self._get_csrf_token()
        request_url = f"{self.WEAPI_URL}/user/getfolloweds?csrf_token={csrf_token}"
        
        data = {
            "userId": uid,
            "offset": offset,
            "limit": limit,
            "csrf_token": csrf_token
        }
        
        result = await self._request("POST", request_url, data)
        return result
    
    async def get_user_full_info(self, uid: str = None) -> Dict[str, Any]:
        """
        获取用户完整信息（结合多个API）
        
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
            "create_time": 0,  # 创建时间戳
            "listen_songs": 0,
            "follows": 0,
            "followeds": 0,
            "event_count": 0,
            "playlist_count": 0,
            "create_days": 0
        }
        
        # 首先尝试API获取登录状态信息（获取uid和基本信息）
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
                    "create_time": profile.get("createTime", 0),
                })
        except Exception as e:
            logger.warning(f"API获取登录状态失败: {e}")
        
        # 获取用户详情（等级、听歌数、创建天数等）
        if uid:
            try:
                detail_result = await self.get_user_detail(uid)
                if detail_result.get("code") == 200:
                    user_info["listen_songs"] = detail_result.get("listenSongs", 0)
                    user_info["create_days"] = detail_result.get("createDays", 0)
                    
                    profile = detail_result.get("profile", {})
                    if profile:
                        if not user_info.get("nickname"):
                            user_info["nickname"] = profile.get("nickname", "")
                        if not user_info.get("avatar_url"):
                            user_info["avatar_url"] = profile.get("avatarUrl", "")
                        if not user_info.get("create_time"):
                            user_info["create_time"] = profile.get("createTime", 0)
                        # 从详情页获取基础统计（后续会被专门API覆盖）
                        user_info["follows"] = profile.get("follows", 0)
                        user_info["followeds"] = profile.get("followeds", 0)
                        user_info["event_count"] = profile.get("eventCount", 0)
                        user_info["playlist_count"] = profile.get("playlistCount", 0)
            except Exception as e:
                logger.warning(f"API获取用户详情失败: {e}")
        
        # 使用等级API获取准确的等级和听歌数
        try:
            level_result = await self.get_user_level()
            if level_result.get("code") == 200:
                level_data = level_result.get("data", {})
                user_info["level"] = level_data.get("level", user_info.get("level", 0))
                now_play_count = level_data.get("nowPlayCount", 0)
                if now_play_count > 0:
                    user_info["listen_songs"] = now_play_count
        except Exception as e:
            logger.warning(f"API获取用户等级失败: {e}")
        
        # 使用专门API获取准确的关注数
        if uid:
            try:
                follows_result = await self.get_user_follows(uid, limit=1)
                if follows_result.get("code") == 200:
                    # 从分页信息获取总数，或者使用返回的follow列表长度
                    # 通常API会返回更准确的数量
                    pass  # 关注数已从profile获取
            except Exception as e:
                logger.debug(f"获取关注列表失败: {e}")
            
            # 使用专门API获取准确的粉丝数
            try:
                followers_result = await self.get_user_followers(uid, limit=1)
                if followers_result.get("code") == 200:
                    pass  # 粉丝数已从profile获取
            except Exception as e:
                logger.debug(f"获取粉丝列表失败: {e}")
            
            # 歌单数量已从profile中获取，这里不再重复调用API
            # 歌单数据会在其他地方（如歌单页面）调用 get_user_playlists 时同步到数据库
            
            # 使用动态API获取准确的动态数
            try:
                events_result = await self.get_user_events(uid, limit=1)
                if events_result.get("code") == 200:
                    # 动态API通常会返回总数
                    total = events_result.get("total", events_result.get("size", 0))
                    if total > 0:
                        user_info["event_count"] = total
            except Exception as e:
                logger.debug(f"获取动态列表失败: {e}")
        
        logger.info(f"获取用户完整信息: {user_info.get('nickname')} Lv.{user_info.get('level')} 关注{user_info.get('follows')} 粉丝{user_info.get('followeds')} 歌单{user_info.get('playlist_count')} 动态{user_info.get('event_count')}")
        
        return user_info

    async def get_discover_playlists_from_html(self, cat: str = None, order: str = "hot", limit: int = 35, offset: int = 0) -> List[Dict[str, Any]]:
        """
        从发现歌单页面HTML解析歌单列表
        
        Args:
            cat: 分类标签（如：华语、流行、摇滚等），None表示全部
            order: 排序方式，hot=最热, new=最新
            limit: 每页数量
            offset: 偏移量
            
        Returns:
            歌单列表 [{id, name, cover, play_count, creator}, ...]
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("需要安装 beautifulsoup4: pip install beautifulsoup4 lxml")
            return []
        
        try:
            # 构建URL
            url = f"{self.BASE_URL}/discover/playlist"
            params = {
                "order": order,
                "limit": str(limit),
                "offset": str(offset)
            }
            if cat:
                params["cat"] = cat
            
            # 直接请求HTML页面
            headers = {
                "User-Agent": self.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": f"{self.BASE_URL}/",
                "Cookie": self.cookies
            }
            
            response = await self.client.get(url, params=params, headers=headers)
            
            if response.status_code != 200:
                logger.warning(f"获取发现歌单页面失败: HTTP {response.status_code}")
                return []
            
            html = response.text
            soup = BeautifulSoup(html, "lxml")
            
            playlists = []
            
            # 解析歌单列表
            # 歌单在 id="m-pl-container" 的 ul 中
            pl_container = soup.find("ul", id="m-pl-container")
            if not pl_container:
                logger.warning("未找到歌单容器")
                return []
            
            # 每个歌单是一个 li 元素
            for li in pl_container.find_all("li"):
                try:
                    # 封面和链接
                    cover_div = li.find("div", class_="u-cover")
                    if not cover_div:
                        continue
                    
                    # 获取歌单ID和封面
                    a_tag = cover_div.find("a", class_="msk")
                    if not a_tag:
                        continue
                    
                    href = a_tag.get("href", "")
                    # href格式: /playlist?id=12345678
                    if "id=" not in href:
                        continue
                    
                    playlist_id = href.split("id=")[-1].split("&")[0]
                    
                    # 封面图片
                    img = cover_div.find("img")
                    cover_url = img.get("src", "") if img else ""
                    
                    # 播放次数
                    play_count_span = cover_div.find("span", class_="nb")
                    play_count_text = play_count_span.get_text(strip=True) if play_count_span else "0"
                    play_count = self._parse_play_count(play_count_text)
                    
                    # 歌单名称
                    name_a = li.find("a", class_="tit")
                    playlist_name = name_a.get("title", "") or name_a.get_text(strip=True) if name_a else ""
                    
                    # 创建者
                    creator_a = li.find("a", class_="nm")
                    creator_name = creator_a.get_text(strip=True) if creator_a else ""
                    
                    if playlist_id and playlist_name:
                        playlists.append({
                            "id": playlist_id,
                            "name": playlist_name,
                            "cover": cover_url,
                            "play_count": play_count,
                            "creator": creator_name
                        })
                        
                except Exception as e:
                    logger.debug(f"解析单个歌单失败: {e}")
                    continue
            
            logger.info(f"从发现页面解析到 {len(playlists)} 个歌单")
            return playlists
            
        except Exception as e:
            logger.error(f"解析发现歌单页面失败: {e}")
            return []
    
    def _parse_play_count(self, text: str) -> int:
        """解析播放次数文本（如：1.2万、100万+）"""
        text = text.strip().replace("+", "")
        try:
            if "亿" in text:
                return int(float(text.replace("亿", "")) * 100000000)
            elif "万" in text:
                return int(float(text.replace("万", "")) * 10000)
            else:
                return int(text)
        except:
            return 0

    async def get_discover_playlist_categories(self) -> Dict[str, Any]:
        """获取歌单分类列表"""
        return await self._weapi_request(
            "/api/playlist/catalogue",
            {}
        )

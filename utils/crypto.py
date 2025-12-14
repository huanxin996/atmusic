"""
加密工具模块 - 网易云API加密
"""
import base64
import hashlib
import json
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


# 网易云加密参数
MODULUS = "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7"
NONCE = "0CoJUm6Qyw8W8jud"
PUB_KEY = "010001"


def md5_encrypt(text: str) -> str:
    """MD5加密"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def create_secret_key(size: int = 16) -> str:
    """生成随机密钥"""
    return os.urandom(size).hex()[:size]


def aes_encrypt(text: str, key: str) -> str:
    """AES加密"""
    iv = "0102030405060708"
    cipher = AES.new(
        key.encode("utf-8"),
        AES.MODE_CBC,
        iv.encode("utf-8")
    )
    padded_text = pad(text.encode("utf-8"), AES.block_size)
    encrypted = cipher.encrypt(padded_text)
    return base64.b64encode(encrypted).decode("utf-8")


def rsa_encrypt(text: str, pub_key: str, modulus: str) -> str:
    """RSA加密"""
    text = text[::-1]
    rs = pow(int(text.encode("utf-8").hex(), 16), int(pub_key, 16), int(modulus, 16))
    return format(rs, "x").zfill(256)


def encrypt_request(data: dict) -> dict:
    """加密请求数据"""
    text = json.dumps(data)
    secret_key = create_secret_key(16)
    
    # 两次AES加密
    params = aes_encrypt(text, NONCE)
    params = aes_encrypt(params, secret_key)
    
    # RSA加密密钥
    enc_sec_key = rsa_encrypt(secret_key, PUB_KEY, MODULUS)
    
    return {
        "params": params,
        "encSecKey": enc_sec_key
    }


def encrypt_eapi(path: str, data: dict) -> dict:
    """EAPI加密"""
    import hashlib
    from Crypto.Cipher import AES
    
    eapi_key = b"e82ckenh8dichen8"
    text = json.dumps(data)
    message = f"nobody{path}use{text}md5forencrypt"
    digest = hashlib.md5(message.encode("utf-8")).hexdigest()
    params = f"{path}-36cd479b6b5-{text}-36cd479b6b5-{digest}"
    
    cipher = AES.new(eapi_key, AES.MODE_ECB)
    padded = pad(params.encode("utf-8"), 16)
    encrypted = cipher.encrypt(padded)
    
    return {
        "params": encrypted.hex().upper()
    }


def aes_decrypt(text: str, key: str) -> str:
    """AES解密"""
    iv = "0102030405060708"
    cipher = AES.new(
        key.encode("utf-8"),
        AES.MODE_CBC,
        iv.encode("utf-8")
    )
    encrypted_data = base64.b64decode(text)
    decrypted = cipher.decrypt(encrypted_data)
    # 移除PKCS7填充
    padding_len = decrypted[-1]
    return decrypted[:-padding_len].decode("utf-8", errors='ignore')


def decrypt_response(encrypted_params: str, secret_key: str) -> dict:
    """
    解密网易云API响应
    
    Args:
        encrypted_params: 加密的params数据（base64编码）
        secret_key: 加密时使用的secret key
        
    Returns:
        解密后的JSON字典
    """
    try:
        # 第一次AES解密（使用secret_key）
        decrypted_once = aes_decrypt(encrypted_params, secret_key)
        # 第二次AES解密（使用NONCE）
        decrypted_twice = aes_decrypt(decrypted_once, NONCE)
        # 解析JSON
        return json.loads(decrypted_twice)
    except Exception as e:
        print(f"解密失败: {e}")
        return None


"""
数据转换工具 - 省份城市码、时间戳等转换
"""
from datetime import datetime
from typing import Optional

# 中国省份代码映射
PROVINCE_CODES = {
    110000: "北京市", 120000: "天津市", 130000: "河北省", 140000: "山西省",
    150000: "内蒙古", 210000: "辽宁省", 220000: "吉林省", 230000: "黑龙江省",
    310000: "上海市", 320000: "江苏省", 330000: "浙江省", 340000: "安徽省",
    350000: "福建省", 360000: "江西省", 370000: "山东省", 410000: "河南省",
    420000: "湖北省", 430000: "湖南省", 440000: "广东省", 450000: "广西",
    460000: "海南省", 500000: "重庆市", 510000: "四川省", 520000: "贵州省",
    530000: "云南省", 540000: "西藏", 610000: "陕西省", 620000: "甘肃省",
    630000: "青海省", 640000: "宁夏", 650000: "新疆", 710000: "台湾省",
    810000: "香港", 820000: "澳门", 0: "未知"
}

# 河南省城市代码映射（示例，可扩展其他省份）
CITY_CODES = {
    # 河南省
    410100: "郑州市", 410200: "开封市", 410300: "洛阳市", 410400: "平顶山市",
    410500: "安阳市", 410600: "鹤壁市", 410700: "新乡市", 410800: "焦作市",
    410900: "濮阳市", 411000: "许昌市", 411100: "漯河市", 411200: "三门峡市",
    411300: "南阳市", 411400: "商丘市", 411500: "信阳市", 411600: "周口市",
    411700: "驻马店市", 419000: "济源市",
    # 北京
    110100: "北京市",
    # 上海
    310100: "上海市",
    # 广东省
    440100: "广州市", 440300: "深圳市", 440400: "珠海市", 440600: "佛山市",
    440700: "江门市", 440900: "茂名市", 441300: "惠州市", 441400: "梅州市",
    441900: "东莞市", 442000: "中山市",
    # 浙江省
    330100: "杭州市", 330200: "宁波市", 330300: "温州市", 330400: "嘉兴市",
    330500: "湖州市", 330600: "绍兴市", 330700: "金华市",
    # 江苏省
    320100: "南京市", 320200: "无锡市", 320300: "徐州市", 320400: "常州市",
    320500: "苏州市", 320600: "南通市",
    # 四川省
    510100: "成都市", 510300: "自贡市", 510400: "攀枝花市", 510500: "泸州市",
    # 湖北省
    420100: "武汉市", 420200: "黄石市", 420300: "十堰市", 420500: "宜昌市",
    # 更多城市可按需添加
    0: "未知"
}


def get_province_name(province_code: int) -> str:
    """根据省份代码获取省份名称"""
    if not province_code:
        return "未知"
    return PROVINCE_CODES.get(province_code, f"未知({province_code})")


def get_city_name(city_code: int) -> str:
    """根据城市代码获取城市名称"""
    if not city_code:
        return "未知"
    return CITY_CODES.get(city_code, f"未知({city_code})")


def get_location(province_code: int, city_code: int) -> str:
    """获取完整的地区名称"""
    province = get_province_name(province_code)
    city = get_city_name(city_code)
    
    if province == "未知" and city == "未知":
        return "未设置"
    if province == city:  # 直辖市
        return province
    if city == "未知":
        return province
    return f"{province} {city}"


def timestamp_to_date(timestamp: Optional[int], format_str: str = "%Y-%m-%d") -> str:
    """将时间戳转换为日期字符串"""
    if not timestamp:
        return "-"
    try:
        # 网易云返回的是毫秒级时间戳
        if timestamp > 10000000000:
            timestamp = timestamp / 1000
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime(format_str)
    except (ValueError, OSError):
        return "-"


def timestamp_to_datetime(timestamp: Optional[int], format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """将时间戳转换为日期时间字符串"""
    return timestamp_to_date(timestamp, format_str)


def timestamp_to_age(timestamp: Optional[int]) -> str:
    """将生日时间戳转换为年龄"""
    if not timestamp:
        return "-"
    try:
        if timestamp > 10000000000:
            timestamp = timestamp / 1000
        birth_date = datetime.fromtimestamp(timestamp)
        today = datetime.now()
        age = today.year - birth_date.year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        return str(age) if age > 0 else "-"
    except (ValueError, OSError):
        return "-"


def format_play_count(count: int) -> str:
    """格式化播放次数"""
    if count >= 100000000:
        return f"{count / 100000000:.1f}亿"
    elif count >= 10000:
        return f"{count / 10000:.1f}万"
    else:
        return str(count)


def format_duration(seconds: int) -> str:
    """格式化时长（秒转分:秒）"""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def format_duration_ms(milliseconds: int) -> str:
    """格式化时长（毫秒转分:秒）"""
    return format_duration(milliseconds // 1000)

# 网易云音乐刷歌助手 🎵

一个自动化刷取网易云音乐每日听歌数量和时长的工具，具有简洁美观的Web界面。

## ✨ 功能特性

- 🔐 **二维码登录** - 安全便捷，无需输入密码
- 👥 **多账号管理** - 支持登录多个账号，一键切换
- 🎵 **自动刷歌** - 模拟真实听歌行为，安全高效
- ⏱️ **刷歌时长** - 累计听歌时长，完成每日任务
- 📊 **实时进度** - WebSocket推送，实时查看刷歌进度
- 📱 **歌单选择** - 支持从每日推荐或指定歌单刷歌
- 📈 **听歌排行** - 查看最近一周和历史听歌榜单
- 👤 **用户详情** - 查看账户信息、等级、听歌数等（支持HTML解析）
- 🎨 **美观界面** - 现代化多页面UI设计，响应式布局
- ⚙️ **模块化架构** - 代码结构清晰，易于维护扩展

## 📁 项目结构

```text
atmusic/
├── main.py              # 应用入口
├── config.py            # 配置管理
├── requirements.txt     # 依赖列表
├── .env.example         # 环境变量示例
│
├── core/                # 核心业务模块
│   ├── __init__.py
│   ├── api.py          # 网易云API封装(含HTML解析)
│   ├── auth.py         # 认证模块(二维码登录)
│   └── player.py       # 播放器模块(刷歌核心)
│
├── web/                 # Web服务模块
│   ├── __init__.py
│   ├── app.py          # FastAPI应用工厂
│   ├── routes.py       # 页面路由
│   └── api.py          # API路由(含WebSocket)
│
├── data/                # 数据模块
│   ├── __init__.py
│   ├── database.py     # 数据库配置
│   └── models.py       # 数据模型
│
├── utils/               # 工具模块
│   ├── __init__.py
│   ├── logger.py       # 日志模块
│   ├── crypto.py       # 加密工具
│   ├── session.py      # 多用户会话管理
│   └── scheduler.py    # 定时任务
│
├── templates/           # HTML模板
│   ├── index.html      # 首页/控制面板
│   ├── login.html      # 登录页
│   ├── profile.html    # 用户详情
│   ├── ranking.html    # 听歌排行
│   ├── playlists.html  # 我的歌单
│   ├── play-count.html # 刷歌数量
│   └── play-time.html  # 刷歌时长
│
├── static/              # 静态资源
│   ├── css/            # 样式文件
│   └── js/             # JavaScript文件
│
├── logs/                # 日志目录
└── data/                # SQLite数据库
```

## 🚀 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境(推荐)
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制示例配置文件
cp .env.example .env

# 根据需要修改配置
```

### 3. 启动应用

```bash
python main.py
```

访问 `http://127.0.0.1:8080` 即可使用

## ⚙️ 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| HOST | 服务器地址 | 127.0.0.1 |
| PORT | 服务器端口 | 8080 |
| DEBUG | 调试模式 | true |
| PLAY_COUNT | 每日刷歌数量 | 300 |
| PLAY_INTERVAL_MIN | 刷歌最小间隔(秒) | 1 |
| PLAY_INTERVAL_MAX | 刷歌最大间隔(秒) | 3 |

## 🔧 技术栈

- **后端**: Python 3.9+ / FastAPI / SQLAlchemy
- **前端**: TailwindCSS / Alpine.js
- **数据库**: SQLite
- **其他**: httpx[brotli] / qrcode / loguru

## 📖 使用说明

1. **登录**: 打开应用后点击"添加"，使用网易云音乐APP扫描二维码
2. **选择账号**: 登录后在左侧账号列表中点击选择要使用的账号
3. **查看详情**: 进入"用户详情"查看账号信息（支持从网页解析更多数据）
4. **选择歌单**: 可以选择"每日推荐"或自己的歌单
5. **刷歌数量**: 设置要刷的歌曲数量，点击"开始刷歌"
6. **刷歌时长**: 设置累计时长，完成每日听歌任务

## ⚠️ 免责声明

本项目仅供学习交流使用，请勿用于商业目的。使用本工具产生的任何后果由用户自行承担。

## 📝 TODO

- [x] 多账号支持
- [x] 听歌排行榜
- [x] 用户详情页
- [ ] 定时任务功能
- [ ] 听歌历史记录
- [ ] Docker部署支持
- [ ] 移动端适配优化

## 📄 License

MIT License

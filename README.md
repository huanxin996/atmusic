# 网易云音乐刷歌助手

本项目用于自动化模拟播放以增加网易云音乐的听歌数量与时长。

## 功能

- 二维码登录（基于网易云音乐授权）
- 多账号管理与会话切换
- 自动化播放（按数量或按时长）
- 实时进度推送（通过 WebSocket）
- 支持从推荐或指定歌单抓取歌曲

## 项目结构（简要）

主要目录说明：

- `main.py`：应用入口
- `core/`：核心模块（网易云 API 封装、播放器）
- `web/`：Web 服务与路由（包含 API 与 WebSocket）
- `templates/`：前端 HTML 模板
- `static/`：静态资源（CSS/JS）
- `data/`：本地数据库与持久化

## 快速开始

1. 创建并激活 Python 虚拟环境：

```powershell
python -m venv venv
venv\Scripts\activate
```

2. 安装依赖：

```powershell
pip install -r requirements.txt
```

3. 复制配置示例并按需修改：

```powershell
copy .env.example .env
```

4. 启动应用：

```powershell
python main.py
```

默认服务地址： http://127.0.0.1:8080

## 主要配置项

- `HOST`：服务器地址（默认 127.0.0.1）
- `PORT`：服务器端口（默认 8080）
- `DEBUG`：调试模式（true/false）
- `PLAY_COUNT`：默认刷歌数量
- `PLAY_INTERVAL_MIN` / `PLAY_INTERVAL_MAX`：播放间隔范围（秒）

## 技术栈

- 后端：Python / FastAPI
- 前端：TailwindCSS / Alpine.js
- 数据库：SQLite（项目内置支持）

## 使用注意

仅限学习和研究用途。请遵守相关服务条款与法律法规，任何操作风险由使用者自行承担。

## TODO

- 定时任务功能
- 听歌历史记录
- Docker 部署支持

## 许可证

Apache License 2.0

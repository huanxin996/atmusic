"""
页面路由
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pathlib import Path

router = APIRouter()

# 模板目录
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def render_template(template_name: str) -> HTMLResponse:
    """渲染模板"""
    template_path = TEMPLATES_DIR / template_name
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页"""
    return render_template("index.html")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页"""
    return render_template("login.html")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """控制面板 - 重定向到用户详情"""
    return render_template("profile.html")


@router.get("/dashboard/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """用户详情页"""
    return render_template("profile.html")


@router.get("/dashboard/ranking", response_class=HTMLResponse)
async def ranking_page(request: Request):
    """听歌排行页"""
    return render_template("ranking.html")


@router.get("/dashboard/playlists", response_class=HTMLResponse)
async def playlists_page(request: Request):
    """我的歌单页"""
    return render_template("playlists.html")


@router.get("/dashboard/play-count", response_class=HTMLResponse)
async def play_count_page(request: Request):
    """刷歌数量页"""
    return render_template("play-count.html")


@router.get("/dashboard/play-time", response_class=HTMLResponse)
async def play_time_page(request: Request):
    """刷歌时长页"""
    return render_template("play-time.html")


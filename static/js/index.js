/**
 * 首页交互逻辑
 */
function app() {
    return {
        // 用户信息
        user: null,
        playlists: [],
        selectedPlaylist: '',
        playCount: 300,
        isRunning: false,
        progress: { current: 0, total: 0, progress: 0 },
        currentSong: null,
        todayStats: {},
        message: '',
        ws: null,

        // 初始化
        async init() {
            await this.checkAuth();
            if (this.user) {
                await this.loadPlaylists();
                await this.loadTodayStats();
                this.connectWebSocket();
            }
        },

        // 检查登录状态
        async checkAuth() {
            try {
                const res = await fetch('/api/auth/status');
                const data = await res.json();
                if (data.logged_in) {
                    this.user = data.user;
                }
            } catch (e) {
                console.error(e);
            }
        },

        // 加载歌单列表
        async loadPlaylists() {
            try {
                const res = await fetch('/api/playlists');
                const data = await res.json();
                if (data.success) {
                    this.playlists = data.playlists;
                }
            } catch (e) {
                console.error(e);
            }
        },

        // 加载今日统计
        async loadTodayStats() {
            try {
                const res = await fetch('/api/stats/today');
                this.todayStats = await res.json();
                this.isRunning = this.todayStats.is_running;
            } catch (e) {
                console.error(e);
            }
        },

        // 连接WebSocket
        connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            this.ws = new WebSocket(`${protocol}//${window.location.host}/api/ws`);
            
            this.ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'progress') {
                    this.progress = msg.data;
                    this.currentSong = msg.data.song;
                    this.todayStats.played_count = msg.data.current;
                } else if (msg.type === 'complete') {
                    this.isRunning = false;
                    this.showMessage('刷歌任务完成！共播放 ' + msg.data.played_count + ' 首');
                }
            };

            this.ws.onclose = () => {
                setTimeout(() => this.connectWebSocket(), 3000);
            };

            // 心跳保活
            setInterval(() => {
                if (this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send('ping');
                }
            }, 30000);
        },

        // 开始刷歌
        async startPlay() {
            try {
                const res = await fetch('/api/play/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        count: parseInt(this.playCount),
                        playlist_id: this.selectedPlaylist || null
                    })
                });
                const data = await res.json();
                if (data.success) {
                    this.isRunning = true;
                    this.progress = { current: 0, total: this.playCount, progress: 0 };
                    this.showMessage('任务已启动');
                } else {
                    this.showMessage(data.detail || '启动失败');
                }
            } catch (e) {
                this.showMessage('请求失败');
            }
        },

        // 停止刷歌
        async stopPlay() {
            try {
                const res = await fetch('/api/play/stop', { method: 'POST' });
                const data = await res.json();
                this.showMessage(data.message);
            } catch (e) {
                this.showMessage('请求失败');
            }
        },

        // 退出登录
        async logout() {
            await fetch('/api/auth/logout', { method: 'POST' });
            this.user = null;
            window.location.href = '/';
        },

        // 显示消息
        showMessage(msg) {
            this.message = msg;
            setTimeout(() => this.message = '', 3000);
        }
    };
}

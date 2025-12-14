/**
 * 单首歌刷取页逻辑
 */
function singleSongPage() {
    return {
        // 单首歌任务
        singleSong: {
            songId: '',
            target: 100,
            interval: 3,
            running: false,
            completed: 0,
            songName: '',
            logs: []
        },
        // 日志自动滚动选项（true = 新日志到达时自动滚动到顶部）
        autoScrollLogs: true,

        // 计算进度（作为方法以确保与 Alpine 的响应式更新兼容）
        progress() {
            try {
                const target = Number(this.singleSong.target) || 0;
                const completed = Number(this.singleSong.completed) || 0;
                if (target <= 0) return 0;
                const pct = Math.round((completed / target) * 100);
                // 限制在 0-100 之间
                if (!isFinite(pct) || isNaN(pct)) return 0;
                return Math.max(0, Math.min(100, pct));
            } catch (e) {
                return 0;
            }
        },

        // 页面初始化
        async pageInit() {
            await this.loadTaskStatus();            // 管理化的任务 WebSocket：支持自动重连与 unload 清理
            this.taskWs = null;
            this._taskWsReconnectTimer = null;
            this._taskWsAttempts = 0;
            this._taskWsIntentionalClose = false;

            const connectTaskWs = () => {
                try {
                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    this.taskWs = new WebSocket(`${protocol}//${window.location.host}/api/ws/task`);

                    this.taskWs.onopen = () => {
                        this._taskWsAttempts = 0;
                    };

                    this.taskWs.onmessage = (event) => {
                        try {
                            const data = JSON.parse(event.data);
                            // 仅处理单首歌模式的 play_count 更新
                            if (data.type === 'play_count' && data.mode === 'single') {
                                if (data.count !== undefined) this.singleSong.completed = data.count;
                                if (data.log) {
                                    this.addLog(data.log, data.logType || 'info');
                                    if (data.log.includes('开始刷取歌曲:')) {
                                        const match = data.log.match(/开始刷取歌曲:\s*(.+)/);
                                        if (match) this.singleSong.songName = match[1];
                                    }
                                }
                            }
                            if (data.type === 'task_status' && data.task === 'play_count') {
                                this.singleSong.running = data.running;
                                // 同步共享状态，确保侧边栏绿点与页面一致
                                window.sharedTaskStatus.playCountRunning = data.running;
                            }
                        } catch (err) {
                            console.error('解析任务WS消息失败:', err);
                        }
                    };

                    this.taskWs.onclose = () => {
                        if (this._taskWsIntentionalClose) return;
                        // 指数退避重连
                        const delay = Math.min(30000, 1000 * Math.pow(2, this._taskWsAttempts));
                        this._taskWsAttempts += 1;
                        this._taskWsReconnectTimer = setTimeout(() => connectTaskWs(), delay);
                    };

                    this.taskWs.onerror = (err) => {
                        console.error('任务WS错误:', err);
                    };
                } catch (err) {
                    console.error('连接任务WS失败:', err);
                    // 失败也尝试重连
                    if (!this._taskWsIntentionalClose) {
                        this._taskWsReconnectTimer = setTimeout(connectTaskWs, 3000);
                    }
                }
            };

            connectTaskWs();

            // 在页面卸载时清理 WS 连接与重连定时器
            const closeTaskWs = () => {
                this._taskWsIntentionalClose = true;
                if (this._taskWsReconnectTimer) {
                    clearTimeout(this._taskWsReconnectTimer);
                    this._taskWsReconnectTimer = null;
                }
                if (this.taskWs && (this.taskWs.readyState === WebSocket.OPEN || this.taskWs.readyState === WebSocket.CONNECTING)) {
                    try { this.taskWs.close(); } catch (e) { /* ignore */ }
                }
                try { window.removeEventListener('ws-message', this._wsMessageHandler); } catch (e) { }
            };
            window.addEventListener('beforeunload', closeTaskWs);
            window.addEventListener('unload', closeTaskWs);

            // 监听用户切换
            window.addEventListener('user-switched', () => { this.loadTaskStatus(); });

            // 监听全局任务状态事件，确保当其他页面改变任务时本页也能同步
            this._wsMessageHandler = (e) => {
                try {
                    const data = e.detail;
                    if (!data || data.type !== 'task_status') return;
                    if (data.task === 'play_count') {
                        this.singleSong.running = !!data.running;
                    }
                    if (data.play_count_running !== undefined) {
                        this.singleSong.running = !!data.play_count_running;
                    }
                } catch (err) { }
            };
            window.addEventListener('ws-message', this._wsMessageHandler);
        },

        // 加载任务状态
        async loadTaskStatus() {
            try {
                const response = await fetch('/api/task/status');
                const data = await response.json();
                if (data.code === 200) {
                    // 仅同步运行状态；今日计数由 task WS（mode=single）更新，避免与批量计数混淆
                    this.singleSong.running = data.play_count_running || false;
                    // don't set singleSong.completed here to avoid mixing counts; wait for WS updates
                }
            } catch (error) {
                console.error('加载任务状态失败:', error);
            }
        },

        // 开始单首歌任务
        async startSingleSongTask() {
            // 互斥检查：不能在刷时长任务或批量刷歌运行时启动单首刷歌
            if (window.sharedTaskStatus && window.sharedTaskStatus.playTimeRunning) {
                this.addLog('任务无法启动: 刷歌时长任务正在运行，请先停止它。', 'error');
                return;
            }
            if (window.sharedTaskStatus && window.sharedTaskStatus.playCountRunning) {
                this.addLog('任务无法启动: 另一个刷歌任务(批量或单首)正在运行，请先停止它。', 'error');
                return;
            }
            if (this.singleSong.running || !this.singleSong.songId) return;

            try {
                const response = await fetch('/api/task/single-song/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        song_id: this.singleSong.songId,
                        target: this.singleSong.target,
                        interval: this.singleSong.interval
                    })
                });
                const data = await response.json();
                if (data.code === 200) {
                    this.singleSong.running = true;
                    this.singleSong.completed = 0;
                    // 立即同步侧边栏状态，后端广播也会同步但这里给用户即时反馈
                    window.sharedTaskStatus.playCountRunning = true;
                    if (this.taskStatus) this.taskStatus.playCountRunning = true;
                    this.addLog('任务已启动', 'success');
                } else {
                    this.addLog('启动失败: ' + data.message, 'error');
                }
            } catch (error) {
                this.addLog('启动失败: ' + error.message, 'error');
            }
        },

        // 停止单首歌任务
        async stopSingleSongTask() {
            try {
                const response = await fetch('/api/task/single-song/stop', { method: 'POST' });
                const data = await response.json();
                if (data.code === 200) {
                    this.singleSong.running = false;
                    // 同步侧边栏状态
                    window.sharedTaskStatus.playCountRunning = false;
                    if (this.taskStatus) this.taskStatus.playCountRunning = false;
                    this.addLog('任务已停止', 'info');
                }
            } catch (error) {
                this.addLog('停止失败: ' + error.message, 'error');
            }
        },

        // 添加日志
        addLog(message, type = 'info') {
            const now = new Date();
            const time = now.toLocaleTimeString('zh-CN', { hour12: false });
            const id = Date.now().toString() + '_' + Math.floor(Math.random() * 1000000);
            // oldest-first: push 到末尾，用户向下滚动查看最新日志
            // 避免重复（与 sidebar 或其它 listener 导致的重复消息）——如果最后一条与当前一致则忽略
            const last = this.singleSong.logs[this.singleSong.logs.length - 1];
            if (last && last.message === message && last.type === type) return;
            this.singleSong.logs.push({ id, time, message, type });
            // 限制日志数量（保留最新 100 条 — 删除最早的）
            if (this.singleSong.logs.length > 100) {
                this.singleSong.logs.shift();
            }
            // 自动滚动到容器底部（最新日志在底部）
            try {
                if (this.autoScrollLogs) {
                    const el = document.getElementById('singleSongLogs');
                    if (el) {
                        try { el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' }); } catch (e) { el.scrollTop = el.scrollHeight; }
                    }
                }
            } catch (e) { /* ignore DOM errors */ }
        }
    };
}

// 设置页面初始化函数
window.pageInit = function(app) {
    app.pageInit();
};
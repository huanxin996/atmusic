/**
 * 刷歌时长页逻辑
 */
function playTimePage() {
    return {
        // 播放时长任务
        playTime: {
            today: 0,
            target: 60,
            songDuration: 30,
            source: 'recommend',  // recommend=每日推荐, discover=发现歌单
            running: false,
            logs: []
        },
        // 日志自动滚动选项（true = 新日志到达时自动滚动到顶部）
        autoScrollLogs: true,
        // 页面初始化
        async pageInit() {
            await this.loadTaskStatus();
            // 监听来自侧边栏的状态更新（仅状态类消息）
            window.addEventListener('ws-message', (e) => {
                const data = e.detail;
                if (data.type === 'task_status' && data.task === 'play_time') {
                    this.playTime.running = data.running;
                }
            });

            // 管理化的任务 WS：自动重连 + 页面 unload 清理
            this.taskWs = null;
            this._taskWsReconnectTimer = null;
            this._taskWsAttempts = 0;
            this._taskWsIntentionalClose = false;

            const connectTaskWs = () => {
                try {
                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    this.taskWs = new WebSocket(`${protocol}//${window.location.host}/api/ws/task`);

                    this.taskWs.onopen = () => { this._taskWsAttempts = 0; };

                    this.taskWs.onmessage = (event) => {
                        try {
                            const data = JSON.parse(event.data);
                            if (data.type === 'play_time') {
                                if (data.seconds !== undefined) this.playTime.today = data.seconds;
                                if (data.log) this.addLog(data.log, data.logType || 'info');
                            }
                            if (data.type === 'task_status' && data.task === 'play_time') {
                                this.playTime.running = data.running;
                            }
                        } catch (err) {
                            console.error('解析任务WS消息失败:', err);
                        }
                    };

                    this.taskWs.onclose = () => {
                        if (this._taskWsIntentionalClose) return;
                        const delay = Math.min(30000, 1000 * Math.pow(2, this._taskWsAttempts));
                        this._taskWsAttempts += 1;
                        this._taskWsReconnectTimer = setTimeout(() => connectTaskWs(), delay);
                    };

                    this.taskWs.onerror = (err) => { console.error('任务WS错误:', err); };
                } catch (err) {
                    console.error('连接任务WS失败:', err);
                    if (!this._taskWsIntentionalClose) {
                        this._taskWsReconnectTimer = setTimeout(connectTaskWs, 3000);
                    }
                }
            };

            connectTaskWs();

            const closeTaskWs = () => {
                this._taskWsIntentionalClose = true;
                if (this._taskWsReconnectTimer) { clearTimeout(this._taskWsReconnectTimer); this._taskWsReconnectTimer = null; }
                if (this.taskWs && (this.taskWs.readyState === WebSocket.OPEN || this.taskWs.readyState === WebSocket.CONNECTING)) {
                    try { this.taskWs.close(); } catch (e) { }
                }
            };
            window.addEventListener('beforeunload', closeTaskWs);
            window.addEventListener('unload', closeTaskWs);
            
            // 监听用户切换
            window.addEventListener('user-switched', () => {
                this.loadTaskStatus();
            });
        },
        
        // 加载任务状态
        async loadTaskStatus() {
            try {
                const response = await fetch('/api/task/status');
                const data = await response.json();
                if (data.code === 200) {
                    // 仅同步运行状态；今日时长由 task WS 更新，避免与其他页面混淆
                    this.playTime.running = data.play_time_running || false;
                }
            } catch (error) {
                console.error('加载任务状态失败:', error);
            }
        },
        
        // 开始刷时长任务
        async startPlayTimeTask() {
            // 互斥检查：不能在刷歌数量或单首刷歌运行时启动刷时长
            if (this.taskStatus && this.taskStatus.playCountRunning) {
                this.addLog('任务无法启动: 刷歌数量/单首刷歌任务正在运行，请先停止它。', 'error');
                return;
            }
            if (this.playTime.running) return;
            
            try {
                const response = await fetch('/api/task/play-time/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        target: this.playTime.target,
                        songDuration: this.playTime.songDuration,
                        source: this.playTime.source
                    })
                });
                const data = await response.json();
                if (data.code === 200) {
                    this.playTime.running = true;
                    this.addLog('任务已启动', 'success');
                } else {
                    this.addLog('启动失败: ' + data.message, 'error');
                }
            } catch (error) {
                this.addLog('启动失败: ' + error.message, 'error');
            }
        },
        
        // 停止刷时长任务
        async stopPlayTimeTask() {
            try {
                const response = await fetch('/api/task/play-time/stop', { method: 'POST' });
                const data = await response.json();
                if (data.code === 200) {
                    this.playTime.running = false;
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
            // oldest-first: append
            const last = this.playTime.logs[this.playTime.logs.length - 1];
            if (last && last.message === message && last.type === type) return;
            this.playTime.logs.push({ id, time, message, type });
            if (this.playTime.logs.length > 100) { this.playTime.logs.shift(); }
            // 自动滚动到底部
            try {
                if (this.autoScrollLogs) {
                    const el = document.getElementById('playTimeLogs');
                    if (el) { try { el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' }); } catch (e) { el.scrollTop = el.scrollHeight; } }
                }
            } catch (e) { }
        }
    };
}

// 设置页面初始化函数
window.pageInit = function(app) {
    app.pageInit();
};

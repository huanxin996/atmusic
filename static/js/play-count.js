/**
 * 刷歌数量页逻辑
 */
function playCountPage() {
    return {
        // 播放数量任务
        playCount: {
            today: 0,
            target: 300,
            interval: 3,
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
                if (data.type === 'task_status' && data.task === 'play_count') {
                    this.playCount.running = data.running;
                }
            });

            // 为获取详细日志与进度建立独立的任务WS连接（支持自动重连与 unload 清理）
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
                            // 仅处理批量刷歌（batch）消息，忽略单首刷歌模式
                            if (data.type === 'play_count') {
                                if (data.mode && data.mode === 'single') return;
                                if (data.count !== undefined) this.playCount.today = data.count;
                                if (data.log) this.addLog(data.log, data.logType || 'info');
                            }
                            if (data.type === 'task_status' && data.task === 'play_count') {
                                this.playCount.running = data.running;
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
                    this.playCount.running = data.play_count_running || false;
                    this.playCount.today = data.play_count_today || 0;
                }
            } catch (error) {
                console.error('加载任务状态失败:', error);
            }
        },
        
        // 开始刷歌任务
        async startPlayCountTask() {
            // 互斥检查：如果刷时长任务正在运行，则不能启动刷数量
            if (this.taskStatus && this.taskStatus.playTimeRunning) {
                this.addLog('任务无法启动: 刷歌时长任务正在运行，请先停止它。', 'error');
                return;
            }
            if (this.playCount.running) return;
            
            try {
                const response = await fetch('/api/task/play-count/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        target: this.playCount.target,
                        interval: this.playCount.interval,
                        source: this.playCount.source
                    })
                });
                const data = await response.json();
                if (data.code === 200) {
                    this.playCount.running = true;
                    this.addLog('任务已启动', 'success');
                } else {
                    this.addLog('启动失败: ' + data.message, 'error');
                }
            } catch (error) {
                this.addLog('启动失败: ' + error.message, 'error');
            }
        },
        
        // 停止刷歌任务
        async stopPlayCountTask() {
            try {
                const response = await fetch('/api/task/play-count/stop', { method: 'POST' });
                const data = await response.json();
                if (data.code === 200) {
                    this.playCount.running = false;
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
            // oldest-first: append to bottom
            // 避免重复
            const last = this.playCount.logs[this.playCount.logs.length - 1];
            if (last && last.message === message && last.type === type) return;
            this.playCount.logs.push({ id, time, message, type });
            if (this.playCount.logs.length > 100) { this.playCount.logs.shift(); }
            // 自动滚动到底部
            try {
                if (this.autoScrollLogs) {
                    const el = document.getElementById('playCountLogs');
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

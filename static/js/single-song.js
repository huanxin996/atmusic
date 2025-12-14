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

        // 计算属性
        get progress() {
            if (this.singleSong.target === 0) return 0;
            return Math.round((this.singleSong.completed / this.singleSong.target) * 100);
        },

        // 页面初始化
        async pageInit() {
            await this.loadTaskStatus();

            // 监听WebSocket消息
            window.addEventListener('ws-message', (e) => {
                const data = e.detail;
                // 任务状态更新
                if (data.type === 'task_status') {
                    // 处理新的task_status格式: {"type": "task_status", "task": "play_count", "running": true}
                    if (data.task === 'play_count') {
                        this.singleSong.running = data.running;
                    }
                }
                // 单首歌任务更新（包含日志和计数）
                if (data.type === 'play_count') {
                    if (data.count !== undefined) {
                        this.singleSong.completed = data.count;
                    }
                    if (data.log) {
                        this.addLog(data.log, data.logType || 'info');
                        // 从日志中提取歌曲名称
                        if (data.log.includes('开始刷取歌曲:')) {
                            const match = data.log.match(/开始刷取歌曲:\s*(.+)/);
                            if (match) {
                                this.singleSong.songName = match[1];
                            }
                        }
                    }
                }
            });

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
                    this.singleSong.running = data.play_count_running || false;
                    this.singleSong.completed = data.play_count_today || 0;
                }
            } catch (error) {
                console.error('加载任务状态失败:', error);
            }
        },

        // 开始单首歌任务
        async startSingleSongTask() {
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
            this.singleSong.logs.unshift({ time, message, type });
            // 限制日志数量
            if (this.singleSong.logs.length > 100) {
                this.singleSong.logs.pop();
            }
        }
    };
}

// 设置页面初始化函数
window.pageInit = function(app) {
    app.pageInit();
};
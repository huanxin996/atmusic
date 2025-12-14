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
            running: false,
            logs: []
        },
        
        // 页面初始化
        async pageInit() {
            await this.loadTaskStatus();
            
            // 监听WebSocket消息
            window.addEventListener('ws-message', (e) => {
                const data = e.detail;
                if (data.type === 'task_status') {
                    this.playTime.running = data.play_time_running;
                }
                if (data.type === 'play_time_log') {
                    this.addLog(data.message, data.log_type);
                }
                if (data.type === 'play_time_progress') {
                    this.playTime.today = data.seconds;
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
                    this.playTime.running = data.play_time_running || false;
                    this.playTime.today = data.play_time_today || 0;
                }
            } catch (error) {
                console.error('加载任务状态失败:', error);
            }
        },
        
        // 开始刷时长任务
        async startPlayTimeTask() {
            if (this.playTime.running) return;
            
            try {
                const response = await fetch('/api/task/play-time/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        target_minutes: this.playTime.target,
                        song_duration: this.playTime.songDuration
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
            this.playTime.logs.unshift({ time, message, type });
            // 限制日志数量
            if (this.playTime.logs.length > 100) {
                this.playTime.logs.pop();
            }
        }
    };
}

// 设置页面初始化函数
window.pageInit = function(app) {
    app.pageInit();
};

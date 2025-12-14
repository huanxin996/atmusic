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
                    this.playCount.running = data.play_count_running;
                }
                if (data.type === 'play_count_log') {
                    this.addLog(data.message, data.log_type);
                }
                if (data.type === 'play_count_progress') {
                    this.playCount.today = data.count;
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
                    this.playCount.running = data.play_count_running || false;
                    this.playCount.today = data.play_count_today || 0;
                }
            } catch (error) {
                console.error('加载任务状态失败:', error);
            }
        },
        
        // 开始刷歌任务
        async startPlayCountTask() {
            if (this.playCount.running) return;
            
            try {
                const response = await fetch('/api/task/play-count/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        count: this.playCount.target,
                        interval: this.playCount.interval
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
            this.playCount.logs.unshift({ time, message, type });
            // 限制日志数量
            if (this.playCount.logs.length > 100) {
                this.playCount.logs.pop();
            }
        }
    };
}

// 设置页面初始化函数
window.pageInit = function(app) {
    app.pageInit();
};

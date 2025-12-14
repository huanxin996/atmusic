/**
 * Dashboard页面交互逻辑 - 多用户版
 */
function dashboard() {
    return {
        // 当前标签页
        currentTab: 'profile',
        loading: false,
        validating: false,
        cookieValid: true,
        ws: null,
        
        // 用户列表
        users: [],
        
        // 当前用户信息
        user: {
            userId: null,
            nickname: '',
            avatarUrl: '',
            signature: '',
            level: 0,
            vipType: 0,
            gender: 0,
            follows: 0,
            followeds: 0,
            playlistCount: 0,
            eventCount: 0,
            listenSongs: 0,
            createTime: null,
            location: ''
        },
        
        // 听歌排行
        recordType: 1, // 1-最近一周 0-所有时间
        playRecords: [],
        
        // 用户歌单
        playlists: [],
        
        // 播放数量任务
        playCount: {
            today: 0,
            target: 300,
            interval: 3,
            running: false,
            logs: []
        },
        // 日志自动滚动选项
        autoScrollPlayCountLogs: true,
        
        // 播放时长任务
        playTime: {
            today: 0,
            target: 60,
            songDuration: 30,
            running: false,
            logs: []
        },
        autoScrollPlayTimeLogs: true,
        
        // 初始化
        async init() {
            await this.loadUsers();
            await this.loadUserInfo();
            this.connectWebSocket();
        },
        
        // 加载用户列表
        async loadUsers() {
            try {
                const response = await fetch('/api/users');
                const data = await response.json();
                if (data.code === 200) {
                    this.users = data.users || [];
                }
            } catch (error) {
                console.error('加载用户列表失败:', error);
            }
        },
        
        // 加载当前用户详细信息
        async loadUserInfo() {
            this.loading = true;
            try {
                const response = await fetch('/api/users/current');
                const data = await response.json();
                
                if (data.code === 200 && data.data) {
                    const info = data.data;
                    this.user = {
                        userId: info.uid,
                        nickname: info.nickname || '用户',
                        avatarUrl: info.avatar_url || '',
                        signature: info.signature || '',
                        level: info.level || 0,
                        vipType: info.vip_type || 0,
                        gender: info.gender || 0,
                        follows: info.follows || 0,
                        followeds: info.followeds || 0,
                        playlistCount: info.playlist_count || 0,
                        eventCount: info.event_count || 0,
                        listenSongs: info.listen_songs || 0,
                        createTime: info.create_time || '-',
                        location: info.location || '未设置'
                    };
                    this.cookieValid = true;
                } else if (data.code === 401) {
                    window.location.href = '/';
                }
            } catch (error) {
                console.error('获取用户信息失败:', error);
            } finally {
                this.loading = false;
            }
        },
        
        // 验证Cookie有效性
        async validateCookie() {
            this.validating = true;
            try {
                const response = await fetch('/api/auth/validate');
                const data = await response.json();
                this.cookieValid = data.valid === true;
                
                if (!this.cookieValid) {
                    alert('Cookie已失效，请重新登录');
                }
            } catch (error) {
                console.error('验证Cookie失败:', error);
                this.cookieValid = false;
            } finally {
                this.validating = false;
            }
        },
        
        // 切换用户
        async switchUser(userId) {
            if (this.loading) return;
            
            try {
                const response = await fetch(`/api/users/switch/${userId}`, { method: 'POST' });
                const data = await response.json();
                
                if (data.code === 200) {
                    await this.loadUsers();
                    await this.loadUserInfo();
                    // 清空相关数据
                    this.playRecords = [];
                    this.playlists = [];
                }
            } catch (error) {
                console.error('切换用户失败:', error);
            }
        },
        
        // 删除用户
        async deleteUser(userId) {
            if (!confirm('确定要删除该账号吗？')) return;
            
            try {
                const response = await fetch(`/api/users/${userId}`, { method: 'DELETE' });
                const data = await response.json();
                
                if (data.code === 200) {
                    await this.loadUsers();
                    if (this.users.length === 0) {
                        window.location.href = '/';
                    } else {
                        await this.loadUserInfo();
                    }
                }
            } catch (error) {
                console.error('删除用户失败:', error);
            }
        },
        
        // 加载听歌排行
        async loadPlayRecord(type = 1) {
            this.recordType = type;
            this.loading = true;
            try {
                const response = await fetch(`/api/user/play-record?record_type=${type}`);
                const data = await response.json();
                
                if (data.code === 200) {
                    this.playRecords = data.records || [];
                }
            } catch (error) {
                console.error('加载听歌排行失败:', error);
            } finally {
                this.loading = false;
            }
        },
        
        // 加载用户歌单
        async loadPlaylists() {
            this.loading = true;
            try {
                const response = await fetch('/api/user/playlists');
                const data = await response.json();
                
                if (data.code === 200) {
                    this.playlists = data.playlists || [];
                }
            } catch (error) {
                console.error('加载歌单失败:', error);
            } finally {
                this.loading = false;
            }
        },
        
        // 刷新用户信息
        async refreshUserInfo() {
            await this.loadUserInfo();
        },
        
        // 连接WebSocket
        connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            this.ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/task`);
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWSMessage(data);
            };
            
            this.ws.onclose = () => {
                setTimeout(() => this.connectWebSocket(), 3000);
            };
        },
        
        // 处理WebSocket消息
        handleWSMessage(data) {
            if (data.type === 'play_count') {
                this.playCount.today = data.count;
                if (data.log) {
                    this.addLog('playCount', data.log, data.logType || 'info');
                }
            } else if (data.type === 'play_time') {
                this.playTime.today = data.seconds;
                if (data.log) {
                    this.addLog('playTime', data.log, data.logType || 'info');
                }
            } else if (data.type === 'task_status') {
                if (data.task === 'play_count') {
                    this.playCount.running = data.running;
                } else if (data.task === 'play_time') {
                    this.playTime.running = data.running;
                }
            }
        },
        
        // 添加日志
        addLog(type, message, logType = 'info') {
            const now = new Date();
            const time = now.toTimeString().split(' ')[0];
            const id = Date.now().toString() + '_' + Math.floor(Math.random() * 1000000);
            const log = { id, time: `[${time}]`, message, type: logType };

            if (type === 'playCount') {
                // oldest-first: append
                const last = this.playCount.logs[this.playCount.logs.length - 1];
                if (!(last && last.message === message && last.type === logType)) {
                    this.playCount.logs.push(log);
                    if (this.playCount.logs.length > 100) this.playCount.logs.shift();
                }
            } else {
                const last = this.playTime.logs[this.playTime.logs.length - 1];
                if (!(last && last.message === message && last.type === logType)) {
                    this.playTime.logs.push(log);
                    if (this.playTime.logs.length > 100) this.playTime.logs.shift();
                }
            }
            // 自动滚动支持：滚动到底部显示最新日志
            try {
                if (type === 'playCount' && this.autoScrollPlayCountLogs) {
                    const el = document.getElementById('playCountLogsDashboard');
                    if (el) { try { el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' }); } catch (e) { el.scrollTop = el.scrollHeight; } }
                } else if (type === 'playTime' && this.autoScrollPlayTimeLogs) {
                    const el = document.getElementById('playTimeLogsDashboard');
                    if (el) { try { el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' }); } catch (e) { el.scrollTop = el.scrollHeight; } }
                }
            } catch (e) { }
        },
        
        // 开始刷歌数量任务
        async startPlayCountTask() {
            try {
                const response = await fetch('/api/task/play-count/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        target: this.playCount.target,
                        interval: this.playCount.interval
                    })
                });
                const data = await response.json();
                if (data.code === 200) {
                    this.playCount.running = true;
                    this.addLog('playCount', '任务已启动', 'success');
                } else {
                    this.addLog('playCount', data.message || '启动失败', 'error');
                }
            } catch (error) {
                this.addLog('playCount', '启动失败: ' + error.message, 'error');
            }
        },
        
        // 停止刷歌数量任务
        async stopPlayCountTask() {
            try {
                const response = await fetch('/api/task/play-count/stop', { method: 'POST' });
                const data = await response.json();
                if (data.code === 200) {
                    this.playCount.running = false;
                    this.addLog('playCount', '任务已停止', 'info');
                }
            } catch (error) {
                this.addLog('playCount', '停止失败: ' + error.message, 'error');
            }
        },
        
        // 开始刷时长任务
        async startPlayTimeTask() {
            try {
                const response = await fetch('/api/task/play-time/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        target: this.playTime.target,
                        songDuration: this.playTime.songDuration
                    })
                });
                const data = await response.json();
                if (data.code === 200) {
                    this.playTime.running = true;
                    this.addLog('playTime', '任务已启动', 'success');
                } else {
                    this.addLog('playTime', data.message || '启动失败', 'error');
                }
            } catch (error) {
                this.addLog('playTime', '启动失败: ' + error.message, 'error');
            }
        },
        
        // 停止刷时长任务
        async stopPlayTimeTask() {
            try {
                const response = await fetch('/api/task/play-time/stop', { method: 'POST' });
                const data = await response.json();
                if (data.code === 200) {
                    this.playTime.running = false;
                    this.addLog('playTime', '任务已停止', 'info');
                }
            } catch (error) {
                this.addLog('playTime', '停止失败: ' + error.message, 'error');
            }
        },
        
        // 退出当前账号
        async logoutCurrent() {
            if (confirm('确定要退出当前账号吗？')) {
                try {
                    await fetch('/api/logout', { method: 'POST' });
                } catch (e) {}
                window.location.href = '/';
            }
        },
        
        // 监听标签页切换，自动加载数据
        $watch: {
            currentTab(newTab) {
                if (newTab === 'play-record' && this.playRecords.length === 0) {
                    this.loadPlayRecord(this.recordType);
                } else if (newTab === 'playlists' && this.playlists.length === 0) {
                    this.loadPlaylists();
                }
            }
        }
    };
}

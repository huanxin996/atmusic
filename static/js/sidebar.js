/**
 * 侧边栏通用逻辑
 */
function sidebarApp() {
    return {
        // 当前页面标识
        currentPage: window.CURRENT_PAGE || '',
        
        // 用户列表
        users: [],
        
        // 是否有当前登录用户
        hasCurrentUser: false,
        
        // 登录检查
        requireLogin: window.REQUIRE_LOGIN !== false,
        isLoggedIn: false,
        
        // 任务状态
        taskStatus: {
            playCountRunning: false,
            playTimeRunning: false
        },
        
    // WebSocket
    ws: null,
    taskWs: null,
    _wsReconnectTimer: null,
    _wsAttempts: 0,
    _wsIntentionalClose: false,
    _taskWsReconnectTimer: null,
    _taskWsAttempts: 0,
    _taskWsIntentionalClose: false,
        
        // 用户状态刷新定时器
        userRefreshTimer: null,
        
        // 初始化
        async init() {
            await this.loadUsers();
            this.connectWebSocket();
            
            // 启动用户状态定时刷新（每30秒刷新一次，保持状态同步）
            this.startUserRefresh();
            
            // 如果页面需要登录但没有用户，重定向到首页
            if (this.requireLogin && !this.hasCurrentUser) {
                window.location.href = '/?need_login=1';
                return;
            }
            
            // 页面卸载时清理资源
            window.addEventListener('beforeunload', () => { try { this.cleanup(); } catch (e) {} });
            window.addEventListener('unload', () => { try { this.cleanup(); } catch (e) {} });

            // 调用页面特定的初始化
            if (typeof window.pageInit === 'function') {
                window.pageInit(this);
            }
        },
        
        // 启动用户状态定时刷新
        startUserRefresh() {
            // 清除已有的定时器
            if (this.userRefreshTimer) {
                clearInterval(this.userRefreshTimer);
            }
            // 每30秒刷新一次用户列表
            this.userRefreshTimer = setInterval(async () => {
                await this.loadUsers();
                // 如果需要登录但当前用户丢失，重定向到首页
                if (this.requireLogin && !this.hasCurrentUser) {
                    window.location.href = '/?need_login=1';
                }
            }, 30000);
        },
        
        // 加载用户列表
        async loadUsers() {
            try {
                const response = await fetch('/api/users');
                const data = await response.json();
                if (data.code === 200) {
                    this.users = data.users || [];
                    this.hasCurrentUser = this.users.some(u => u.is_current);
                    this.isLoggedIn = this.hasCurrentUser;
                }
            } catch (error) {
                console.error('加载用户列表失败:', error);
            }
        },
        
        // 切换用户
        async switchUser(userId) {
            try {
                const response = await fetch(`/api/users/switch/${userId}`, { method: 'POST' });
                const data = await response.json();
                
                if (data.code === 200) {
                    await this.loadUsers();
                    // 触发页面刷新数据事件
                    window.dispatchEvent(new CustomEvent('user-switched'));
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
                    if (!this.hasCurrentUser) {
                        window.location.href = '/';
                    } else {
                        window.dispatchEvent(new CustomEvent('user-switched'));
                    }
                }
            } catch (error) {
                console.error('删除用户失败:', error);
            }
        },
        
        // 退出当前账号
        async logoutCurrent() {
            const currentUser = this.users.find(u => u.is_current);
            if (currentUser) {
                await this.deleteUser(currentUser.user_id);
            }
        },
        
        // WebSocket连接
        connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

            // 状态 WS（/api/ws/status）管理化连接
            const connectStatusWs = () => {
                const wsUrl = `${protocol}//${window.location.host}/api/ws/status`;
                try {
                    this.ws = new WebSocket(wsUrl);

                    this.ws.onopen = () => { this._wsAttempts = 0; };

                    this.ws.onmessage = (event) => {
                        try {
                            const data = JSON.parse(event.data);
                            if (data.type === 'task_status') {
                                if (data.task === 'play_count') {
                                    this.taskStatus.playCountRunning = data.running;
                                } else if (data.task === 'play_time') {
                                    this.taskStatus.playTimeRunning = data.running;
                                }
                                if (data.play_count_running !== undefined) {
                                    this.taskStatus.playCountRunning = data.play_count_running;
                                }
                                if (data.play_time_running !== undefined) {
                                    this.taskStatus.playTimeRunning = data.play_time_running;
                                }
                            }
                            if (data.type === 'task_status') {
                                window.dispatchEvent(new CustomEvent('ws-message', { detail: data }));
                            }
                        } catch (e) {
                            console.error('WebSocket消息解析失败:', e);
                        }
                    };

                    this.ws.onclose = () => {
                        if (this._wsIntentionalClose) return;
                        const delay = Math.min(30000, 1000 * Math.pow(2, this._wsAttempts));
                        this._wsAttempts += 1;
                        this._wsReconnectTimer = setTimeout(() => connectStatusWs(), delay);
                    };

                    this.ws.onerror = (err) => { console.error('状态WS错误:', err); };
                } catch (err) {
                    console.error('连接状态WS失败:', err);
                    if (!this._wsIntentionalClose) this._wsReconnectTimer = setTimeout(connectStatusWs, 5000);
                }
            };

            // 任务 WS（/api/ws/task）管理化连接 — 侧边栏仅同步状态，无需转发详细日志
            const connectTaskWs = () => {
                const taskWsUrl = `${protocol}//${window.location.host}/api/ws/task`;
                try {
                    this.taskWs = new WebSocket(taskWsUrl);

                    this.taskWs.onopen = () => { this._taskWsAttempts = 0; };

                    this.taskWs.onmessage = (event) => {
                        try {
                            const data = JSON.parse(event.data);
                            if (data.type === 'task_status') {
                                if (data.task === 'play_count') this.taskStatus.playCountRunning = data.running;
                                if (data.task === 'play_time') this.taskStatus.playTimeRunning = data.running;
                                window.dispatchEvent(new CustomEvent('ws-message', { detail: data }));
                            }
                        } catch (err) {
                            console.error('任务WS消息解析失败:', err);
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
                    if (!this._taskWsIntentionalClose) this._taskWsReconnectTimer = setTimeout(connectTaskWs, 5000);
                }
            };

            connectStatusWs();
            connectTaskWs();
        },

        // 清理：在页面卸载时关闭 WS、清除定时器
        cleanup() {
            // 停止用户刷新定时器
            if (this.userRefreshTimer) {
                clearInterval(this.userRefreshTimer);
                this.userRefreshTimer = null;
            }
            // 标记并关闭状态 WS
            this._wsIntentionalClose = true;
            if (this._wsReconnectTimer) { clearTimeout(this._wsReconnectTimer); this._wsReconnectTimer = null; }
            if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
                try { this.ws.close(); } catch (e) { }
            }
            // 标记并关闭任务 WS
            this._taskWsIntentionalClose = true;
            if (this._taskWsReconnectTimer) { clearTimeout(this._taskWsReconnectTimer); this._taskWsReconnectTimer = null; }
            if (this.taskWs && (this.taskWs.readyState === WebSocket.OPEN || this.taskWs.readyState === WebSocket.CONNECTING)) {
                try { this.taskWs.close(); } catch (e) { }
            }
        }
    };
}

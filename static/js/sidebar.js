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
            const wsUrl = `${protocol}//${window.location.host}/api/ws/status`;
            
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'task_status') {
                        // 处理新的task_status格式: {"type": "task_status", "task": "play_count", "running": true}
                        if (data.task === 'play_count') {
                            this.taskStatus.playCountRunning = data.running;
                        } else if (data.task === 'play_time') {
                            this.taskStatus.playTimeRunning = data.running;
                        }
                        // 兼容旧格式
                        if (data.play_count_running !== undefined) {
                            this.taskStatus.playCountRunning = data.play_count_running;
                        }
                        if (data.play_time_running !== undefined) {
                            this.taskStatus.playTimeRunning = data.play_time_running;
                        }
                    }
                    // 转发消息给页面处理
                    window.dispatchEvent(new CustomEvent('ws-message', { detail: data }));
                } catch (e) {
                    console.error('WebSocket消息解析失败:', e);
                }
            };
            
            this.ws.onclose = () => {
                setTimeout(() => this.connectWebSocket(), 5000);
            };
        }
    };
}

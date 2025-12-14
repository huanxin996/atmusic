/**
 * 用户详情页逻辑
 */
function profilePage() {
    return {
        loading: false,
        validating: false,
        refreshingHtml: false,
        cookieValid: true,
        htmlInfoLoaded: false,
        
        // 用户信息
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
            createDays: 0,
            location: ''
        },
        
        // HTML解析的额外信息
        htmlInfo: {
            level: 0,
            listenSongs: 0,
            follows: 0,
            followeds: 0,
            eventCount: 0,
            createDays: 0,
            location: ''
        },
        
        // 页面初始化
        async pageInit() {
            await this.loadUserInfo();
            // 自动加载HTML解析信息
            await this.loadHtmlInfo();
            
            // 监听用户切换事件
            window.addEventListener('user-switched', () => {
                this.htmlInfoLoaded = false;
                this.loadUserInfo();
                this.loadHtmlInfo();
            });
        },
        
        // 加载用户信息（从API）
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
                        createDays: info.create_days || 0,
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
        
        // 从HTML解析加载用户详细信息
        async loadHtmlInfo() {
            if (!this.user.userId) return;
            
            try {
                const response = await fetch('/api/users/current/html-info');
                const data = await response.json();
                
                if (data.code === 200 && data.data) {
                    const info = data.data;
                    this.htmlInfo = {
                        level: info.level || 0,
                        listenSongs: info.listen_songs || 0,
                        follows: info.follows || 0,
                        followeds: info.followeds || 0,
                        eventCount: info.event_count || 0,
                        createDays: info.create_days || 0,
                        location: info.location || ''
                    };
                    
                    // 使用HTML解析的数据更新用户信息（HTML数据通常更准确）
                    if (this.htmlInfo.level > 0) {
                        this.user.level = this.htmlInfo.level;
                    }
                    if (this.htmlInfo.listenSongs > 0) {
                        this.user.listenSongs = this.htmlInfo.listenSongs;
                    }
                    if (this.htmlInfo.follows > 0) {
                        this.user.follows = this.htmlInfo.follows;
                    }
                    if (this.htmlInfo.followeds > 0) {
                        this.user.followeds = this.htmlInfo.followeds;
                    }
                    if (this.htmlInfo.eventCount > 0) {
                        this.user.eventCount = this.htmlInfo.eventCount;
                    }
                    if (this.htmlInfo.createDays > 0) {
                        this.user.createDays = this.htmlInfo.createDays;
                    }
                    if (this.htmlInfo.location) {
                        this.user.location = this.htmlInfo.location;
                    }
                    
                    this.htmlInfoLoaded = true;
                    console.log('HTML解析用户信息加载成功');
                }
            } catch (error) {
                console.error('从HTML解析用户信息失败:', error);
            }
        },
        
        // 刷新HTML解析信息
        async refreshFromHtml() {
            this.refreshingHtml = true;
            try {
                await this.loadHtmlInfo();
                if (this.htmlInfoLoaded) {
                    // 成功提示
                    console.log('用户信息已从网页刷新');
                }
            } catch (error) {
                console.error('刷新用户信息失败:', error);
            } finally {
                this.refreshingHtml = false;
            }
        },
        
        // 验证Cookie
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
        
        // 格式化数字（添加千分位）
        formatNumber(num) {
            if (!num) return '0';
            return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        },
        
        // 获取性别文本
        getGenderText() {
            switch(this.user.gender) {
                case 1: return '男';
                case 2: return '女';
                default: return '未设置';
            }
        },
        
        // 获取VIP文本
        getVipText() {
            if (this.user.vipType === 11) return '黑胶VIP';
            if (this.user.vipType > 0) return 'VIP';
            return '普通用户';
        }
    };
}

// 设置页面初始化函数
window.pageInit = function(app) {
    app.pageInit();
};

/**
 * 用户详情页逻辑
 */
function profilePage() {
    return {
        loading: false,
        validating: false,
        cookieValid: true,
        
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
            createTime: null,
            createDays: 0,
            location: ''
        },
        
        // 页面初始化
        async pageInit() {
            await this.loadUserInfo();
            
            // 监听用户切换事件
            window.addEventListener('user-switched', () => {
                this.loadUserInfo();
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
                        // 将时间戳格式化为 YYYY-MM-DD（支持秒或毫秒）
                        createTime: this.formatDate(info.create_time),
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

        // 将时间戳（秒或毫秒）格式化为 YYYY-MM-DD，空值或无效返回 '-'
        formatDate(ts) {
            if (ts === null || ts === undefined || ts === '' || ts === 0) return '-';
            // 确保是数字
            const n = Number(ts);
            if (!isFinite(n)) return '-';
            // 如果看起来像秒（小于 1e11），则转换为毫秒
            const tsMs = n < 1e11 ? n * 1000 : n;
            const d = new Date(tsMs);
            if (isNaN(d.getTime())) return '-';
            const y = d.getFullYear();
            const m = String(d.getMonth() + 1).padStart(2, '0');
            const day = String(d.getDate()).padStart(2, '0');
            return `${y}-${m}-${day}`;
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

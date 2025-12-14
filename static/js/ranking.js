/**
 * 听歌排行页逻辑
 */
function rankingPage() {
    return {
        loading: false,
        recordType: 1, // 1-最近一周 0-所有时间
        playRecords: [],
        
        // 页面初始化
        async pageInit() {
            await this.loadPlayRecord(1);
            
            // 监听用户切换事件
            window.addEventListener('user-switched', () => {
                this.loadPlayRecord(this.recordType);
            });
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
        }
    };
}

// 设置页面初始化函数
window.pageInit = function(app) {
    app.pageInit();
};

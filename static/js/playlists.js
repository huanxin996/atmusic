/**
 * 歌单页逻辑
 */
function playlistsPage() {
    return {
        loading: false,
        playlists: [],
        
        // 页面初始化
        async pageInit() {
            await this.loadPlaylists();
            
            // 监听用户切换事件
            window.addEventListener('user-switched', () => {
                this.loadPlaylists();
            });
        },
        
        // 加载歌单
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
        }
    };
}

// 设置页面初始化函数
window.pageInit = function(app) {
    app.pageInit();
};

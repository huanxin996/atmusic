/**
 * 登录页面交互逻辑
 */
function loginApp() {
    return {
        // 状态
        tab: 'qr',
        qrKey: '',
        qrImage: '',
        status: 'waiting',
        statusMessage: '请使用网易云音乐APP扫码',
        loading: false,
        cookies: '',
        phone: '',
        password: '',
        countryCode: '86',
        message: '',
        messageType: 'error',
        ws: null,
        wsConnected: false,
        checkInterval: null,
        isLoggedIn: false,

        // 初始化
        async init() {
            this.connectWebSocket();
        },

        // 切换登录方式
        switchTab(newTab) {
            this.tab = newTab;
            if (newTab === 'qr' && !this.qrImage) {
                this.generateQR();
            }
        },

        // 连接WebSocket
        connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            this.ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/login`);
            
            this.ws.onopen = () => {
                this.wsConnected = true;
                this.generateQR();
            };
            
            this.ws.onmessage = (event) => {
                this.handleWebSocketMessage(JSON.parse(event.data));
            };
            
            this.ws.onclose = () => {
                this.wsConnected = false;
                if (!this.isLoggedIn) {
                    setTimeout(() => this.connectWebSocket(), 3000);
                }
            };
            
            this.ws.onerror = () => {
                this.wsConnected = false;
            };
        },

        // 处理WebSocket消息
        handleWebSocketMessage(msg) {
            if (msg.type === 'qr_generated') {
                this.loading = false;
                if (msg.data.success) {
                    this.qrKey = msg.data.qr_key;
                    this.qrImage = msg.data.qr_image;
                    this.status = 'waiting';
                    this.statusMessage = '请使用网易云音乐APP扫码';
                    this.startCheckStatus();
                } else {
                    this.showMessage(msg.data.message || '生成二维码失败', 'error');
                }
            } else if (msg.type === 'qr_status') {
                this.handleQRStatus(msg.data);
            }
        },

        // 处理二维码状态
        handleQRStatus(data) {
            switch (data.code) {
                case 801:
                    this.status = 'waiting';
                    this.statusMessage = '等待扫码...';
                    break;
                case 802:
                    this.status = 'scanned';
                    this.statusMessage = '已扫码，请在手机上确认';
                    break;
                case 803:
                    this.status = 'success';
                    this.statusMessage = '登录成功！';
                    this.isLoggedIn = true;
                    this.stopCheckStatus();
                    this.showMessage('登录成功，正在跳转...', 'success');
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 1500);
                    break;
                case 800:
                    this.status = 'expired';
                    this.statusMessage = '二维码已过期';
                    this.stopCheckStatus();
                    break;
                case 8821:
                    this.status = 'error';
                    this.statusMessage = data.message || '环境异常';
                    this.stopCheckStatus();
                    this.showMessage('请使用Cookie登录', 'error');
                    break;
            }
        },

        // 生成二维码
        generateQR() {
            if (!this.wsConnected) {
                this.showMessage('正在连接服务器...', 'error');
                return;
            }
            this.loading = true;
            this.status = 'waiting';
            this.stopCheckStatus();
            this.ws.send(JSON.stringify({ action: 'generate_qr' }));
        },

        // 开始检查状态
        startCheckStatus() {
            this.stopCheckStatus();
            this.checkInterval = setInterval(() => {
                if (this.isLoggedIn || !this.wsConnected) {
                    this.stopCheckStatus();
                    return;
                }
                if (this.qrKey && this.ws?.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({ action: 'check_qr', qr_key: this.qrKey }));
                }
            }, 2000);
        },

        // 停止检查状态
        stopCheckStatus() {
            if (this.checkInterval) {
                clearInterval(this.checkInterval);
                this.checkInterval = null;
            }
        },

        // 密码登录
        async loginWithPassword() {
            if (!this.phone || !this.password) return;
            this.loading = true;
            try {
                const res = await fetch('/api/auth/password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        phone: this.phone,
                        password: this.password,
                        country_code: this.countryCode
                    })
                });
                if (res.ok) {
                    this.isLoggedIn = true;
                    this.showMessage('登录成功！', 'success');
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 1000);
                } else {
                    const data = await res.json();
                    this.showMessage(data.detail || '登录失败', 'error');
                }
            } catch (e) {
                this.showMessage('网络错误', 'error');
            } finally {
                this.loading = false;
            }
        },

        // Cookie登录
        async loginWithCookie() {
            if (!this.cookies) return;
            this.loading = true;
            try {
                const res = await fetch('/api/auth/cookies', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cookies: this.cookies })
                });
                if (res.ok) {
                    this.isLoggedIn = true;
                    this.showMessage('登录成功！', 'success');
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 1000);
                } else {
                    const data = await res.json();
                    this.showMessage(data.detail || 'Cookie无效', 'error');
                }
            } catch (e) {
                this.showMessage('网络错误', 'error');
            } finally {
                this.loading = false;
            }
        },

        // 显示消息
        showMessage(msg, type = 'error') {
            this.message = msg;
            this.messageType = type;
            setTimeout(() => this.message = '', 3000);
        }
    };
}

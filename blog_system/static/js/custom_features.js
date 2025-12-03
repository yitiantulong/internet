/**
 * custom_features.js
 * 包含：网络性能面板、宝可梦互动、文章加密解锁
 */

document.addEventListener("DOMContentLoaded", () => {
    initNetworkMonitor();
    initPokemon();
    initUnlockForm();
});

// ==========================================
// 1. 网络性能监测面板 (Network Monitor)
// ==========================================
function initNetworkMonitor() {
    const monitorEl = document.getElementById('network-monitor');
    if (!monitorEl) return;

    const rttEl = document.getElementById('net-rtt');
    const throughputEl = document.getElementById('net-throughput');

    async function fetchMetrics() {
        const start = performance.now();
        try {
            // 请求后端性能接口 (复用后端已有的记录功能)
            const response = await fetch('/api/performance/metrics?limit=1');
            const end = performance.now();
            
            // 计算 RTT (客户端视角)
            const rtt = (end - start).toFixed(0);
            
            // 更新 UI
            if (rttEl) rttEl.innerText = `${rtt} ms`;
            
            // 简单模拟吞吐量 (或者从后端 response.json() 获取真实数据)
            // 这里为了演示效果，显示本次请求的数据大小
            const size = response.headers.get("content-length") || 500;
            if (throughputEl) throughputEl.innerText = `${size} B/req`;

        } catch (e) {
            console.error("Monitor Error:", e);
            if (rttEl) rttEl.innerText = "Offline";
        }
    }

    // 每 2 秒刷新一次
    setInterval(fetchMetrics, 2000);
}

// ==========================================
// 2. 宝可梦互动组件 (Pokemon Interaction)
// ==========================================
function initPokemon() {
    const container = document.getElementById('pokemon-pet-container');
    const msgBox = document.getElementById('poke-msg');
    const svg = container.querySelector('svg');

    if (!container) return;

    container.addEventListener('click', async () => {
        // 1. 触发前端动画
        container.classList.add('poke-jump');
        svg.classList.add('poke-blush');
        
        // 动画结束后移除类，方便下次触发
        setTimeout(() => {
            container.classList.remove('poke-jump');
            svg.classList.remove('poke-blush');
        }, 500);

        try {
            // 2. 调用后端接口记录互动
            const res = await fetch('/api/pokemon/interact', { method: 'POST' });
            const data = await res.json();

            if (data.success) {
                msgBox.innerText = `Pika! 已互动 ${data.stats.count} 次`;
                msgBox.style.display = 'block';
                setTimeout(() => msgBox.style.display = 'none', 3000);
            }
        } catch (e) {
            console.error("Pokemon Interact Error:", e);
            msgBox.innerText = "Pika... (网络错误)";
            msgBox.style.display = 'block';
        }
    });
}

// ==========================================
// 3. 文章解锁逻辑 (Encrypted Post Unlock)
// ==========================================
function initUnlockForm() {
    // 监听所有带有 'post-unlock-form' 类的表单提交
    document.addEventListener('submit', async (e) => {
        if (e.target && e.target.classList.contains('post-unlock-form')) {
            e.preventDefault();
            const form = e.target;
            const postId = form.dataset.postId;
            const passwordInput = form.querySelector('input[name="password"]');
            const btn = form.querySelector('button');
            const errorMsg = form.querySelector('.unlock-error');

            const password = passwordInput.value;
            
            // UI Loading 状态
            const originalText = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 解锁中...';
            btn.disabled = true;

            try {
                const res = await fetch(`/api/posts/${postId}/unlock`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: password })
                });
                const data = await res.json();

                if (data.success) {
                    // 解锁成功，刷新页面 (后端 Cookie 已设置，刷新即可看到内容)
                    window.location.reload();
                } else {
                    // 显示错误信息
                    if (errorMsg) {
                        errorMsg.innerText = data.message || "密码错误";
                        errorMsg.style.display = 'block';
                    } else {
                        alert(data.message || "密码错误");
                    }
                }
            } catch (err) {
                alert("网络错误，请重试");
            } finally {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        }
    });
}
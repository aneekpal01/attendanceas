// ========================================================
// LIVE ATTENDANCE CONTROLLER
// ========================================================
// The teacher screen polls the server every 2 seconds.
// This is intentionally simpler than WebSockets and is
// more than enough for a hackathon classroom demo.
// ========================================================

const liveShell = document.querySelector('.live-shell');

if (liveShell) {
    const sessionId = liveShell.dataset.sessionId;
    const expiresAt = new Date(liveShell.dataset.expires).getTime();

    const presentEl = document.getElementById('presentCount');
    const totalEl = document.getElementById('totalCount');
    const percentageEl = document.getElementById('percentage');
    const progressEl = document.getElementById('progressBar');
    const countdownEl = document.getElementById('countdown');
    const statusEl = document.getElementById('liveStatus');

    function formatTime(seconds) {
        const safe = Math.max(0, seconds);
        const minutes = Math.floor(safe / 60).toString().padStart(2, '0');
        const secs = Math.floor(safe % 60).toString().padStart(2, '0');
        return `${minutes}:${secs}`;
    }

    function updateCountdown() {
        const remaining = Math.max(0, Math.floor((expiresAt - Date.now()) / 1000));
        countdownEl.textContent = formatTime(remaining);

        if (remaining <= 0) {
            statusEl.className = 'badge danger';
            statusEl.innerHTML = '● SESSION EXPIRED';
        }
    }

    async function refreshStats() {
        try {
            const response = await fetch(`/api/session/${sessionId}/stats`, {
                cache: 'no-store'
            });
            const data = await response.json();

            // Replace the static values with fresh database values.
            presentEl.textContent = data.present;
            totalEl.textContent = data.total;
            percentageEl.textContent = `${data.percentage}%`;
            progressEl.style.width = `${Math.min(100, data.percentage)}%`;

            if (data.active) {
                statusEl.className = 'badge success';
                statusEl.innerHTML = '<span class="live-dot"></span> SESSION ACTIVE';
            }
        } catch (error) {
            // The UI stays usable even if a temporary request fails.
            console.warn('Live stats refresh failed:', error);
        }
    }

    updateCountdown();
    refreshStats();

    // Countdown updates every second.
    setInterval(updateCountdown, 1000);

    // Attendance count updates every two seconds.
    setInterval(refreshStats, 2000);
}

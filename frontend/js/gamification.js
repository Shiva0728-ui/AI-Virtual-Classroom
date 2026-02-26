/* ═══════════════════════════════════════════════════════════════
   Gamification Module - XP, Badges, Achievements
   ═══════════════════════════════════════════════════════════════ */

const Gamification = {
    async load() {
        try {
            const [stats, badges] = await Promise.all([
                api('/api/gamification/stats'),
                api('/api/gamification/all-badges'),
            ]);
            this.renderStats(stats);
            this.renderBadges(badges);
        } catch(err) {
            App.toast('Failed to load achievements', 'error');
        }
    },

    renderStats(stats) {
        // Level
        document.getElementById('ach-level').textContent = stats.level;
        document.getElementById('ach-xp-total').textContent = `${stats.xp_total} XP`;
        document.getElementById('ach-xp-progress').textContent = stats.xp_progress;
        document.getElementById('ach-xp-next').textContent = '200';
        
        // XP Bar
        const percent = (stats.xp_progress / 200) * 100;
        document.getElementById('ach-xp-bar').style.width = `${Math.min(percent, 100)}%`;
        
        // Circle
        const circle = document.getElementById('xp-circle-fill');
        if (circle) {
            const circumference = 2 * Math.PI * 45; // r=45
            const offset = circumference - (percent / 100) * circumference;
            circle.style.strokeDashoffset = Math.max(offset, 0);
        }
        
        // Stats
        document.getElementById('ach-streak').textContent = stats.streak_days;
        document.getElementById('ach-lessons').textContent = stats.lessons_completed;
        document.getElementById('ach-quizzes').textContent = stats.quizzes_passed;
    },

    renderBadges(badges) {
        const grid = document.getElementById('badges-grid');
        grid.innerHTML = badges.map(b => `
            <div class="badge-card ${b.earned ? 'earned' : 'locked'}">
                <div class="badge-icon">${b.icon}</div>
                <div class="badge-name">${b.name}</div>
                <div class="badge-desc">${b.description}</div>
                ${b.earned ? '<div style="color: var(--success); font-size: 0.7rem; margin-top: 6px;">✅ Earned</div>' : 
                `<div style="font-size: 0.65rem; color: var(--text-muted); margin-top: 6px;">🔒 ${b.criteria_type}: ${b.criteria_value}</div>`}
            </div>
        `).join('');
    }
};


/* ═══════════════════════════════════════════════════════════════
   Leaderboard Module
   ═══════════════════════════════════════════════════════════════ */

const Leaderboard = {
    async load() {
        try {
            const data = await api('/api/leaderboard');
            this.render(data);
        } catch(err) {
            App.toast('Failed to load leaderboard', 'error');
        }
    },

    render(data) {
        const table = document.getElementById('leaderboard-table');
        
        if (data.length === 0) {
            table.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--text-muted);">
                    <h3>🏆 No one on the leaderboard yet!</h3>
                    <p>Start learning to be the first!</p>
                </div>
            `;
            return;
        }

        table.innerHTML = data.map(user => {
            let rankClass = '';
            let rankDisplay = user.rank;
            if (user.rank === 1) { rankClass = 'gold'; rankDisplay = '🥇'; }
            else if (user.rank === 2) { rankClass = 'silver'; rankDisplay = '🥈'; }
            else if (user.rank === 3) { rankClass = 'bronze'; rankDisplay = '🥉'; }

            return `
                <div class="lb-row ${user.is_me ? 'is-me' : ''}">
                    <div class="lb-rank ${rankClass}">${rankDisplay}</div>
                    <div class="lb-avatar">${user.avatar}</div>
                    <div class="lb-user">
                        <div class="lb-username">${user.username} ${user.is_me ? '(You)' : ''}</div>
                        <div class="lb-fullname">${user.full_name || ''}</div>
                    </div>
                    <div class="lb-stats">
                        <span class="lb-xp">⭐ ${user.xp_total} XP</span>
                        <span class="lb-level">🏆 Lv.${user.level}</span>
                        <span class="lb-streak">🔥 ${user.streak_days}d</span>
                    </div>
                </div>
            `;
        }).join('');
    }
};

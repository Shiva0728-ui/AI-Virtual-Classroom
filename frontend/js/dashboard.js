/* ═══════════════════════════════════════════════════════════════
   Dashboard, Teacher Dashboard & Parent Report
   ═══════════════════════════════════════════════════════════════ */

const Dashboard = {
    async load() {
        try {
            const [overview, recommendations, novaStatus] = await Promise.all([
                api('/api/progress/overview'),
                api('/api/recommendations'),
                api('/api/nova/status')
            ]);
            this.render(overview, recommendations, novaStatus);
        } catch(err) {
            console.error('Dashboard load error:', err);
        }
    },

    render(overview, recommendations, novaStatus) {
        // Greeting
        const hour = new Date().getHours();
        let greeting;
        if (hour < 12) greeting = 'Good morning';
        else if (hour < 17) greeting = 'Good afternoon';
        else greeting = 'Good evening';
        
        const name = AppState.user?.full_name || AppState.user?.username || 'Student';
        document.getElementById('dashboard-greeting').textContent = `${greeting}, ${name}! 👋`;
        
        // NOVA Insight
        if (novaStatus) {
            const insightEl = document.getElementById('dash-nova-insight');
            const avatarEl = document.getElementById('dash-nova-avatar');
            if (insightEl) insightEl.textContent = novaStatus.message;
            if (avatarEl) avatarEl.className = `nova-avatar-sm mood-${novaStatus.mood}`;
        }

        // Stats
        document.getElementById('dash-xp').textContent = overview.xp_total || 0;
        document.getElementById('dash-level').textContent = overview.level || 1;
        document.getElementById('dash-lessons').textContent = `${overview.completed_lessons || 0}/${overview.total_lessons || 0}`;
        document.getElementById('dash-progress').textContent = `${overview.overall_progress || 0}%`;

        // Streak
        const streakEl = document.getElementById('dashboard-streak');
        streakEl.querySelector('span').textContent = overview.streak || 0;

        // Course Progress
        const progressList = document.getElementById('dash-course-progress');
        if (overview.courses && overview.courses.length > 0) {
            progressList.innerHTML = overview.courses.map(c => `
                <div class="course-progress-item">
                    <div class="course-progress-icon">${c.icon}</div>
                    <div class="course-progress-info">
                        <div class="course-progress-name">${c.title}</div>
                        <div class="course-progress-stats">${c.completed}/${c.total} lessons</div>
                        <div class="progress-bar" style="margin-top: 4px;">
                            <div class="progress-fill" style="width: ${c.progress}%"></div>
                        </div>
                    </div>
                    <div class="course-progress-percent">${c.progress}%</div>
                </div>
            `).join('');
        } else {
            progressList.innerHTML = '<p class="text-muted" style="padding: 16px 0;">Start a course to see progress here!</p>';
        }

        // Recommendations
        const recList = document.getElementById('dash-recommendations');
        if (recommendations && recommendations.length > 0) {
            recList.innerHTML = recommendations.map(r => `
                <div class="recommendation-item" onclick="Courses.openLesson(${r.lesson_id})">
                    <div class="rec-icon">${r.course_icon || '📘'}</div>
                    <div class="rec-info">
                        <div class="rec-title">${r.lesson_title}</div>
                        <div class="rec-reason">${r.reason}</div>
                    </div>
                    <i class="fas fa-arrow-right" style="color: var(--accent-primary);"></i>
                </div>
            `).join('');
        } else {
            recList.innerHTML = '<p class="text-muted" style="padding: 16px 0;">Complete lessons to get recommendations!</p>';
        }

        // Recent Activity
        const recentList = document.getElementById('dash-recent');
        if (overview.recent_lessons && overview.recent_lessons.length > 0) {
            recentList.innerHTML = overview.recent_lessons.map(r => `
                <div class="recent-item">
                    <div>
                        <div class="recent-title">${r.title}</div>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">Understanding: ${Math.round(r.understanding)}%</div>
                    </div>
                    <span class="status-badge status-${r.status}">${r.status.replace('_', ' ')}</span>
                </div>
            `).join('');
        } else {
            recentList.innerHTML = '<p class="text-muted" style="padding: 16px 0;">No recent activity. Start learning!</p>';
        }
    }
};


/* ═══════════════════════════════════════════════════════════════
   Teacher Dashboard
   ═══════════════════════════════════════════════════════════════ */

const TeacherDashboard = {
    async load() {
        try {
            const data = await api('/api/dashboard/teacher');
            this.render(data);
        } catch(err) {
            App.toast('Failed to load teacher dashboard', 'error');
        }
    },

    render(data) {
        document.getElementById('td-students').textContent = data.total_students;
        document.getElementById('td-lessons').textContent = data.total_lessons_completed;
        document.getElementById('td-understanding').textContent = `${data.avg_understanding}%`;

        const table = document.getElementById('td-student-table');
        if (data.students.length === 0) {
            table.innerHTML = '<p class="text-muted" style="padding: 20px;">No students registered yet.</p>';
            return;
        }

        table.innerHTML = `
            <div class="st-row">
                <div>Avatar</div>
                <div>Student</div>
                <div>XP</div>
                <div>Level</div>
                <div>Streak</div>
                <div>Lessons</div>
                <div>Avg Score</div>
                <div>Homework</div>
            </div>
            ${data.students.map(s => `
                <div class="st-row">
                    <div>${s.avatar}</div>
                    <div>
                        <div style="font-weight: 600;">${s.full_name || s.username}</div>
                        <div style="font-size: 0.7rem; color: var(--text-muted);">@${s.username}</div>
                    </div>
                    <div style="color: var(--xp-color); font-weight: 700;">${s.xp}</div>
                    <div>${s.level}</div>
                    <div style="color: var(--streak-color);">${s.streak}🔥</div>
                    <div>${s.lessons_completed}</div>
                    <div>${s.avg_understanding}%</div>
                    <div>${s.homework_completed} (${s.homework_avg_grade}%)</div>
                </div>
            `).join('')}
        `;
    }
};


/* ═══════════════════════════════════════════════════════════════
   Parent Report
   ═══════════════════════════════════════════════════════════════ */

const ParentReport = {
    async load() {
        try {
            const data = await api('/api/dashboard/parent');
            this.render(data);
        } catch(err) {
            App.toast('Failed to load parent report', 'error');
        }
    },

    render(data) {
        const content = document.getElementById('parent-report-content');

        if (!data.children || data.children.length === 0) {
            content.innerHTML = `
                <div class="card" style="text-align: center; padding: 40px;">
                    <h3>👨‍👩‍👧 No children linked yet</h3>
                    <p class="text-muted">Your child's progress will appear here once they're linked to your account.</p>
                </div>
            `;
            return;
        }

        content.innerHTML = data.children.map(child => `
            <div class="parent-child-card">
                <div class="parent-child-header">
                    <div class="parent-child-avatar">${child.child.avatar}</div>
                    <div>
                        <h3>${child.child.full_name || child.child.username}</h3>
                        <p class="text-muted">Level ${child.level} • ${child.xp} XP • ${child.streak}🔥 day streak</p>
                    </div>
                </div>

                <h4 style="margin-bottom: 12px;">📊 Course Progress</h4>
                <div class="parent-course-grid">
                    ${child.courses.map(c => `
                        <div class="parent-course-card">
                            <h4>${c.icon} ${c.course}</h4>
                            <div class="progress-bar" style="margin: 6px 0;">
                                <div class="progress-fill" style="width: ${c.progress}%"></div>
                            </div>
                            <div style="font-size: 0.75rem; color: var(--text-muted);">${c.completed}/${c.total_lessons} lessons (${c.progress}%)</div>
                        </div>
                    `).join('')}
                </div>

                <h4 style="margin-bottom: 12px;">🧠 Quiz Performance</h4>
                <div style="display: flex; gap: 24px; font-size: 0.9rem; margin-bottom: 16px;">
                    <span>Total: ${child.quiz_stats.total}</span>
                    <span style="color: var(--success);">Correct: ${child.quiz_stats.correct}</span>
                    <span style="color: var(--accent-secondary);">Accuracy: ${child.quiz_stats.accuracy}%</span>
                </div>

                <h4 style="margin-bottom: 12px;">📝 Recent Activity</h4>
                ${child.recent_activity.length > 0 ? child.recent_activity.map(a => `
                    <div class="recent-item">
                        <div>
                            <div class="recent-title">${a.lesson}</div>
                            <div style="font-size: 0.7rem; color: var(--text-muted);">${new Date(a.date).toLocaleDateString()}</div>
                        </div>
                        <span class="status-badge status-${a.status}">${a.status.replace('_', ' ')}</span>
                    </div>
                `).join('') : '<p class="text-muted">No recent activity</p>'}
            </div>
        `).join('');
    }
};

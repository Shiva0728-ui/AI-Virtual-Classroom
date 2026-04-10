/* ═══════════════════════════════════════════════════════════════
   AI Virtual Classroom - Main App Controller
   Handles routing, state, and API communication
   ═══════════════════════════════════════════════════════════════ */

const API_BASE = '';  // Same origin

// ─── State ────────────────────────────────────────────────────
const AppState = {
    token: localStorage.getItem('ai_classroom_token') || null,
    user: JSON.parse(localStorage.getItem('ai_classroom_user') || 'null'),
    currentPage: 'dashboard',
    currentCourse: null,
    currentLesson: null,
};

// ─── API Helper ───────────────────────────────────────────────
async function api(endpoint, options = {}, timeoutMs = 60000) {
    const headers = {
        'Content-Type': 'application/json',
        ...(AppState.token ? { 'Authorization': `Bearer ${AppState.token}` } : {}),
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: { ...headers, ...options.headers },
            body: options.body ? JSON.stringify(options.body) : undefined,
            signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (response.status === 401) {
            Auth.logout();
            throw new Error('Session expired');
        }

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'API error');
        }

        return data;
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw new Error('Request timed out. The AI is taking too long — please try again.');
        }
        if (error.message !== 'Session expired') {
            console.error('API Error:', error);
        }
        throw error;
    }
}

// ─── App Controller ──────────────────────────────────────────
const App = {
    init() {
        // Configure marked.js for markdown rendering
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                highlight: function(code, lang) {
                    if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
                        return hljs.highlight(code, { language: lang }).value;
                    }
                    return code;
                },
                breaks: true,
            });
        }

        // Check if logged in
        if (AppState.token && AppState.user) {
            this.showMainApp();
        } else {
            this.showAuthPage();
        }
    },

    showAuthPage() {
        document.getElementById('auth-page').classList.add('active');
        document.getElementById('main-app').classList.remove('active');
    },

    showMainApp() {
        document.getElementById('auth-page').classList.remove('active');
        document.getElementById('main-app').classList.add('active');
        
        this.updateSidebar();
        
        // Initialize NOVA AI Teacher
        if (typeof NovaAI !== 'undefined') {
            NovaAI.init();
        }
        
        this.navigate('dashboard');
    },

    updateSidebar() {
        if (!AppState.user) return;
        
        document.getElementById('sidebar-avatar').textContent = AppState.user.avatar || '🧑‍🎓';
        document.getElementById('sidebar-username').textContent = AppState.user.full_name || AppState.user.username;
        
        // Show/hide role-specific nav items
        const role = AppState.user.role;
        document.querySelectorAll('.teacher-only').forEach(el => {
            el.style.display = (role === 'teacher') ? 'flex' : 'none';
        });
        document.querySelectorAll('.parent-only').forEach(el => {
            el.style.display = (role === 'parent') ? 'flex' : 'none';
        });

        // Load XP
        this.updateXPDisplay();
    },

    async updateXPDisplay() {
        try {
            const stats = await api('/api/gamification/stats');
            document.getElementById('sidebar-level').textContent = `Level ${stats.level}`;
            document.getElementById('sidebar-xp').textContent = stats.xp_total;
            const percent = stats.xp_for_next_level > 0 ? (stats.xp_progress / 200) * 100 : 0;
            document.getElementById('sidebar-xp-bar').style.width = `${Math.min(percent, 100)}%`;
        } catch(e) {}
    },

    navigate(page) {
        AppState.currentPage = page;
        
        // Close mobile sidebar on navigate
        this.closeSidebar();
        
        // Update active nav
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === page);
        });
        
        // Show active page
        document.querySelectorAll('.content-page').forEach(p => {
            p.classList.toggle('active', p.id === `page-${page}`);
        });
        
        // Trigger ambient JARVIS voice if enabled
        if (typeof Voice !== 'undefined') {
            Voice.ambientNarration(page);
        }
        
        // Load page data
        switch(page) {
            case 'dashboard': Dashboard.load(); break;
            case 'courses': Courses.load(); break;
            case 'create-course': break;  // Static page, no data to load
            case 'visual-lab': break;  // Visual Lab - static page
            case 'quiz': Quiz.loadSelection(); break;
            case 'achievements': Gamification.load(); break;
            case 'leaderboard': Leaderboard.load(); break;
            case 'homework': HomeworkPage.load(); break;
            case 'teacher-dashboard': TeacherDashboard.load(); break;
            case 'parent-report': ParentReport.load(); break;
            case 'profile': Profile.load(); break;
            case 'rl-dashboard': RLDashboard.loadStats(); break;
        }
    },

    toggleSidebar() {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebar-overlay');
        if (window.innerWidth <= 768) {
            sidebar.classList.toggle('mobile-open');
            if (overlay) overlay.classList.toggle('active', sidebar.classList.contains('mobile-open'));
        } else {
            sidebar.classList.toggle('collapsed');
        }
    },

    closeSidebar() {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebar-overlay');
        sidebar.classList.remove('mobile-open');
        if (overlay) overlay.classList.remove('active');
    },

    loading(show) {
        document.getElementById('loading-overlay').classList.toggle('hidden', !show);
    },

    toast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const icons = { success: '✅', error: '❌', info: 'ℹ️', xp: '⭐' };
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span> ${message}`;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    },

    renderMarkdown(text) {
        if (typeof marked !== 'undefined') {
            const html = marked.parse(text || '');
            return html;
        }
        return text.replace(/\n/g, '<br>');
    },
};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => App.init());

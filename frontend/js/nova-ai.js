/* ═══════════════════════════════════════════════════════════════
   NOVA — Neural Oriented Virtual Assistant
   Full AI Teacher Panel: contextual awareness, conversational
   teaching, proactive insights, holographic avatar
   ═══════════════════════════════════════════════════════════════ */

const NovaAI = {
    initialized: false,
    updateInterval: null,
    isOpen: false,
    chatHistory: [],
    currentMood: 'neutral',

    init() {
        if (!AppState.token) return;

        if (!this.initialized) {
            this.renderPanel();
            this.attachEvents();
            this.initialized = true;
        }

        this.fetchStatus();

        // Auto-refresh status every 3 minutes
        if (this.updateInterval) clearInterval(this.updateInterval);
        this.updateInterval = setInterval(() => this.fetchStatus(), 180000);
    },

    renderPanel() {
        if (document.getElementById('nova-panel')) return;

        const panelHTML = `
            <div id="nova-panel" class="nova-panel collapsed">
                <!-- Toggle Button -->
                <button class="nova-toggle" id="nova-toggle" onclick="NovaAI.toggle()" title="Talk to NOVA">
                    <div class="nova-toggle-avatar">
                        <div class="nova-core"></div>
                        <div class="nova-ring nova-ring-1"></div>
                        <div class="nova-ring nova-ring-2"></div>
                        <div class="nova-ring nova-ring-3"></div>
                    </div>
                    <span class="nova-toggle-label">NOVA</span>
                    <span class="nova-notification-dot" id="nova-dot"></span>
                </button>

                <!-- Expanded Panel -->
                <div class="nova-body" id="nova-body">
                    <div class="nova-header">
                        <div class="nova-header-left">
                            <div class="nova-avatar-lg" id="nova-avatar-main">
                                <div class="nova-core"></div>
                                <div class="nova-ring nova-ring-1"></div>
                                <div class="nova-ring nova-ring-2"></div>
                                <div class="nova-ring nova-ring-3"></div>
                            </div>
                            <div class="nova-header-info">
                                <h3>N.O.V.A.</h3>
                                <span class="nova-subtitle" id="nova-mood-text">Neural Oriented Virtual Assistant</span>
                            </div>
                        </div>
                        <button class="nova-close" onclick="NovaAI.toggle()">
                            <i class="fas fa-chevron-right"></i>
                        </button>
                    </div>

                    <!-- Status Card -->
                    <div class="nova-status-card" id="nova-status-card">
                        <p class="nova-status-message" id="nova-status-msg">Initializing systems...</p>
                    </div>

                    <!-- Suggestions -->
                    <div class="nova-suggestions" id="nova-suggestions"></div>

                    <!-- Chat Area -->
                    <div class="nova-chat" id="nova-chat">
                        <div class="nova-chat-messages" id="nova-chat-messages"></div>
                    </div>

                    <!-- Input -->
                    <div class="nova-input-area">
                        <input type="text" id="nova-input" class="nova-input" 
                               placeholder="Ask NOVA anything..."
                               onkeydown="if(event.key==='Enter')NovaAI.sendMessage()">
                        <button class="nova-send" onclick="NovaAI.sendMessage()" id="nova-send-btn">
                            <i class="fas fa-paper-plane"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;

        const loadingOverlay = document.getElementById('loading-overlay');
        if (loadingOverlay) {
            loadingOverlay.insertAdjacentHTML('beforebegin', panelHTML);
        } else {
            document.body.insertAdjacentHTML('beforeend', panelHTML);
        }
    },

    attachEvents() {
        // Close on Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) this.toggle();
        });
    },

    toggle() {
        const panel = document.getElementById('nova-panel');
        if (!panel) return;

        this.isOpen = !this.isOpen;
        panel.classList.toggle('collapsed', !this.isOpen);
        panel.classList.toggle('expanded', this.isOpen);

        // Hide notification dot when opened
        if (this.isOpen) {
            document.getElementById('nova-dot')?.classList.remove('active');
            document.getElementById('nova-input')?.focus();
        }
    },

    async fetchStatus() {
        if (!AppState.token) return;

        try {
            const data = await api('/api/nova/status');
            this.updateStatus(data);
        } catch (e) {
            console.error('NOVA status fetch failed:', e);
            this.updateStatus({
                mood: 'neutral',
                message: 'Systems online. How can I help you learn today?',
                suggestions: []
            });
        }
    },

    updateStatus(data) {
        // Update mood
        this.currentMood = data.mood || 'neutral';
        const avatar = document.getElementById('nova-avatar-main');
        if (avatar) {
            avatar.className = `nova-avatar-lg mood-${this.currentMood}`;
        }

        const moodText = document.getElementById('nova-mood-text');
        if (moodText) {
            const moodLabels = {
                neutral: 'Ready to assist',
                encouraging: 'Keeping you motivated',
                happy: 'Celebrating your progress',
                thinking: 'Analyzing your journey',
                suggestive: 'Has a suggestion for you',
                helping: 'Here to help',
                teaching: 'Teaching mode active',
                celebrating: 'Celebrating with you!',
                speaking: 'In conversation',
                analytical: 'Reviewing your data',
                confused: 'Processing...'
            };
            moodText.textContent = moodLabels[this.currentMood] || 'Neural Oriented Virtual Assistant';
        }

        // Update status message
        const msgEl = document.getElementById('nova-status-msg');
        if (msgEl) {
            msgEl.style.opacity = '0';
            setTimeout(() => {
                msgEl.textContent = data.message;
                msgEl.style.opacity = '1';
            }, 200);
        }

        // Render suggestions
        const sugEl = document.getElementById('nova-suggestions');
        if (sugEl && data.suggestions && data.suggestions.length > 0) {
            sugEl.innerHTML = data.suggestions.map(s => `
                <div class="nova-suggestion" onclick="NovaAI.handleAction('${s.action}')">
                    <span class="nova-suggestion-icon">${s.icon || '💡'}</span>
                    <div class="nova-suggestion-text">
                        <strong>${s.title}</strong>
                        <small>${s.message}</small>
                    </div>
                    <i class="fas fa-chevron-right"></i>
                </div>
            `).join('');
        } else if (sugEl) {
            sugEl.innerHTML = '';
        }

        // Show notification if panel is closed
        if (!this.isOpen && data.suggestions && data.suggestions.length > 0) {
            document.getElementById('nova-dot')?.classList.add('active');
        }
    },

    async sendMessage() {
        const input = document.getElementById('nova-input');
        const message = input.value.trim();
        if (!message) return;

        input.value = '';

        // Show user message
        this.addChatMessage('user', message);

        // Show typing indicator
        this.showTyping();

        // Detect screen context
        const context = this.getScreenContext();

        try {
            const data = await api('/api/nova/ask', {
                method: 'POST',
                body: { question: message, screen_context: context }
            });

            this.removeTyping();
            this.addChatMessage('nova', data.response);

            // Update mood
            if (data.mood) {
                this.currentMood = data.mood;
                const avatar = document.getElementById('nova-avatar-main');
                if (avatar) avatar.className = `nova-avatar-lg mood-${data.mood}`;
            }

        } catch (e) {
            this.removeTyping();
            this.addChatMessage('nova', "I had trouble processing that. Please try again! 🤔");
        }
    },

    addChatMessage(role, content) {
        const container = document.getElementById('nova-chat-messages');
        if (!container) return;

        const div = document.createElement('div');
        div.className = `nova-msg nova-msg-${role}`;

        if (role === 'nova') {
            div.innerHTML = `
                <div class="nova-msg-avatar">
                    <div class="nova-core-sm"></div>
                </div>
                <div class="nova-msg-bubble">${this.formatMessage(content)}</div>
            `;
        } else {
            div.innerHTML = `
                <div class="nova-msg-bubble">${this.escapeHtml(content)}</div>
                <div class="nova-msg-avatar-user">${AppState.user?.avatar || '🧑‍🎓'}</div>
            `;
        }

        container.appendChild(div);

        // Animate in
        requestAnimationFrame(() => div.classList.add('visible'));

        // Scroll to bottom
        container.scrollTop = container.scrollHeight;

        this.chatHistory.push({ role, content });
    },

    formatMessage(text) {
        // Simple markdown-like formatting
        let html = this.escapeHtml(text);
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/`(.*?)`/g, '<code>$1</code>');
        html = html.replace(/\n/g, '<br>');
        return html;
    },

    showTyping() {
        const container = document.getElementById('nova-chat-messages');
        if (!container) return;

        const div = document.createElement('div');
        div.className = 'nova-msg nova-msg-nova nova-typing-msg';
        div.id = 'nova-typing';
        div.innerHTML = `
            <div class="nova-msg-avatar">
                <div class="nova-core-sm thinking"></div>
            </div>
            <div class="nova-msg-bubble nova-typing-bubble">
                <div class="nova-typing-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        container.appendChild(div);
        requestAnimationFrame(() => div.classList.add('visible'));
        container.scrollTop = container.scrollHeight;
    },

    removeTyping() {
        const el = document.getElementById('nova-typing');
        if (el) el.remove();
    },

    getScreenContext() {
        const page = AppState.currentPage || 'dashboard';
        let context = `User is on the ${page} page.`;

        if (page === 'classroom') {
            const title = document.getElementById('classroom-title')?.textContent;
            if (title && title !== 'Virtual Classroom') {
                context += ` Currently studying: "${title}".`;
            }
        } else if (page === 'courses') {
            context += ' Browsing available courses.';
        } else if (page === 'quiz') {
            context += ' Taking a quiz.';
        } else if (page === 'homework') {
            context += ' Viewing homework assignments.';
        } else if (page === 'rl-dashboard') {
            context += ' Viewing the Reinforcement Learning analytics dashboard.';
        } else if (page === 'achievements') {
            context += ' Viewing achievements and badges.';
        }

        return context;
    },

    handleAction(action) {
        if (action.startsWith('/')) {
            const parts = action.split('/');
            const page = parts[1];

            if (page === 'classroom' && parts.length > 3) {
                Classroom.startLesson(parseInt(parts[3]));
            } else {
                App.navigate(page);
            }
        }
        // Close panel on mobile
        if (window.innerWidth < 768) this.toggle();
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    reset() {
        if (this.updateInterval) clearInterval(this.updateInterval);
        this.initialized = false;
        this.chatHistory = [];
        const panel = document.getElementById('nova-panel');
        if (panel) panel.remove();
    }
};

window.NovaAI = NovaAI;

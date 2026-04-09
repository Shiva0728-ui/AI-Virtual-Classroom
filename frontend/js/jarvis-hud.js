/* ═══════════════════════════════════════════════════════════════
   JARVIS Smart HUD Overlay
   Handles ambient intelligence, proactive suggestions, and status
   ═══════════════════════════════════════════════════════════════ */

const JarvisHUD = {
    initialized: false,
    updateInterval: null,
    isOpen: false,

    init() {
        console.log("JarvisHUD init called");
        if (!AppState.token) {
            console.log("JarvisHUD init aborted: no token");
            return;
        }
        
        if (!this.initialized) {
            console.log("JarvisHUD rendering HUD");
            this.renderHUD();
            this.attachEvents();
            this.initialized = true;
        }
        
        this.fetchStatus();
        
        // Auto-refresh JARVIS status every 5 minutes
        if (this.updateInterval) clearInterval(this.updateInterval);
        this.updateInterval = setInterval(() => this.fetchStatus(), 300000);
    },

    renderHUD() {
        // Create HUD container if it doesn't exist
        if (!document.getElementById('jarvis-hud')) {
            const hudHTML = `
                <div id="jarvis-hud" class="jarvis-hud closed">
                    <div class="jarvis-bar" onclick="JarvisHUD.togglePanel()">
                        <div class="jarvis-avatar" id="jarvis-avatar">
                            <div class="jarvis-core"></div>
                            <div class="jarvis-ring ring-1"></div>
                            <div class="jarvis-ring ring-2"></div>
                        </div>
                        <div class="jarvis-status">
                            <span class="jarvis-label">J.A.R.V.I.S.</span>
                            <span class="jarvis-message" id="jarvis-message">Systems nominal.</span>
                        </div>
                        <div class="jarvis-indicator">
                            <i class="fas fa-chevron-up" id="jarvis-chevron"></i>
                        </div>
                    </div>
                    
                    <div class="jarvis-panel" id="jarvis-panel">
                        <div class="jarvis-panel-header">
                            <h3>Smart Suggestions</h3>
                            <button class="icon-btn" onclick="JarvisHUD.togglePanel()"><i class="fas fa-times"></i></button>
                        </div>
                        <div class="jarvis-suggestions" id="jarvis-suggestions">
                            <div class="empty-suggestions">Analyzing your progress...</div>
                        </div>
                    </div>
                </div>
            `;
            
            // Insert before loading overlay
            const loadingOverlay = document.getElementById('loading-overlay');
            if (loadingOverlay) {
                console.log("JarvisHUD inserting HTML before loading-overlay");
                loadingOverlay.insertAdjacentHTML('beforebegin', hudHTML);
            } else {
                console.error("JarvisHUD render failed: no loading-overlay found");
                document.body.insertAdjacentHTML('beforeend', hudHTML);
            }
        } else {
            console.log("JarvisHUD already exists in DOM");
        }
    },

    attachEvents() {
        // Handle clicks outside to close
        document.addEventListener('click', (e) => {
            const hud = document.getElementById('jarvis-hud');
            if (hud && this.isOpen && !hud.contains(e.target)) {
                this.closePanel();
            }
        });
    },

    async fetchStatus() {
        if (!AppState.token) return;
        
        try {
            const data = await api('/api/jarvis/status');
            this.updateUI(data);
        } catch (e) {
            console.error('Failed to fetch JARVIS status:', e);
        }
    },

    updateUI(data) {
        const messageEl = document.getElementById('jarvis-message');
        const avatarEl = document.getElementById('jarvis-avatar');
        const suggestionsEl = document.getElementById('jarvis-suggestions');
        
        if (!messageEl || !avatarEl || !suggestionsEl) return;
        
        // Update message with typewriter effect
        this.typeMessage(messageEl, data.message);
        
        // Update mood classes
        avatarEl.className = `jarvis-avatar mood-${data.mood}`;
        
        // Render suggestions
        if (data.suggestions && data.suggestions.length > 0) {
            suggestionsEl.innerHTML = data.suggestions.map(s => `
                <div class="jarvis-suggestion-card type-${s.type}" onclick="JarvisHUD.handleAction('${s.action}')">
                    <div class="suggestion-icon">${this.getIconForType(s.type)}</div>
                    <div class="suggestion-content">
                        <h4>${s.title}</h4>
                        <p>${s.message}</p>
                    </div>
                    <div class="suggestion-arrow"><i class="fas fa-arrow-right"></i></div>
                </div>
            `).join('');
            
            // Add notification dot if closed
            if (!this.isOpen) {
                document.getElementById('jarvis-hud').classList.add('has-notifications');
            }
        } else {
            suggestionsEl.innerHTML = `<div class="empty-suggestions">No new suggestions right now. Keep up the good work!</div>`;
        }
    },

    typeMessage(element, text) {
        element.style.opacity = '0';
        setTimeout(() => {
            element.textContent = text;
            element.style.opacity = '1';
        }, 300);
    },

    getIconForType(type) {
        const icons = {
            'review': '<i class="fas fa-sync-alt"></i>',
            'goal': '<i class="fas fa-bullseye"></i>',
            'explore': '<i class="fas fa-compass"></i>',
            'break': '<i class="fas fa-coffee"></i>'
        };
        return icons[type] || '<i class="fas fa-lightbulb"></i>';
    },

    togglePanel() {
        if (this.isOpen) {
            this.closePanel();
        } else {
            this.openPanel();
        }
    },

    openPanel() {
        const hud = document.getElementById('jarvis-hud');
        if (hud) {
            hud.classList.remove('closed');
            hud.classList.add('open', 'panel-active');
            hud.classList.remove('has-notifications');
            document.getElementById('jarvis-chevron').className = 'fas fa-chevron-down';
            this.isOpen = true;
        }
    },

    closePanel() {
        const hud = document.getElementById('jarvis-hud');
        if (hud) {
            hud.classList.remove('open', 'panel-active');
            hud.classList.add('closed');
            document.getElementById('jarvis-chevron').className = 'fas fa-chevron-up';
            this.isOpen = false;
        }
    },

    handleAction(action) {
        this.closePanel();
        if (action.startsWith('/')) {
            // It's a route path
            const parts = action.split('/');
            const page = parts[1];
            
            if (page === 'classroom' && parts.length > 3) {
                // Handle lesson resume -> /classroom/courseId/lessonId
                Classroom.startLesson(parseInt(parts[3]));
            } else {
                App.navigate(page);
            }
        }
    },
    
    // Called when user logs out
    reset() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        this.initialized = false;
        const hud = document.getElementById('jarvis-hud');
        if (hud) hud.remove();
    }
};

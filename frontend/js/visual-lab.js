/* ═══════════════════════════════════════════════════════════════
   Visual Lab Module - AI-Powered Educational Visual Generator
   Students can generate interactive visuals for any concept
   ═══════════════════════════════════════════════════════════════ */

const VisualLab = {
    history: [],

    fillExample(text) {
        document.getElementById('visual-lab-concept').value = text;
    },

    async generate() {
        const input = document.getElementById('visual-lab-concept');
        const concept = input.value.trim();
        if (!concept) {
            App.toast('Please enter a concept to visualize!', 'info');
            input.focus();
            return;
        }

        const typeRadio = document.querySelector('input[name="visual-type"]:checked');
        const visualType = typeRadio ? typeRadio.value : 'animation';

        const output = document.getElementById('visual-lab-output');
        const result = document.getElementById('visual-lab-result');
        output.classList.remove('hidden');

        result.innerHTML = `
            <div class="card visual-lab-generating">
                <div class="visual-loader-ring large"></div>
                <h3>Generating ${visualType === 'image' ? 'AI Image' : 'Interactive Animation'}...</h3>
                <p class="text-muted">"${Classroom.escapeHtml(concept)}"</p>
                <p class="text-muted">This may take 10-20 seconds. The AI is creating a custom visual just for you.</p>
            </div>`;

        try {
            const endpoint = visualType === 'image' ? '/api/visuals/image' : '/api/visuals/animation';
            const data = await api(endpoint, {
                method: 'POST',
                body: { concept, context: '', visual_type: visualType }
            });

            if (data.type === 'animation' && data.html) {
                const blob = new Blob([data.html], { type: 'text/html' });
                const blobUrl = URL.createObjectURL(blob);
                result.innerHTML = `
                    <div class="card visual-lab-result-card">
                        <div class="visual-lab-result-header">
                            <div>
                                <span class="ai-visual-badge">AI Generated Animation</span>
                                <h3>${Classroom.escapeHtml(data.title || concept)}</h3>
                            </div>
                            <div class="visual-lab-result-actions">
                                <button class="btn btn-sm btn-ghost" onclick="VisualLab.regenerate()" title="Regenerate">
                                    <i class="fas fa-sync-alt"></i> Regenerate
                                </button>
                                <button class="btn btn-sm btn-ghost" onclick="VisualLab.toggleFullscreen()" title="Fullscreen">
                                    <i class="fas fa-expand"></i> Fullscreen
                                </button>
                            </div>
                        </div>
                        <iframe class="visual-lab-frame" id="visual-lab-iframe" src="${blobUrl}" sandbox="allow-scripts"></iframe>
                    </div>`;

                this.addToHistory(concept, 'animation', blobUrl);

            } else if (data.type === 'image' && data.url) {
                result.innerHTML = `
                    <div class="card visual-lab-result-card">
                        <div class="visual-lab-result-header">
                            <div>
                                <span class="ai-visual-badge">AI Generated Image (DALL-E 3)</span>
                                <h3>${Classroom.escapeHtml(data.title || concept)}</h3>
                            </div>
                            <div class="visual-lab-result-actions">
                                <button class="btn btn-sm btn-ghost" onclick="VisualLab.regenerate()">
                                    <i class="fas fa-sync-alt"></i> Regenerate
                                </button>
                                <a href="${data.url}" target="_blank" class="btn btn-sm btn-ghost">
                                    <i class="fas fa-external-link-alt"></i> Open Full Size
                                </a>
                            </div>
                        </div>
                        <img class="visual-lab-image" src="${data.url}" alt="${Classroom.escapeHtml(concept)}">
                    </div>`;

                this.addToHistory(concept, 'image', data.url);
            } else {
                throw new Error('Unexpected response format');
            }

            App.toast('+5 XP for generating a visual!', 'xp');
            App.updateXPDisplay();

        } catch (err) {
            console.error('Visual Lab error:', err);
            result.innerHTML = `
                <div class="card visual-lab-error">
                    <i class="fas fa-exclamation-triangle" style="font-size: 2rem; color: var(--accent-warning)"></i>
                    <h3>Generation Failed</h3>
                    <p class="text-muted">${err.message || 'Could not generate visual. Please try again.'}</p>
                    <button class="btn btn-primary" onclick="VisualLab.regenerate()">
                        <i class="fas fa-sync-alt"></i> Try Again
                    </button>
                </div>`;
        }
    },

    regenerate() {
        this.generate();
    },

    toggleFullscreen() {
        const iframe = document.getElementById('visual-lab-iframe');
        if (!iframe) return;

        const overlay = document.createElement('div');
        overlay.className = 'visual-fullscreen-overlay';
        overlay.innerHTML = `
            <div class="visual-fullscreen-content">
                <button class="visual-fullscreen-close" onclick="this.closest('.visual-fullscreen-overlay').remove()">
                    <i class="fas fa-times"></i> Close
                </button>
                <iframe src="${iframe.src}" sandbox="allow-scripts" class="visual-fullscreen-frame"></iframe>
            </div>`;
        document.body.appendChild(overlay);
    },

    addToHistory(concept, type, url) {
        this.history.unshift({ concept, type, url, time: new Date() });
        if (this.history.length > 10) this.history.pop();
        this.renderHistory();
    },

    renderHistory() {
        const section = document.getElementById('visual-lab-history');
        const grid = document.getElementById('visual-lab-history-grid');
        if (this.history.length === 0) {
            section.classList.add('hidden');
            return;
        }
        section.classList.remove('hidden');
        grid.innerHTML = this.history.map((item, i) => `
            <div class="visual-history-item" onclick="VisualLab.replayHistory(${i})">
                <div class="visual-history-icon">${item.type === 'animation' ? '🎬' : '🖼️'}</div>
                <div class="visual-history-info">
                    <div class="visual-history-title">${Classroom.escapeHtml(item.concept)}</div>
                    <div class="visual-history-meta">${item.type} · ${this.timeAgo(item.time)}</div>
                </div>
            </div>
        `).join('');
    },

    replayHistory(index) {
        const item = this.history[index];
        if (!item) return;

        const result = document.getElementById('visual-lab-result');
        const output = document.getElementById('visual-lab-output');
        output.classList.remove('hidden');

        if (item.type === 'animation') {
            result.innerHTML = `
                <div class="card visual-lab-result-card">
                    <div class="visual-lab-result-header">
                        <div>
                            <span class="ai-visual-badge">AI Generated Animation</span>
                            <h3>${Classroom.escapeHtml(item.concept)}</h3>
                        </div>
                    </div>
                    <iframe class="visual-lab-frame" id="visual-lab-iframe" src="${item.url}" sandbox="allow-scripts"></iframe>
                </div>`;
        } else {
            result.innerHTML = `
                <div class="card visual-lab-result-card">
                    <div class="visual-lab-result-header">
                        <div>
                            <span class="ai-visual-badge">AI Generated Image</span>
                            <h3>${Classroom.escapeHtml(item.concept)}</h3>
                        </div>
                    </div>
                    <img class="visual-lab-image" src="${item.url}" alt="${Classroom.escapeHtml(item.concept)}">
                </div>`;
        }
    },

    timeAgo(date) {
        const seconds = Math.floor((new Date() - date) / 1000);
        if (seconds < 60) return 'just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        return `${Math.floor(seconds / 3600)}h ago`;
    }
};

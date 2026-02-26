/* ═══════════════════════════════════════════════════════════════
   Homework Module
   ═══════════════════════════════════════════════════════════════ */

const HomeworkPage = {
    currentHomeworkId: null,

    async load() {
        try {
            const data = await api('/api/homework');
            this.render(data);
        } catch(err) {
            App.toast('Failed to load homework', 'error');
        }
    },

    render(homeworks) {
        const list = document.getElementById('homework-list');
        
        if (homeworks.length === 0) {
            list.innerHTML = `
                <div class="card" style="text-align: center; padding: 40px;">
                    <h3>📚 No homework yet!</h3>
                    <p class="text-muted">Homework assignments will appear here when assigned by a teacher.</p>
                </div>
            `;
            return;
        }

        list.innerHTML = homeworks.map(h => {
            const diffColors = { easy: 'var(--success)', medium: 'var(--warning)', hard: 'var(--danger)' };
            const gradeColor = h.grade >= 80 ? 'var(--success)' : h.grade >= 50 ? 'var(--warning)' : 'var(--danger)';
            
            return `
                <div class="homework-card">
                    <div class="homework-card-header">
                        <div class="homework-title">📝 ${h.title}</div>
                        ${h.submitted ? 
                            (h.grade !== null ? 
                                `<span class="homework-grade" style="background: ${gradeColor}20; color: ${gradeColor}">Score: ${Math.round(h.grade)}%</span>` :
                                '<span class="status-badge status-completed">Submitted</span>') :
                            `<button class="btn btn-primary btn-sm" onclick="HomeworkPage.showSubmitForm(${h.id}, '${h.title.replace(/'/g, "\\'")}', '${h.description.replace(/'/g, "\\'")}')">
                                <i class="fas fa-paper-plane"></i> Submit
                            </button>`
                        }
                    </div>
                    <div class="homework-desc">${h.description}</div>
                    <div class="homework-meta">
                        <span><i class="fas fa-folder"></i> ${h.course}</span>
                        <span style="color: ${diffColors[h.difficulty] || 'var(--text-muted)'}">
                            <i class="fas fa-signal"></i> ${h.difficulty}
                        </span>
                        <span><i class="fas fa-star"></i> Max: ${h.max_score}</span>
                        ${h.due_date ? `<span><i class="fas fa-clock"></i> Due: ${new Date(h.due_date).toLocaleDateString()}</span>` : ''}
                    </div>
                    ${h.feedback ? `
                        <div style="margin-top: 12px; padding: 12px; background: var(--bg-secondary); border-radius: var(--radius-sm); font-size: 0.85rem;">
                            <strong>📋 Feedback:</strong><br>
                            ${this.parseFeedback(h.feedback)}
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');
    },

    parseFeedback(feedback) {
        try {
            const f = JSON.parse(feedback);
            return `
                <p>${f.feedback || ''}</p>
                ${f.strengths ? `<p style="color: var(--success)">✅ Strengths: ${f.strengths.join(', ')}</p>` : ''}
                ${f.improvements ? `<p style="color: var(--warning)">💡 Can improve: ${f.improvements.join(', ')}</p>` : ''}
                ${f.suggestions ? `<p>📖 Next: ${f.suggestions}</p>` : ''}
            `;
        } catch {
            return feedback;
        }
    },

    showCreateForm() {
        document.getElementById('homework-create-modal').classList.remove('hidden');
    },

    hideCreateForm() {
        document.getElementById('homework-create-modal').classList.add('hidden');
    },

    async create() {
        const title = document.getElementById('hw-title').value.trim();
        const description = document.getElementById('hw-description').value.trim();
        const difficulty = document.getElementById('hw-difficulty').value;
        const maxScore = parseInt(document.getElementById('hw-max-score').value) || 100;

        if (!title || !description) {
            App.toast('Please fill in title and description', 'error');
            return;
        }

        try {
            await api('/api/homework/create', {
                method: 'POST',
                body: { title, description, difficulty, max_score: maxScore }
            });
            this.hideCreateForm();
            App.toast('Homework created! 📝', 'success');
            this.load();
        } catch(err) {
            App.toast(err.message || 'Failed to create homework', 'error');
        }
    },

    showSubmitForm(homeworkId, title, description) {
        this.currentHomeworkId = homeworkId;
        document.getElementById('hw-submit-title').textContent = `Submit: ${title}`;
        document.getElementById('hw-submit-desc').textContent = description;
        document.getElementById('hw-content').value = '';
        document.getElementById('homework-submit-modal').classList.remove('hidden');
    },

    hideSubmitForm() {
        document.getElementById('homework-submit-modal').classList.add('hidden');
    },

    async submit() {
        const content = document.getElementById('hw-content').value.trim();
        if (!content) {
            App.toast('Please write your solution!', 'error');
            return;
        }

        App.loading(true);
        try {
            const result = await api('/api/homework/submit', {
                method: 'POST',
                body: { homework_id: this.currentHomeworkId, content }
            });
            this.hideSubmitForm();
            App.toast(`Homework graded: ${Math.round(result.grade)}% (+${result.xp_earned} XP)`, 'xp');
            App.updateXPDisplay();
            this.load();
        } catch(err) {
            App.toast(err.message || 'Failed to submit homework', 'error');
        } finally {
            App.loading(false);
        }
    }
};

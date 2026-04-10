/* ═══════════════════════════════════════════════════════════════
   Classroom & Tutor Module — Futuristic Real-Teacher Experience
   The interactive teaching interface - the heart of the app
   ═══════════════════════════════════════════════════════════════ */

const Classroom = {
    currentLessonId: null,
    isTeaching: false,
    currentPhase: 'idle',        // teaching | questioning | feedback | summary
    conceptsList: [],            // All concepts for the lesson
    currentConceptIndex: 0,
    totalConcepts: 0,
    understanding: 0,

    // Start a lesson - tutor begins teaching
    async startLesson(lessonId) {
        this.currentLessonId = lessonId;
        App.navigate('classroom');

        // Clear chat
        const chat = document.getElementById('classroom-chat');
        chat.innerHTML = '';
        
        // Show cinematic intro
        this.showLessonIntro();
        
        // Show typing animation
        this.addTypingIndicator();
        
        try {
            const data = await api('/api/tutor/start-lesson', {
                method: 'POST',
                body: { lesson_id: lessonId }
            });
            
            this.removeTypingIndicator();
            this.hideLessonIntro();
            
            // Setup lesson data
            if (data.lesson) {
                document.getElementById('classroom-title').textContent = data.lesson.title;
                document.getElementById('classroom-course').textContent = data.lesson.course;
                this.conceptsList = data.lesson.concepts || [];
                this.totalConcepts = data.lesson.total_concepts || 0;
                this.currentConceptIndex = data.lesson.current_concept || 0;
                this.understanding = data.understanding || 0;
                
                this.updateProgress(this.currentConceptIndex, this.totalConcepts);
                this.updateUnderstandingMeter(0);
                this.renderConceptCards();
            }
            
            // Update phase indicator
            this.setPhase(data.phase || 'teaching');
            
            // Show tutor message with entrance animation
            this.addMessage('tutor', data.message);
            this.isTeaching = true;
            
            // Auto-speak if voice is enabled
            if (Voice.enabled) {
                Voice.speak(data.message);
            }
            
            this.scrollToBottom();
            
            // Animated XP notification
            this.showXPGain(10, 'Started a lesson!');
            App.updateXPDisplay();
            
        } catch(err) {
            this.removeTypingIndicator();
            this.hideLessonIntro();
            this.addMessage('tutor', '❌ Failed to start lesson. Please try again.');
            App.toast('Failed to start lesson', 'error');
        }
    },

    // Send student message to tutor
    async sendMessage() {
        const input = document.getElementById('student-input');
        const message = input.value.trim();
        
        if (!message || !this.currentLessonId) {
            if (!this.currentLessonId) {
                App.toast('Please select a lesson first!', 'info');
            }
            return;
        }
        
        input.value = '';
        
        // Show student message
        this.addMessage('student', message);
        this.scrollToBottom();
        
        // Show typing indicator with avatar animation
        this.addTypingIndicator();
        this.setAvatarState('thinking');
        
        // Disable input while waiting
        const sendBtn = document.getElementById('send-btn');
        sendBtn.disabled = true;
        
        try {
            const data = await api('/api/tutor/respond', {
                method: 'POST',
                body: { lesson_id: this.currentLessonId, message }
            });
            
            this.removeTypingIndicator();
            this.setAvatarState('idle');
            
            // Update phase
            this.setPhase(data.phase || 'teaching');
            
            // Show tutor response
            this.addMessage('tutor', data.message);
            
            // Handle structured response
            if (data.is_correct === true) {
                this.showCorrectFeedback();
                this.showXPGain(10, 'Correct answer!');
            } else if (data.is_correct === false) {
                this.showEncouragement();
                this.showXPGain(3, 'Keep trying!');
            }
            
            // Update progress
            if (data.progress) {
                this.currentConceptIndex = data.progress.current_concept;
                this.understanding = data.progress.understanding;
                this.updateProgress(data.progress.current_concept, data.progress.total_concepts);
                this.updateUnderstandingMeter(data.progress.understanding);
                
                // Update concept cards
                if (data.concept_mastered) {
                    this.markConceptMastered(data.progress.current_concept - 1);
                }
                
                App.updateXPDisplay();
            }
            
            // Check if lesson complete
            if (data.lesson_complete) {
                this.setPhase('summary');
                this.showLessonComplete();
            }
            
            // Auto-speak
            if (Voice.enabled) {
                Voice.speak(data.message);
            }
            
            this.scrollToBottom();
            
        } catch(err) {
            this.removeTypingIndicator();
            this.setAvatarState('idle');
            this.addMessage('tutor', 'Sorry, I had trouble processing that. Could you try again? 🤔');
        } finally {
            sendBtn.disabled = false;
            input.focus();
        }
    },

    // ─── Phase System ─────────────────────────────────────────
    setPhase(phase) {
        this.currentPhase = phase;
        const indicator = document.getElementById('phase-indicator');
        if (!indicator) return;
        
        const phases = {
            teaching:    { icon: '📚', label: 'Teaching', color: '#6366f1' },
            questioning: { icon: '❓', label: 'Checking Understanding', color: '#f59e0b' },
            feedback:    { icon: '💬', label: 'Giving Feedback', color: '#10b981' },
            summary:     { icon: '🏆', label: 'Lesson Complete!', color: '#ef4444' },
        };
        
        const p = phases[phase] || phases.teaching;
        indicator.innerHTML = `<span class="phase-icon">${p.icon}</span><span class="phase-label">${p.label}</span>`;
        indicator.style.setProperty('--phase-color', p.color);
        indicator.classList.add('phase-pulse');
        setTimeout(() => indicator.classList.remove('phase-pulse'), 600);
    },

    // ─── Understanding Meter (Circular SVG) ────────────────────
    updateUnderstandingMeter(percent) {
        const circle = document.getElementById('understanding-circle');
        const text = document.getElementById('understanding-text');
        if (!circle || !text) return;
        
        const circumference = 2 * Math.PI * 45; // radius = 45
        const offset = circumference - (percent / 100) * circumference;
        circle.style.strokeDasharray = circumference;
        circle.style.strokeDashoffset = offset;
        text.textContent = `${Math.round(percent)}%`;
        
        // Color based on understanding
        if (percent >= 80) {
            circle.style.stroke = '#10b981'; // green
        } else if (percent >= 50) {
            circle.style.stroke = '#f59e0b'; // amber
        } else {
            circle.style.stroke = '#6366f1'; // purple
        }
    },

    // ─── Concept Progress Cards ────────────────────────────────
    renderConceptCards() {
        const container = document.getElementById('concept-cards');
        if (!container) return;
        
        container.innerHTML = this.conceptsList.map((concept, i) => `
            <div class="concept-card ${i < this.currentConceptIndex ? 'mastered' : (i === this.currentConceptIndex ? 'active' : '')}" 
                 id="concept-card-${i}">
                <div class="concept-num">${i + 1}</div>
                <div class="concept-name">${this.escapeHtml(concept)}</div>
                <div class="concept-status">
                    ${i < this.currentConceptIndex ? '✅' : (i === this.currentConceptIndex ? '📖' : '🔒')}
                </div>
            </div>
        `).join('');
    },

    markConceptMastered(index) {
        const card = document.getElementById(`concept-card-${index}`);
        if (card) {
            card.classList.add('mastered');
            card.classList.remove('active');
            card.querySelector('.concept-status').textContent = '✅';
            
            // Glow animation
            card.classList.add('concept-glow');
            setTimeout(() => card.classList.remove('concept-glow'), 1500);
        }
        
        // Mark next as active
        const nextCard = document.getElementById(`concept-card-${index + 1}`);
        if (nextCard) {
            nextCard.classList.add('active');
            nextCard.querySelector('.concept-status').textContent = '📖';
        }
    },

    // ─── Visual Feedback Effects ──────────────────────────────
    showCorrectFeedback() {
        // Spawn celebration particles
        this.spawnParticles('correct');
        
        // Flash the understanding meter green
        const meter = document.getElementById('understanding-meter');
        if (meter) {
            meter.classList.add('meter-correct');
            setTimeout(() => meter.classList.remove('meter-correct'), 1000);
        }
    },

    showEncouragement() {
        // Gentle pulse on the chat area
        const chat = document.getElementById('classroom-chat');
        if (chat) {
            chat.classList.add('encourage-pulse');
            setTimeout(() => chat.classList.remove('encourage-pulse'), 800);
        }
    },

    showXPGain(amount, reason) {
        const popup = document.createElement('div');
        popup.className = 'xp-popup';
        popup.innerHTML = `<span class="xp-amount">+${amount} XP</span><span class="xp-reason">${reason}</span>`;
        document.body.appendChild(popup);
        
        // Animate up and fade
        requestAnimationFrame(() => {
            popup.classList.add('xp-popup-animate');
        });
        
        setTimeout(() => popup.remove(), 2500);
    },

    spawnParticles(type) {
        const container = document.getElementById('particle-container');
        if (!container) return;
        
        const colors = type === 'correct' 
            ? ['#10b981', '#34d399', '#6ee7b7', '#fbbf24', '#fcd34d']
            : ['#6366f1', '#818cf8', '#a5b4fc'];
        
        for (let i = 0; i < 20; i++) {
            const particle = document.createElement('div');
            particle.className = 'celebration-particle';
            particle.style.left = `${30 + Math.random() * 40}%`;
            particle.style.top = `${30 + Math.random() * 40}%`;
            particle.style.background = colors[Math.floor(Math.random() * colors.length)];
            particle.style.setProperty('--dx', `${(Math.random() - 0.5) * 200}px`);
            particle.style.setProperty('--dy', `${-Math.random() * 200 - 50}px`);
            container.appendChild(particle);
            
            setTimeout(() => particle.remove(), 1500);
        }
    },

    // ─── Teacher Avatar ───────────────────────────────────────
    setAvatarState(state) {
        const avatar = document.getElementById('teacher-avatar');
        if (!avatar) return;
        
        avatar.classList.remove('avatar-speaking', 'avatar-thinking', 'avatar-celebrating');
        if (state === 'speaking') avatar.classList.add('avatar-speaking');
        else if (state === 'thinking') avatar.classList.add('avatar-thinking');
        else if (state === 'celebrating') avatar.classList.add('avatar-celebrating');
    },

    // ─── Cinematic Lesson Intro ───────────────────────────────
    showLessonIntro() {
        const overlay = document.getElementById('lesson-intro-overlay');
        if (overlay) {
            overlay.classList.add('active');
            overlay.innerHTML = `
                <div class="intro-content">
                    <div class="intro-rings">
                        <div class="intro-ring ring-1"></div>
                        <div class="intro-ring ring-2"></div>
                        <div class="intro-ring ring-3"></div>
                    </div>
                    <div class="intro-icon">🎓</div>
                    <div class="intro-text">Preparing your lesson...</div>
                    <div class="intro-sub">Professor AI is getting ready</div>
                </div>
            `;
        }
    },

    hideLessonIntro() {
        const overlay = document.getElementById('lesson-intro-overlay');
        if (overlay) {
            overlay.classList.add('fade-out');
            setTimeout(() => {
                overlay.classList.remove('active', 'fade-out');
                overlay.innerHTML = '';
            }, 500);
        }
    },

    // ─── Lesson Complete ──────────────────────────────────────
    showLessonComplete() {
        this.showXPGain(50, 'Lesson Complete!');
        App.updateXPDisplay();
        
        const chat = document.getElementById('classroom-chat');
        const div = document.createElement('div');
        div.className = 'chat-message tutor lesson-complete-card';
        div.innerHTML = `
            <div class="chat-avatar">🎉</div>
            <div class="chat-bubble lesson-complete-bubble">
                <div class="complete-header">
                    <div class="complete-trophy">🏆</div>
                    <h3>Lesson Complete!</h3>
                </div>
                <div class="complete-stats">
                    <div class="stat-item">
                        <div class="stat-value">${Math.round(this.understanding)}%</div>
                        <div class="stat-label">Understanding</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">+50</div>
                        <div class="stat-label">XP Earned</div>
                    </div>
                </div>
                <p>Great job! Ready to test your knowledge?</p>
                <div class="complete-actions">
                    <button class="btn btn-primary btn-glow" onclick="Classroom.takeQuiz()">
                        <i class="fas fa-clipboard-question"></i> Take the Quiz
                    </button>
                    <button class="btn btn-secondary" onclick="App.navigate('courses')">
                        <i class="fas fa-book"></i> More Lessons
                    </button>
                </div>
            </div>
        `;
        chat.appendChild(div);
        this.scrollToBottom();
        
        // Spawn lots of celebration particles
        for (let i = 0; i < 3; i++) {
            setTimeout(() => this.spawnParticles('correct'), i * 300);
        }
    },

    // Add a message to the chat
    addMessage(role, content) {
        const chat = document.getElementById('classroom-chat');
        const div = document.createElement('div');
        div.className = `chat-message ${role} message-enter`;
        
        const avatar = role === 'tutor' ? '🎓' : (AppState.user?.avatar || '🧑‍🎓');
        let renderedContent;
        if (role === 'tutor') {
            renderedContent = App.renderMarkdown(content);
            // Detect AI visual tags and replace with generated animations/diagrams
            renderedContent = this.enhanceWithMedia(renderedContent);
        } else {
            renderedContent = this.escapeHtml(content);
        }
        
        div.innerHTML = `
            <div class="chat-avatar">${avatar}</div>
            <div class="chat-bubble">${renderedContent}</div>
        `;
        
        chat.appendChild(div);
        
        // Trigger entrance animation
        requestAnimationFrame(() => {
            div.classList.add('message-visible');
        });
        
        // Highlight code blocks
        if (role === 'tutor' && typeof hljs !== 'undefined') {
            div.querySelectorAll('pre code').forEach(block => {
                hljs.highlightElement(block);
            });
        }
    },

    // Enhance rendered HTML — detect visual tags and replace with AI-generated visuals
    enhanceWithMedia(html) {
        // Detect [VISUAL_ANIMATION: description] tags and replace with visual placeholders
        html = html.replace(
            /\[VISUAL_ANIMATION:\s*([^\]]+)\]/gi,
            (match, description) => {
                const id = 'visual-' + Date.now() + '-' + Math.random().toString(36).substr(2, 6);
                // Trigger async generation
                setTimeout(() => this.generateVisual(id, description.trim(), 'animation'), 100);
                return `<div class="ai-visual-container" id="${id}">
                    <div class="ai-visual-loading">
                        <div class="visual-loader-ring"></div>
                        <span class="visual-loader-text">Generating visual: ${this.escapeHtml(description.trim())}...</span>
                    </div>
                </div>`;
            }
        );

        // Detect [VISUAL_DIAGRAM: description] tags
        html = html.replace(
            /\[VISUAL_DIAGRAM:\s*([^\]]+)\]/gi,
            (match, description) => {
                const id = 'visual-' + Date.now() + '-' + Math.random().toString(36).substr(2, 6);
                setTimeout(() => this.generateVisual(id, description.trim(), 'animation'), 100);
                return `<div class="ai-visual-container" id="${id}">
                    <div class="ai-visual-loading">
                        <div class="visual-loader-ring"></div>
                        <span class="visual-loader-text">Generating diagram: ${this.escapeHtml(description.trim())}...</span>
                    </div>
                </div>`;
            }
        );

        // Make any remaining images responsive
        html = html.replace(/<img\s/gi, '<img loading="lazy" ');

        return html;
    },

    // Generate a visual via the API and inject it into the placeholder
    async generateVisual(containerId, concept, type) {
        const container = document.getElementById(containerId);
        if (!container) return;

        try {
            const data = await api('/api/visuals/generate', {
                method: 'POST',
                body: { concept, context: '', visual_type: type }
            }, 60000); // 60 second timeout for visuals

            if (data.type === 'animation' && data.html) {
                // Render HTML animation in a sandboxed iframe
                const blob = new Blob([data.html], { type: 'text/html' });
                const blobUrl = URL.createObjectURL(blob);
                container.innerHTML = `
                    <div class="ai-visual-wrapper">
                        <div class="ai-visual-header">
                            <span class="ai-visual-badge">AI Generated</span>
                            <span class="ai-visual-title">${this.escapeHtml(data.title || concept)}</span>
                            <div class="ai-visual-actions">
                                <button class="btn btn-xs btn-ghost" onclick="Classroom.regenVisual('${containerId}','${this.escapeAttr(concept)}','${type}')" title="Regenerate">
                                    <i class="fas fa-sync-alt"></i>
                                </button>
                                <button class="btn btn-xs btn-ghost" onclick="Classroom.expandVisual(this)" title="Fullscreen">
                                    <i class="fas fa-expand"></i>
                                </button>
                            </div>
                        </div>
                        <iframe class="ai-visual-frame" src="${blobUrl}" sandbox="allow-scripts" loading="lazy"></iframe>
                    </div>`;
            } else if (data.type === 'image' && data.url) {
                container.innerHTML = `
                    <div class="ai-visual-wrapper">
                        <div class="ai-visual-header">
                            <span class="ai-visual-badge">AI Generated</span>
                            <span class="ai-visual-title">${this.escapeHtml(data.title || concept)}</span>
                        </div>
                        <img class="ai-visual-image" src="${data.url}" alt="${this.escapeHtml(concept)}" loading="lazy">
                    </div>`;
            } else if (data.type === 'inline_svg' && data.svg) {
                container.innerHTML = `
                    <div class="ai-visual-wrapper">
                        <div class="ai-visual-header">
                            <span class="ai-visual-badge">AI Generated</span>
                            <span class="ai-visual-title">${this.escapeHtml(concept)}</span>
                        </div>
                        <div class="ai-visual-svg">${data.svg}</div>
                    </div>`;
            } else {
                container.innerHTML = `<div class="ai-visual-error">Could not generate visual. <button class="btn btn-xs btn-accent" onclick="Classroom.regenVisual('${containerId}','${this.escapeAttr(concept)}','${type}')">Retry</button></div>`;
            }
        } catch (err) {
            console.error('Visual generation error:', err);
            container.innerHTML = `<div class="ai-visual-error">
                <i class="fas fa-exclamation-triangle"></i> Visual generation failed.
                <button class="btn btn-xs btn-accent" onclick="Classroom.regenVisual('${containerId}','${this.escapeAttr(concept)}','${type}')" style="margin-left:8px">Retry</button>
            </div>`;
        }
        this.scrollToBottom();
    },

    // Regenerate a visual
    regenVisual(containerId, concept, type) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = `<div class="ai-visual-loading">
            <div class="visual-loader-ring"></div>
            <span class="visual-loader-text">Regenerating visual...</span>
        </div>`;
        this.generateVisual(containerId, concept, type);
    },

    // Expand visual to fullscreen overlay
    expandVisual(btn) {
        const wrapper = btn.closest('.ai-visual-wrapper');
        const iframe = wrapper.querySelector('.ai-visual-frame');
        if (!iframe) return;
        
        const overlay = document.createElement('div');
        overlay.className = 'visual-fullscreen-overlay';
        overlay.innerHTML = `
            <div class="visual-fullscreen-content">
                <button class="visual-fullscreen-close" onclick="this.closest('.visual-fullscreen-overlay').remove()">
                    <i class="fas fa-times"></i> Close (Esc)
                </button>
                <iframe src="${iframe.src}" sandbox="allow-scripts" class="visual-fullscreen-frame"></iframe>
            </div>`;
        document.body.appendChild(overlay);

        // Close on Escape key
        const closeOnEsc = (e) => {
            if (e.key === 'Escape') {
                overlay.remove();
                document.removeEventListener('keydown', closeOnEsc);
            }
        };
        document.addEventListener('keydown', closeOnEsc);
    },

    escapeAttr(str) {
        return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
    },

    // Request a visual for whatever topic the student types / current lesson
    async requestVisual() {
        const input = document.getElementById('student-input');
        let concept = input.value.trim();
        
        if (!concept) {
            // Use current lesson title as the concept
            const titleEl = document.getElementById('classroom-title');
            concept = titleEl ? titleEl.textContent : '';
            if (!concept || concept === 'Virtual Classroom') {
                App.toast('Type a concept in the input box, then click the visual button!', 'info');
                return;
            }
        }
        
        input.value = '';
        
        // Add a system message in chat
        const id = 'visual-req-' + Date.now();
        const chat = document.getElementById('classroom-chat');
        
        // Show student request
        this.addMessage('student', `🎨 Generate a visual for: ${concept}`);
        
        // Add visual placeholder
        const div = document.createElement('div');
        div.className = 'chat-message tutor message-enter';
        div.innerHTML = `
            <div class="chat-avatar">🎓</div>
            <div class="chat-bubble">
                <p>Let me create an interactive visual for <strong>${this.escapeHtml(concept)}</strong>...</p>
                <div class="ai-visual-container" id="${id}">
                    <div class="ai-visual-loading">
                        <div class="visual-loader-ring"></div>
                        <span class="visual-loader-text">Generating AI visual...</span>
                    </div>
                </div>
            </div>`;
        chat.appendChild(div);
        requestAnimationFrame(() => div.classList.add('message-visible'));
        this.scrollToBottom();
        
        // Generate
        await this.generateVisual(id, concept, 'animation');
    },

    addTypingIndicator() {
        const chat = document.getElementById('classroom-chat');
        const existing = chat.querySelector('.typing-indicator');
        if (existing) return;
        
        const div = document.createElement('div');
        div.className = 'chat-message tutor';
        div.id = 'typing-message';
        div.innerHTML = `
            <div class="chat-avatar avatar-thinking">🎓</div>
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <span class="typing-text">Professor AI is thinking...</span>
            </div>
        `;
        chat.appendChild(div);
        this.scrollToBottom();
    },

    removeTypingIndicator() {
        const el = document.getElementById('typing-message');
        if (el) el.remove();
    },

    updateProgress(current, total) {
        const numEl = document.getElementById('classroom-concept-num');
        if (numEl) numEl.textContent = `${current + 1}/${total}`;
        const percent = total > 0 ? ((current + 1) / total) * 100 : 0;
        const fill = document.getElementById('classroom-progress-fill');
        if (fill) fill.style.width = `${Math.min(percent, 100)}%`;
    },

    takeQuiz() {
        if (this.currentLessonId) {
            Quiz.startQuiz(this.currentLessonId);
            App.navigate('quiz');
        } else {
            App.navigate('quiz');
        }
    },

    scrollToBottom() {
        const chat = document.getElementById('classroom-chat');
        setTimeout(() => {
            chat.scrollTop = chat.scrollHeight;
        }, 100);
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};


/* ═══════════════════════════════════════════════════════════════
   Courses Module
   ═══════════════════════════════════════════════════════════════ */

const Courses = {
    coursesData: [],

    async load() {
        try {
            const courses = await api('/api/courses');
            this.coursesData = courses;
            this.renderCourseGrid(courses);
        } catch(err) {
            App.toast('Failed to load courses', 'error');
        }
    },

    renderCourseGrid(courses) {
        const grid = document.getElementById('courses-grid');
        document.getElementById('course-detail').classList.add('hidden');
        grid.classList.remove('hidden');
        
        grid.innerHTML = courses.map(c => `
            <div class="course-card" onclick="Courses.showCourseDetail(${c.id})">
                <div class="course-card-icon">${c.icon}</div>
                <div class="course-card-title">${c.title}</div>
                <div class="course-card-desc">${c.description}</div>
                <div class="course-card-meta">
                    <span><i class="fas fa-book"></i> ${c.total_lessons} lessons</span>
                    <span><i class="fas fa-signal"></i> ${c.difficulty}</span>
                    <span><i class="fas fa-folder"></i> ${c.category}</span>
                </div>
                <div class="course-card-progress">
                    <div class="course-card-progress-text">
                        <span>${c.completed_lessons}/${c.total_lessons} completed</span>
                        <span>${c.progress_percent}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${c.progress_percent}%"></div>
                    </div>
                </div>
            </div>
        `).join('');
    },

    async showCourseDetail(courseId) {
        try {
            const course = await api(`/api/courses/${courseId}`);
            AppState.currentCourse = course;
            
            document.getElementById('courses-grid').classList.add('hidden');
            const detail = document.getElementById('course-detail');
            detail.classList.remove('hidden');
            
            detail.querySelector('#course-detail-content').innerHTML = `
                <div class="course-detail-header">
                    <div class="course-detail-icon">${course.icon}</div>
                    <div>
                        <h2>${course.title}</h2>
                        <p class="text-muted">${course.description}</p>
                        <div class="course-card-meta" style="margin-top: 8px;">
                            <span><i class="fas fa-signal"></i> ${course.difficulty}</span>
                            <span><i class="fas fa-folder"></i> ${course.category}</span>
                            <span><i class="fas fa-book"></i> ${course.lessons.length} lessons</span>
                        </div>
                    </div>
                </div>
                
                <h3 style="margin: 20px 0 12px;"><i class="fas fa-list-ol" style="color: var(--accent-primary)"></i> Lessons</h3>
                <div class="lesson-list">
                    ${course.lessons.map(l => `
                        <div class="lesson-item" onclick="Courses.openLesson(${l.id})">
                            <div class="lesson-num">${l.order_num}</div>
                            <div class="lesson-info">
                                <div class="lesson-title">${l.title}</div>
                                <div class="lesson-meta">
                                    <span><i class="fas fa-clock"></i> ${l.estimated_minutes} min</span>
                                    <span><i class="fas fa-signal"></i> ${l.difficulty}</span>
                                    ${l.understanding > 0 ? `<span><i class="fas fa-brain"></i> ${Math.round(l.understanding)}% understood</span>` : ''}
                                </div>
                            </div>
                            <div class="lesson-status">
                                <span class="status-badge status-${l.status}">${l.status.replace('_', ' ')}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        } catch(err) {
            App.toast('Failed to load course', 'error');
        }
    },

    showCourseList() {
        document.getElementById('courses-grid').classList.remove('hidden');
        document.getElementById('course-detail').classList.add('hidden');
    },

    openLesson(lessonId) {
        AppState.currentLesson = lessonId;
        Classroom.startLesson(lessonId);
    }
};

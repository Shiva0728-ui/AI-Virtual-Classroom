/* ═══════════════════════════════════════════════════════════════
   Quiz Module
   ═══════════════════════════════════════════════════════════════ */

const Quiz = {
    questions: [],
    currentIndex: 0,
    score: 0,
    currentLessonId: null,
    answered: false,

    async loadSelection() {
        // Show quiz lesson selection
        document.getElementById('quiz-selection').classList.remove('hidden');
        document.getElementById('quiz-active').classList.add('hidden');
        document.getElementById('quiz-results').classList.add('hidden');

        try {
            const courses = await api('/api/courses');
            const grid = document.getElementById('quiz-lesson-list');
            
            let html = '';
            for (const course of courses) {
                const detail = await api(`/api/courses/${course.id}`);
                for (const lesson of detail.lessons) {
                    html += `
                        <div class="quiz-lesson-card" onclick="Quiz.startQuiz(${lesson.id})">
                            <div class="quiz-lesson-icon">${course.icon}</div>
                            <div>
                                <div style="font-weight:600; font-size:0.9rem;">${lesson.title}</div>
                                <div style="font-size:0.75rem; color:var(--text-muted);">${course.title} • ${lesson.difficulty}</div>
                            </div>
                        </div>
                    `;
                }
            }
            grid.innerHTML = html || '<p class="text-muted">No lessons available yet.</p>';
        } catch(err) {
            App.toast('Failed to load quiz options', 'error');
        }
    },

    async startQuiz(lessonId) {
        this.currentLessonId = lessonId;
        this.currentIndex = 0;
        this.score = 0;
        this.answered = false;

        App.loading(true);

        try {
            const data = await api(`/api/quiz/${lessonId}?count=5`);
            this.questions = data.questions || [];
            
            if (this.questions.length === 0) {
                App.toast('No quiz questions available', 'info');
                App.loading(false);
                return;
            }

            // Navigate to quiz page if not already there
            if (AppState.currentPage !== 'quiz') {
                App.navigate('quiz');
            }

            document.getElementById('quiz-selection').classList.add('hidden');
            document.getElementById('quiz-active').classList.remove('hidden');
            document.getElementById('quiz-results').classList.add('hidden');
            document.getElementById('quiz-title').textContent = `Quiz - Question ${this.currentIndex + 1}`;

            this.showQuestion();
        } catch(err) {
            App.toast('Failed to generate quiz', 'error');
        } finally {
            App.loading(false);
        }
    },

    showQuestion() {
        if (this.currentIndex >= this.questions.length) {
            this.showResults();
            return;
        }

        const q = this.questions[this.currentIndex];
        this.answered = false;

        // Update counter
        document.getElementById('quiz-counter').textContent = `${this.currentIndex + 1}/${this.questions.length}`;
        const percent = ((this.currentIndex) / this.questions.length) * 100;
        document.getElementById('quiz-progress-fill').style.width = `${percent}%`;
        document.getElementById('quiz-title').textContent = `Question ${this.currentIndex + 1}`;
        
        // Hide feedback and next button
        document.getElementById('quiz-feedback').classList.add('hidden');
        document.getElementById('quiz-next-btn').classList.add('hidden');

        const area = document.getElementById('quiz-question-area');
        const letters = ['A', 'B', 'C', 'D'];
        
        area.innerHTML = `
            <div class="quiz-question-text">${q.question}</div>
            <div class="quiz-options">
                ${q.options.map((opt, i) => `
                    <div class="quiz-option" data-index="${i}" onclick="Quiz.selectAnswer(${i})">
                        <div class="quiz-option-letter">${letters[i]}</div>
                        <span>${opt}</span>
                    </div>
                `).join('')}
            </div>
        `;

        // Voice read question
        if (Voice.enabled) {
            Voice.speak(q.question);
        }
    },

    async selectAnswer(index) {
        if (this.answered) return;
        this.answered = true;

        const q = this.questions[this.currentIndex];
        const isCorrect = index === q.correct;
        
        if (isCorrect) this.score++;

        // Highlight options
        document.querySelectorAll('.quiz-option').forEach((opt, i) => {
            if (i === q.correct) {
                opt.classList.add('correct');
            } else if (i === index && !isCorrect) {
                opt.classList.add('incorrect');
            }
        });

        // Show feedback
        const feedback = document.getElementById('quiz-feedback');
        feedback.classList.remove('hidden');
        feedback.className = `quiz-feedback ${isCorrect ? 'correct' : 'incorrect'}`;
        feedback.innerHTML = isCorrect
            ? `✅ <strong>Correct!</strong> ${q.explanation || 'Great job!'}`
            : `💡 <strong>Not quite!</strong> ${q.explanation || `The correct answer was: ${q.options[q.correct]}`}`;

        // Show next button
        document.getElementById('quiz-next-btn').classList.remove('hidden');

        // Submit to backend
        try {
            await api('/api/quiz/submit', {
                method: 'POST',
                body: {
                    lesson_id: this.currentLessonId,
                    question: q.question,
                    user_answer: q.options[index],
                    correct_answer: q.options[q.correct],
                    is_correct: isCorrect,
                }
            });
            
            if (isCorrect) {
                App.toast('+20 XP! 🎉', 'xp');
            } else {
                App.toast('+5 XP for trying! 💪', 'xp');
            }
            App.updateXPDisplay();
        } catch(e) {}
    },

    nextQuestion() {
        this.currentIndex++;
        this.showQuestion();
    },

    showResults() {
        document.getElementById('quiz-active').classList.add('hidden');
        document.getElementById('quiz-results').classList.remove('hidden');

        const percent = Math.round((this.score / this.questions.length) * 100);
        let grade, className, message;

        if (percent >= 80) {
            grade = `${percent}%`;
            className = 'great';
            message = '🏆 Excellent! You really understand this topic!';
        } else if (percent >= 50) {
            grade = `${percent}%`;
            className = 'ok';
            message = '👍 Good effort! Review the lesson to improve.';
        } else {
            grade = `${percent}%`;
            className = 'low';
            message = '💪 Keep learning! Go through the lesson again and try once more.';
        }

        document.getElementById('quiz-results-content').innerHTML = `
            <h2>Quiz Complete!</h2>
            <div class="quiz-score-big ${className}">${grade}</div>
            <p style="font-size: 1.1rem; margin-bottom: 8px;">${message}</p>
            <p class="text-muted">You got ${this.score} out of ${this.questions.length} correct</p>
            <div style="margin: 20px 0;">
                <span style="color: var(--xp-color); font-weight: 700;">
                    ⭐ +${this.score * 20 + (this.questions.length - this.score) * 5} XP earned
                </span>
            </div>
        `;
    },

    reset() {
        this.loadSelection();
    }
};

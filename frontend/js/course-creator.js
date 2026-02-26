/* ===============================================================
   Course Creator Module
   Lets students create custom courses from topics or file uploads
   =============================================================== */

const CourseCreator = {
    selectedFile: null,

    // Generate course from a topic description
    async generateFromTopic() {
        const topic = document.getElementById('cc-topic').value.trim();
        const detail = document.getElementById('cc-detail').value.trim();

        if (!topic) {
            App.toast('Please enter a topic you want to learn!', 'error');
            return;
        }

        this.showProgress('AI is designing your course on "' + topic + '"...');

        const btn = document.getElementById('cc-generate-btn');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';

        try {
            const data = await api('/api/courses/generate', {
                method: 'POST',
                body: { topic, detail }
            });

            this.hideProgress();
            this.showResult(data);
            App.toast('Course created successfully! +30 XP', 'xp');
            App.updateXPDisplay();

            // Clear form
            document.getElementById('cc-topic').value = '';
            document.getElementById('cc-detail').value = '';

        } catch (err) {
            this.hideProgress();
            App.toast(err.message || 'Failed to generate course. Please try again.', 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-wand-magic-sparkles"></i> Generate Course with AI';
        }
    },

    // Handle file selection
    fileSelected() {
        const input = document.getElementById('cc-file');
        if (input.files && input.files[0]) {
            this.selectedFile = input.files[0];
            const maxSize = 10 * 1024 * 1024; // 10MB
            if (this.selectedFile.size > maxSize) {
                App.toast('File is too large! Max 10MB.', 'error');
                this.clearFile();
                return;
            }
            document.getElementById('file-selected-name').textContent = this.selectedFile.name;
            document.querySelector('.file-upload-content').classList.add('hidden');
            document.getElementById('file-selected-info').classList.remove('hidden');
        }
    },

    clearFile() {
        this.selectedFile = null;
        document.getElementById('cc-file').value = '';
        document.querySelector('.file-upload-content').classList.remove('hidden');
        document.getElementById('file-selected-info').classList.add('hidden');
    },

    // Generate course from uploaded file
    async generateFromFile() {
        if (!this.selectedFile) {
            App.toast('Please select a file first!', 'error');
            return;
        }

        const titleHint = document.getElementById('cc-file-title').value.trim();
        this.showProgress('AI is analyzing "' + this.selectedFile.name + '" and creating a course...');

        const btn = document.getElementById('cc-file-btn');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';

        try {
            // Use FormData for file upload
            const formData = new FormData();
            formData.append('file', this.selectedFile);
            formData.append('title_hint', titleHint);

            const headers = {};
            if (AppState.token) {
                headers['Authorization'] = `Bearer ${AppState.token}`;
            }

            const response = await fetch('/api/courses/generate-from-file', {
                method: 'POST',
                headers: headers,
                body: formData,  // Don't set Content-Type - browser sets it with boundary
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to process file');
            }

            this.hideProgress();
            this.showResult(data);
            App.toast('Course created from file! +30 XP', 'xp');
            App.updateXPDisplay();

            // Clear form
            this.clearFile();
            document.getElementById('cc-file-title').value = '';

        } catch (err) {
            this.hideProgress();
            App.toast(err.message || 'Failed to generate course from file. Please try again.', 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-cogs"></i> Analyze & Create Course';
        }
    },

    showProgress(text) {
        const el = document.getElementById('cc-progress');
        el.classList.remove('hidden');
        document.getElementById('cc-progress-title').textContent = text || 'AI is creating your course...';
        document.getElementById('cc-result').classList.add('hidden');
    },

    hideProgress() {
        document.getElementById('cc-progress').classList.add('hidden');
    },

    showResult(data) {
        const el = document.getElementById('cc-result');
        el.classList.remove('hidden');

        const course = data.course;
        el.querySelector('#cc-result-content').innerHTML = `
            <div style="text-align: center; margin-bottom: 24px;">
                <div style="font-size: 3rem;">${course.icon || '📘'}</div>
                <h2 style="margin-top: 8px;">${course.title}</h2>
                <p class="text-muted">${course.description}</p>
                <p style="margin-top: 8px; color: var(--success); font-weight: 600;">
                    <i class="fas fa-check-circle"></i> ${course.lessons_count} lessons created!
                </p>
            </div>

            <div class="cc-result-lessons">
                <h4 style="margin-bottom: 12px;"><i class="fas fa-list-ol" style="color: var(--accent-primary);"></i> Lesson Plan</h4>
                ${course.lessons.map((l, i) => `
                    <div class="cc-result-lesson-item">
                        <div class="lesson-num">${i + 1}</div>
                        <div class="lesson-title">${l.title}</div>
                    </div>
                `).join('')}
            </div>

            <div style="text-align: center; margin-top: 24px; display: flex; gap: 12px; justify-content: center; flex-wrap: wrap;">
                <button class="btn btn-primary" onclick="Courses.openLesson(${course.lessons[0]?.id || 0})">
                    <i class="fas fa-play"></i> Start Learning Now
                </button>
                <button class="btn btn-secondary" onclick="Courses.showCourseDetail(${course.id}); App.navigate('courses')">
                    <i class="fas fa-eye"></i> View Full Course
                </button>
                <button class="btn btn-ghost" onclick="document.getElementById('cc-result').classList.add('hidden')">
                    <i class="fas fa-plus"></i> Create Another
                </button>
            </div>
        `;
    },

    // Drag & drop support
    initDragDrop() {
        const zone = document.getElementById('file-upload-zone');
        if (!zone) return;

        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('drag-over');
        });
        zone.addEventListener('dragleave', () => {
            zone.classList.remove('drag-over');
        });
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('drag-over');
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                const input = document.getElementById('cc-file');
                input.files = e.dataTransfer.files;
                CourseCreator.fileSelected();
            }
        });
    }
};

// Initialize drag & drop when page loads
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => CourseCreator.initDragDrop(), 500);
});

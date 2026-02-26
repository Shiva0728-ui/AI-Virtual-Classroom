/* ═══════════════════════════════════════════════════════════════
   Authentication Module
   ═══════════════════════════════════════════════════════════════ */

const Auth = {
    selectedRole: 'student',

    showLogin() {
        document.getElementById('login-form').classList.add('active');
        document.getElementById('register-form').classList.remove('active');
    },

    showRegister() {
        document.getElementById('login-form').classList.remove('active');
        document.getElementById('register-form').classList.add('active');
    },

    selectRole(role) {
        this.selectedRole = role;
        document.querySelectorAll('.role-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.role === role);
        });
    },

    async login() {
        const username = document.getElementById('login-username').value.trim();
        const password = document.getElementById('login-password').value;
        const errorEl = document.getElementById('login-error');
        
        errorEl.classList.add('hidden');

        if (!username || !password) {
            errorEl.textContent = 'Please fill in all fields';
            errorEl.classList.remove('hidden');
            return;
        }

        const btn = document.getElementById('login-btn');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Logging in...';

        try {
            const data = await api('/api/auth/login', {
                method: 'POST',
                body: { username, password }
            });
            
            AppState.token = data.access_token;
            AppState.user = data.user;
            localStorage.setItem('ai_classroom_token', data.access_token);
            localStorage.setItem('ai_classroom_user', JSON.stringify(data.user));
            
            App.showMainApp();
            App.toast(`Welcome back, ${data.user.full_name || data.user.username}! 🎉`, 'success');
        } catch(err) {
            errorEl.textContent = err.message || 'Login failed';
            errorEl.classList.remove('hidden');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Log In';
        }
    },

    async register() {
        const username = document.getElementById('reg-username').value.trim();
        const fullname = document.getElementById('reg-fullname').value.trim();
        const email = document.getElementById('reg-email').value.trim();
        const password = document.getElementById('reg-password').value;
        const errorEl = document.getElementById('register-error');
        
        errorEl.classList.add('hidden');

        if (!username || !email || !password) {
            errorEl.textContent = 'Please fill in all required fields';
            errorEl.classList.remove('hidden');
            return;
        }

        if (password.length < 4) {
            errorEl.textContent = 'Password must be at least 4 characters';
            errorEl.classList.remove('hidden');
            return;
        }

        const btn = document.getElementById('register-btn');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating account...';

        try {
            const data = await api('/api/auth/register', {
                method: 'POST',
                body: {
                    username,
                    email,
                    password,
                    full_name: fullname,
                    role: this.selectedRole,
                }
            });
            
            AppState.token = data.access_token;
            AppState.user = data.user;
            localStorage.setItem('ai_classroom_token', data.access_token);
            localStorage.setItem('ai_classroom_user', JSON.stringify(data.user));
            
            App.showMainApp();
            App.toast(`Welcome to AI Virtual Classroom, ${data.user.full_name || data.user.username}! 🚀`, 'success');
        } catch(err) {
            errorEl.textContent = err.message || 'Registration failed';
            errorEl.classList.remove('hidden');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-user-plus"></i> Create Account';
        }
    },

    logout() {
        AppState.token = null;
        AppState.user = null;
        localStorage.removeItem('ai_classroom_token');
        localStorage.removeItem('ai_classroom_user');
        App.showAuthPage();
        Auth.showLogin();
    }
};

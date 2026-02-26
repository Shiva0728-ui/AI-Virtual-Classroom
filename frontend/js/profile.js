/* ═══════════════════════════════════════════════════════════════
   Profile Management
   ═══════════════════════════════════════════════════════════════ */

const Profile = {
    selectedAvatar: null,

    load() {
        const user = AppState.user;
        if (!user) return;

        document.getElementById('profile-avatar-display').textContent = user.avatar || '🧑‍🎓';
        document.getElementById('profile-fullname').textContent = user.full_name || user.username;
        document.getElementById('profile-username').textContent = '@' + user.username;
        document.getElementById('profile-email').textContent = user.email || '';
        document.getElementById('profile-role').textContent = user.role || 'student';
        document.getElementById('profile-name-input').value = user.full_name || '';

        this.selectedAvatar = user.avatar || '🧑‍🎓';

        // Setup avatar picker
        document.querySelectorAll('.avatar-option').forEach(opt => {
            opt.classList.toggle('selected', opt.dataset.avatar === this.selectedAvatar);
            opt.onclick = () => {
                document.querySelectorAll('.avatar-option').forEach(o => o.classList.remove('selected'));
                opt.classList.add('selected');
                Profile.selectedAvatar = opt.dataset.avatar;
            };
        });
    },

    async saveProfile() {
        const fullName = document.getElementById('profile-name-input').value.trim();
        if (!fullName) {
            App.toast('Please enter your name', 'error');
            return;
        }

        try {
            App.loading(true);
            const data = await api('/api/auth/profile', {
                method: 'PUT',
                body: { full_name: fullName, avatar: this.selectedAvatar }
            });

            // Update local state
            AppState.user.full_name = fullName;
            AppState.user.avatar = this.selectedAvatar;
            localStorage.setItem('ai_classroom_user', JSON.stringify(AppState.user));

            App.updateSidebar();
            this.load();
            App.toast('Profile updated!', 'success');
        } catch (e) {
            App.toast(e.message || 'Failed to update profile', 'error');
        } finally {
            App.loading(false);
        }
    },

    async changePassword() {
        const current = document.getElementById('profile-current-pw').value;
        const newPw = document.getElementById('profile-new-pw').value;
        const confirm = document.getElementById('profile-confirm-pw').value;

        if (!current || !newPw || !confirm) {
            App.toast('Please fill all password fields', 'error');
            return;
        }
        if (newPw !== confirm) {
            App.toast('New passwords do not match', 'error');
            return;
        }
        if (newPw.length < 4) {
            App.toast('Password must be at least 4 characters', 'error');
            return;
        }

        try {
            App.loading(true);
            await api('/api/auth/change-password', {
                method: 'PUT',
                body: { current_password: current, new_password: newPw }
            });

            document.getElementById('profile-current-pw').value = '';
            document.getElementById('profile-new-pw').value = '';
            document.getElementById('profile-confirm-pw').value = '';
            App.toast('Password changed successfully!', 'success');
        } catch (e) {
            App.toast(e.message || 'Failed to change password', 'error');
        } finally {
            App.loading(false);
        }
    }
};

/**
 * TrendCommerce AI - Authentication Controller
 * Integra os formulários de Login, Cadastro e Recuperação com a API FastAPI.
 */

document.addEventListener('DOMContentLoaded', () => {
    const authState = {
        currentView: 'login',
        recoveryEmail: '',
        generatedCode: '1234'
    };

    // Referências do DOM
    const authSection = document.getElementById('authSection');
    const dashboardSection = document.getElementById('dashboardSection');

    const formLogin = document.getElementById('formLogin');
    const formRegister = document.getElementById('formRegister');
    const formRecoveryStep1 = document.getElementById('formRecoveryStep1');
    const formRecoveryStep2 = document.getElementById('formRecoveryStep2');
    const formRecoveryStep3 = document.getElementById('formRecoveryStep3');

    const sideLogin = document.getElementById('side-login');
    const sideRegister = document.getElementById('side-register');
    const sideRecovery = document.getElementById('side-recovery');

    const btnGoToRegister = document.getElementById('btnGoToRegister');
    const btnGoToLogin = document.getElementById('btnGoToLogin');
    const linkForgotPassword = document.getElementById('linkForgotPassword');
    const btnRecoveryBackToLogin = document.getElementById('btnRecoveryBackToLogin');
    const btnResendCode = document.getElementById('btnResendCode');

    const otpInputs = [
        document.getElementById('otp1'),
        document.getElementById('otp2'),
        document.getElementById('otp3'),
        document.getElementById('otp4')
    ];

    // Verificar se usuário já está logado
    const existingToken = window.api.getToken();
    const existingUser = window.api.getUser();
    if (existingToken && existingUser) {
        showDashboard(existingUser);
    }

    // ==========================================
    // Alternância de Telas
    // ==========================================
    window.switchAuthView = function(targetView) {
        authState.currentView = targetView;
        document.querySelectorAll('.field-error').forEach(el => el.textContent = '');

        [formLogin, formRegister, formRecoveryStep1, formRecoveryStep2, formRecoveryStep3].forEach(v => {
            if (v) v.classList.remove('active');
        });

        [sideLogin, sideRegister, sideRecovery].forEach(s => {
            if (s) s.classList.remove('active');
        });

        switch (targetView) {
            case 'login':
                if (formLogin) formLogin.classList.add('active');
                if (sideLogin) sideLogin.classList.add('active');
                break;
            case 'register':
                if (formRegister) formRegister.classList.add('active');
                if (sideRegister) sideRegister.classList.add('active');
                break;
            case 'recovery-1':
                if (formRecoveryStep1) formRecoveryStep1.classList.add('active');
                if (sideRecovery) sideRecovery.classList.add('active');
                break;
            case 'recovery-2':
                if (formRecoveryStep2) formRecoveryStep2.classList.add('active');
                if (sideRecovery) sideRecovery.classList.add('active');
                clearOtp();
                setTimeout(() => otpInputs[0] && otpInputs[0].focus(), 100);
                break;
            case 'recovery-3':
                if (formRecoveryStep3) formRecoveryStep3.classList.add('active');
                if (sideRecovery) sideRecovery.classList.add('active');
                break;
        }
    };

    if (btnGoToRegister) btnGoToRegister.addEventListener('click', () => window.switchAuthView('register'));
    if (btnGoToLogin) btnGoToLogin.addEventListener('click', () => window.switchAuthView('login'));
    if (linkForgotPassword) linkForgotPassword.addEventListener('click', () => window.switchAuthView('recovery-1'));
    if (btnRecoveryBackToLogin) btnRecoveryBackToLogin.addEventListener('click', () => window.switchAuthView('login'));

    // ==========================================
    // Mostrar/Ocultar Senha
    // ==========================================
    document.querySelectorAll('.btn-toggle-pass').forEach(button => {
        button.addEventListener('click', () => {
            const targetId = button.getAttribute('data-target');
            const targetInput = document.getElementById(targetId);
            const eyeIcon = button.querySelector('.eye-icon');
            const eyeOffIcon = button.querySelector('.eye-off-icon');

            if (targetInput.type === 'password') {
                targetInput.type = 'text';
                if (eyeIcon) eyeIcon.classList.add('hidden');
                if (eyeOffIcon) eyeOffIcon.classList.remove('hidden');
            } else {
                targetInput.type = 'password';
                if (eyeIcon) eyeIcon.classList.remove('hidden');
                if (eyeOffIcon) eyeOffIcon.classList.add('hidden');
            }
        });
    });

    // ==========================================
    // OTP 4 Dígitos
    // ==========================================
    function clearOtp() {
        otpInputs.forEach(input => { if (input) input.value = ''; });
    }

    otpInputs.forEach((input, index) => {
        if (!input) return;
        input.addEventListener('input', (e) => {
            const val = e.target.value.replace(/\D/g, '');
            e.target.value = val;
            if (val && index < otpInputs.length - 1 && otpInputs[index + 1]) {
                otpInputs[index + 1].focus();
            }
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && !input.value && index > 0 && otpInputs[index - 1]) {
                otpInputs[index - 1].focus();
            }
        });

        input.addEventListener('paste', (e) => {
            e.preventDefault();
            const pasted = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '');
            if (pasted) {
                const chars = pasted.split('').slice(0, 4);
                chars.forEach((char, i) => {
                    if (otpInputs[i]) otpInputs[i].value = char;
                });
                const nextIndex = Math.min(chars.length, 3);
                if (otpInputs[nextIndex]) otpInputs[nextIndex].focus();
            }
        });
    });

    if (btnResendCode) {
        btnResendCode.addEventListener('click', async () => {
            if (!authState.recoveryEmail) {
                window.showToast('Informe seu email primeiro.', 'error');
                return;
            }
            try {
                const res = await window.api.auth.forgotPassword(authState.recoveryEmail);
                window.showToast(res.message, 'info', 6000);
                clearOtp();
                if (otpInputs[0]) otpInputs[0].focus();
            } catch (err) {
                window.showToast(err.message, 'error');
            }
        });
    }

    // ==========================================
    // SUBMIT: LOGIN
    // ==========================================
    if (formLogin) {
        formLogin.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('loginEmail').value.trim();
            const password = document.getElementById('loginPassword').value;
            const emailErr = document.getElementById('loginEmailError');
            const passErr = document.getElementById('loginPasswordError');

            emailErr.textContent = '';
            passErr.textContent = '';

            if (!email) {
                emailErr.textContent = 'Informe seu email.';
                return;
            }
            if (!password) {
                passErr.textContent = 'Informe sua senha.';
                return;
            }

            setLoading('btnSubmitLogin', true);

            try {
                const response = await window.api.auth.login(email, password);
                window.showToast(`Bem-vindo, ${response.user.email}!`, 'success');
                showDashboard(response.user);
            } catch (err) {
                passErr.textContent = err.message || 'Email ou senha incorretos.';
                window.showToast(err.message || 'Falha ao autenticar.', 'error');
            } finally {
                setLoading('btnSubmitLogin', false);
            }
        });
    }

    // ==========================================
    // SUBMIT: CADASTRO
    // ==========================================
    if (formRegister) {
        formRegister.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('registerEmail').value.trim();
            const password = document.getElementById('registerPassword').value;
            const confirmPassword = document.getElementById('registerConfirmPassword').value;

            const emailErr = document.getElementById('registerEmailError');
            const passErr = document.getElementById('registerPasswordError');
            const confirmErr = document.getElementById('registerConfirmPasswordError');

            emailErr.textContent = '';
            passErr.textContent = '';
            confirmErr.textContent = '';

            if (!email) {
                emailErr.textContent = 'Informe um email.';
                return;
            }
            if (password.length < 6) {
                passErr.textContent = 'Mínimo de 6 caracteres.';
                return;
            }
            if (password !== confirmPassword) {
                confirmErr.textContent = 'As senhas não conferem.';
                return;
            }

            setLoading('btnSubmitRegister', true);

            try {
                await window.api.auth.register(email, password);
                window.showToast('Cadastro realizado com sucesso! Conecte-se.', 'success');
                document.getElementById('loginEmail').value = email;
                document.getElementById('loginPassword').value = '';
                formRegister.reset();
                window.switchAuthView('login');
            } catch (err) {
                emailErr.textContent = err.message || 'Erro ao cadastrar.';
                window.showToast(err.message, 'error');
            } finally {
                setLoading('btnSubmitRegister', false);
            }
        });
    }

    // ==========================================
    // SUBMIT: RECUPERAÇÃO ETAPA 1
    // ==========================================
    if (formRecoveryStep1) {
        formRecoveryStep1.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('recoveryEmail').value.trim();
            const emailErr = document.getElementById('recoveryEmailError');
            emailErr.textContent = '';

            if (!email) {
                emailErr.textContent = 'Informe seu email.';
                return;
            }

            setLoading('btnSubmitRecoveryEmail', true);

            try {
                const res = await window.api.auth.forgotPassword(email);
                authState.recoveryEmail = email;
                window.showToast(res.message, 'success', 7000);
                window.switchAuthView('recovery-2');
            } catch (err) {
                emailErr.textContent = err.message || 'Email não encontrado.';
                window.showToast(err.message, 'error');
            } finally {
                setLoading('btnSubmitRecoveryEmail', false);
            }
        });
    }

    // ==========================================
    // SUBMIT: RECUPERAÇÃO ETAPA 2 (OTP)
    // ==========================================
    if (formRecoveryStep2) {
        formRecoveryStep2.addEventListener('submit', (e) => {
            e.preventDefault();
            const code = otpInputs.map(i => i.value).join('');
            const otpErr = document.getElementById('otpError');
            otpErr.textContent = '';

            if (code.length < 4) {
                otpErr.textContent = 'Preencha todos os 4 dígitos.';
                return;
            }

            authState.enteredCode = code;
            window.showToast('Código informado. Defina sua nova senha.', 'success');
            window.switchAuthView('recovery-3');
        });
    }

    // ==========================================
    // SUBMIT: RECUPERAÇÃO ETAPA 3 (NOVA SENHA)
    // ==========================================
    if (formRecoveryStep3) {
        formRecoveryStep3.addEventListener('submit', async (e) => {
            e.preventDefault();
            const newPassword = document.getElementById('newPassword').value;
            const confirmNewPassword = document.getElementById('confirmNewPassword').value;
            const newPassErr = document.getElementById('newPasswordError');
            const confirmErr = document.getElementById('confirmNewPasswordError');

            newPassErr.textContent = '';
            confirmErr.textContent = '';

            if (newPassword.length < 6) {
                newPassErr.textContent = 'Mínimo de 6 caracteres.';
                return;
            }
            if (newPassword !== confirmNewPassword) {
                confirmErr.textContent = 'As senhas não coincidem.';
                return;
            }

            setLoading('btnSubmitNewPassword', true);

            try {
                const res = await window.api.auth.resetPassword(
                    authState.recoveryEmail,
                    authState.enteredCode || '1234',
                    newPassword
                );
                window.showToast(res.message, 'success');
                document.getElementById('loginEmail').value = authState.recoveryEmail;
                document.getElementById('loginPassword').value = '';
                formRecoveryStep3.reset();
                window.switchAuthView('login');
            } catch (err) {
                newPassErr.textContent = err.message;
                window.showToast(err.message, 'error');
            } finally {
                setLoading('btnSubmitNewPassword', false);
            }
        });
    }

    // ==========================================
    // Transição para Dashboard
    // ==========================================
    function showDashboard(user) {
        if (authSection) authSection.classList.add('hidden');
        if (dashboardSection) {
            dashboardSection.classList.remove('hidden');
            if (window.initDashboard) {
                window.initDashboard(user);
            }
        }
    }

    window.logoutToAuth = function() {
        window.api.auth.logout();
        if (dashboardSection) dashboardSection.classList.add('hidden');
        if (authSection) {
            authSection.classList.remove('hidden');
            window.switchAuthView('login');
        }
        window.showToast('Sessão encerrada.', 'info');
    };

    function setLoading(btnId, isLoading) {
        const btn = document.getElementById(btnId);
        if (!btn) return;
        const txt = btn.querySelector('.btn-text');
        const sp = btn.querySelector('.btn-spinner');
        btn.disabled = isLoading;
        if (txt) txt.classList.toggle('hidden', isLoading);
        if (sp) sp.classList.toggle('hidden', !isLoading);
    }
});

// Toast Global
window.showToast = function(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type === 'error' ? 'toast-error' : type === 'success' ? 'toast-success' : ''}`;

    let icon = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    if (type === 'success') {
        icon = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    } else if (type === 'error') {
        icon = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#ff4d6d" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
    }

    toast.innerHTML = `${icon}<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
};
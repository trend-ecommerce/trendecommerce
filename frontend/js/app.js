/**
 * TrendEcommerce AI - Frontend Authentication Logic
 * Supports all 5 states:
 * 1. Login (Bem-vindo de volta)
 * 2. Register (Acesse sua conta / Cadastrar)
 * 3. Recovery Step 1 (Enviaremos um código para seu email)
 * 4. Recovery Step 2 (Digite seu código de 4 dígitos)
 * 5. Recovery Step 3 (Redefinir nova senha)
 * + Success state / session preview
 */

document.addEventListener('DOMContentLoaded', () => {
    // ==========================================
    // State & DOM Elements
    // ==========================================
    const state = {
        currentView: 'login', // 'login' | 'register' | 'recovery-1' | 'recovery-2' | 'recovery-3' | 'success'
        recoveryEmail: '',
        generatedCode: '1234', // Simulated OTP
        authenticatedUser: null
    };

    // Forms
    const formLogin = document.getElementById('formLogin');
    const formRegister = document.getElementById('formRegister');
    const formRecoveryStep1 = document.getElementById('formRecoveryStep1');
    const formRecoveryStep2 = document.getElementById('formRecoveryStep2');
    const formRecoveryStep3 = document.getElementById('formRecoveryStep3');
    const authSuccessView = document.getElementById('authSuccessView');

    // Side contents
    const sideLogin = document.getElementById('side-login');
    const sideRegister = document.getElementById('side-register');
    const sideRecovery = document.getElementById('side-recovery');

    // Navigation Triggers
    const btnGoToRegister = document.getElementById('btnGoToRegister');
    const btnGoToLogin = document.getElementById('btnGoToLogin');
    const linkForgotPassword = document.getElementById('linkForgotPassword');
    const btnRecoveryBackToLogin = document.getElementById('btnRecoveryBackToLogin');
    const btnResendCode = document.getElementById('btnResendCode');
    const btnLogout = document.getElementById('btnLogout');

    // OTP Inputs
    const otpInputs = [
        document.getElementById('otp1'),
        document.getElementById('otp2'),
        document.getElementById('otp3'),
        document.getElementById('otp4')
    ];

    // ==========================================
    // Initial Local Mock DB Setup
    // ==========================================
    function initUserDatabase() {
        if (!localStorage.getItem('trendecommerce_users')) {
            const initialUsers = [
                { email: 'admin@trendecommerce.com', password: 'admin123', name: 'Administrador' },
                { email: 'teste@exemplo.com', password: 'senha123', name: 'Usuário Teste' }
            ];
            localStorage.setItem('trendecommerce_users', JSON.stringify(initialUsers));
        }
    }
    initUserDatabase();

    function getUsers() {
        return JSON.parse(localStorage.getItem('trendecommerce_users') || '[]');
    }

    function saveUsers(users) {
        localStorage.setItem('trendecommerce_users', JSON.stringify(users));
    }

    // ==========================================
    // View Switcher Function
    // ==========================================
    function switchView(targetView) {
        state.currentView = targetView;

        // Reset errors
        document.querySelectorAll('.field-error').forEach(el => el.textContent = '');

        // Hide all forms and success view
        [formLogin, formRegister, formRecoveryStep1, formRecoveryStep2, formRecoveryStep3, authSuccessView].forEach(view => {
            view.classList.remove('active');
        });

        // Hide all side contents
        [sideLogin, sideRegister, sideRecovery].forEach(side => {
            side.classList.remove('active');
        });

        switch (targetView) {
            case 'login':
                formLogin.classList.add('active');
                sideLogin.classList.add('active');
                break;
            case 'register':
                formRegister.classList.add('active');
                sideRegister.classList.add('active');
                break;
            case 'recovery-1':
                formRecoveryStep1.classList.add('active');
                sideRecovery.classList.add('active');
                break;
            case 'recovery-2':
                formRecoveryStep2.classList.add('active');
                sideRecovery.classList.add('active');
                clearOtpInputs();
                setTimeout(() => otpInputs[0].focus(), 100);
                break;
            case 'recovery-3':
                formRecoveryStep3.classList.add('active');
                sideRecovery.classList.add('active');
                break;
            case 'success':
                authSuccessView.classList.add('active');
                sideLogin.classList.add('active');
                if (state.authenticatedUser) {
                    document.getElementById('loggedUserEmail').textContent = state.authenticatedUser.email;
                }
                break;
        }
    }

    // ==========================================
    // Navigation Events
    // ==========================================
    btnGoToRegister.addEventListener('click', () => switchView('register'));
    btnGoToLogin.addEventListener('click', () => switchView('login'));
    linkForgotPassword.addEventListener('click', () => switchView('recovery-1'));
    btnRecoveryBackToLogin.addEventListener('click', () => switchView('login'));
    btnLogout.addEventListener('click', () => {
        state.authenticatedUser = null;
        showToast('Sessão encerrada com sucesso.', 'info');
        switchView('login');
    });

    // ==========================================
    // Password Show/Hide Toggle
    // ==========================================
    document.querySelectorAll('.btn-toggle-pass').forEach(button => {
        button.addEventListener('click', () => {
            const targetId = button.getAttribute('data-target');
            const targetInput = document.getElementById(targetId);
            const eyeIcon = button.querySelector('.eye-icon');
            const eyeOffIcon = button.querySelector('.eye-off-icon');

            if (targetInput.type === 'password') {
                targetInput.type = 'text';
                eyeIcon.classList.add('hidden');
                eyeOffIcon.classList.remove('hidden');
            } else {
                targetInput.type = 'password';
                eyeIcon.classList.remove('hidden');
                eyeOffIcon.classList.add('hidden');
            }
        });
    });

    // ==========================================
    // OTP 4-Digit Code Handling
    // ==========================================
    function clearOtpInputs() {
        otpInputs.forEach(input => input.value = '');
    }

    otpInputs.forEach((input, index) => {
        // Only accept numbers
        input.addEventListener('input', (e) => {
            const val = e.target.value.replace(/\D/g, '');
            e.target.value = val;

            if (val && index < otpInputs.length - 1) {
                otpInputs[index + 1].focus();
            }
        });

        // Backspace to previous
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && !input.value && index > 0) {
                otpInputs[index - 1].focus();
            }
        });

        // Paste support
        input.addEventListener('paste', (e) => {
            e.preventDefault();
            const pasted = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '');
            if (pasted) {
                const chars = pasted.split('').slice(0, 4);
                chars.forEach((char, i) => {
                    if (otpInputs[i]) otpInputs[i].value = char;
                });
                const nextIndex = Math.min(chars.length, 3);
                otpInputs[nextIndex].focus();
            }
        });
    });

    // Resend code simulated action
    btnResendCode.addEventListener('click', () => {
        state.generatedCode = Math.floor(1000 + Math.random() * 9000).toString();
        showToast(`Novo código de 4 dígitos enviado para ${state.recoveryEmail || 'seu email'}: [ ${state.generatedCode} ]`, 'info', 6000);
        clearOtpInputs();
        otpInputs[0].focus();
    });

    // ==========================================
    // Form 1: LOGIN Submission
    // ==========================================
    formLogin.addEventListener('submit', (e) => {
        e.preventDefault();
        const email = document.getElementById('loginEmail').value.trim();
        const password = document.getElementById('loginPassword').value;
        const emailErr = document.getElementById('loginEmailError');
        const passErr = document.getElementById('loginPasswordError');

        emailErr.textContent = '';
        passErr.textContent = '';

        if (!validateEmail(email)) {
            emailErr.textContent = 'Por favor, informe um email válido.';
            return;
        }

        if (!password) {
            passErr.textContent = 'Por favor, informe sua senha.';
            return;
        }

        // Simulate request
        setButtonLoading('btnSubmitLogin', true);

        setTimeout(() => {
            setButtonLoading('btnSubmitLogin', false);
            const users = getUsers();
            const user = users.find(u => u.email.toLowerCase() === email.toLowerCase() && u.password === password);

            if (user) {
                state.authenticatedUser = user;
                showToast(`Bem-vindo, ${user.email}!`, 'success');
                switchView('success');
            } else {
                passErr.textContent = 'Email ou senha incorretos.';
                showToast('Falha na autenticação. Verifique os dados.', 'error');
            }
        }, 600);
    });

    // ==========================================
    // Form 2: CADASTRO (REGISTER) Submission
    // ==========================================
    formRegister.addEventListener('submit', (e) => {
        e.preventDefault();
        const email = document.getElementById('registerEmail').value.trim();
        const password = document.getElementById('registerPassword').value;
        const confirmPassword = document.getElementById('registerConfirmPassword').value;

        const emailErr = document.getElementById('registerEmailError');
        const passErr = document.getElementById('registerPasswordError');
        const confirmPassErr = document.getElementById('registerConfirmPasswordError');

        emailErr.textContent = '';
        passErr.textContent = '';
        confirmPassErr.textContent = '';

        if (!validateEmail(email)) {
            emailErr.textContent = 'Email inválido.';
            return;
        }

        if (password.length < 6) {
            passErr.textContent = 'A senha deve conter no mínimo 6 caracteres.';
            return;
        }

        if (password !== confirmPassword) {
            confirmPassErr.textContent = 'As senhas não coincidem.';
            return;
        }

        const users = getUsers();
        if (users.some(u => u.email.toLowerCase() === email.toLowerCase())) {
            emailErr.textContent = 'Este email já está cadastrado.';
            return;
        }

        setButtonLoading('btnSubmitRegister', true);

        setTimeout(() => {
            setButtonLoading('btnSubmitRegister', false);
            users.push({ email, password, name: email.split('@')[0] });
            saveUsers(users);

            showToast('Cadastro realizado com sucesso! Faça login para continuar.', 'success');
            document.getElementById('loginEmail').value = email;
            document.getElementById('loginPassword').value = '';
            formRegister.reset();
            switchView('login');
        }, 700);
    });

    // ==========================================
    // Form 3: RECOVERY STEP 1 (Email)
    // ==========================================
    formRecoveryStep1.addEventListener('submit', (e) => {
        e.preventDefault();
        const email = document.getElementById('recoveryEmail').value.trim();
        const emailErr = document.getElementById('recoveryEmailError');
        emailErr.textContent = '';

        if (!validateEmail(email)) {
            emailErr.textContent = 'Informe um email válido.';
            return;
        }

        const users = getUsers();
        const userExists = users.some(u => u.email.toLowerCase() === email.toLowerCase());

        setButtonLoading('btnSubmitRecoveryEmail', true);

        setTimeout(() => {
            setButtonLoading('btnSubmitRecoveryEmail', false);
            if (!userExists) {
                emailErr.textContent = 'Nenhuma conta encontrada com este email.';
                return;
            }

            state.recoveryEmail = email;
            state.generatedCode = Math.floor(1000 + Math.random() * 9000).toString();
            showToast(`Código de validação enviado: [ ${state.generatedCode} ]`, 'success', 7000);
            switchView('recovery-2');
        }, 600);
    });

    // ==========================================
    // Form 4: RECOVERY STEP 2 (OTP)
    // ==========================================
    formRecoveryStep2.addEventListener('submit', (e) => {
        e.preventDefault();
        const enteredCode = otpInputs.map(i => i.value).join('');
        const otpError = document.getElementById('otpError');
        otpError.textContent = '';

        if (enteredCode.length < 4) {
            otpError.textContent = 'Digite todos os 4 dígitos do código.';
            return;
        }

        setButtonLoading('btnSubmitOtp', true);

        setTimeout(() => {
            setButtonLoading('btnSubmitOtp', false);
            if (enteredCode === state.generatedCode || enteredCode === '1234') {
                showToast('Código validado! Defina sua nova senha.', 'success');
                switchView('recovery-3');
            } else {
                otpError.textContent = 'Código incorreto. Tente novamente ou reenvie.';
                showToast('Código de verificação inválido.', 'error');
            }
        }, 600);
    });

    // ==========================================
    // Form 5: RECOVERY STEP 3 (Nova Senha)
    // ==========================================
    formRecoveryStep3.addEventListener('submit', (e) => {
        e.preventDefault();
        const newPassword = document.getElementById('newPassword').value;
        const confirmNewPassword = document.getElementById('confirmNewPassword').value;

        const newPassErr = document.getElementById('newPasswordError');
        const confirmPassErr = document.getElementById('confirmNewPasswordError');

        newPassErr.textContent = '';
        confirmPassErr.textContent = '';

        if (newPassword.length < 6) {
            newPassErr.textContent = 'A senha deve ter pelo menos 6 caracteres.';
            return;
        }

        if (newPassword !== confirmNewPassword) {
            confirmPassErr.textContent = 'As senhas não coincidem.';
            return;
        }

        setButtonLoading('btnSubmitNewPassword', true);

        setTimeout(() => {
            setButtonLoading('btnSubmitNewPassword', false);
            const users = getUsers();
            const userIndex = users.findIndex(u => u.email.toLowerCase() === state.recoveryEmail.toLowerCase());

            if (userIndex !== -1) {
                users[userIndex].password = newPassword;
                saveUsers(users);
            }

            showToast('Senha redefinida com sucesso! Você já pode entrar.', 'success');
            document.getElementById('loginEmail').value = state.recoveryEmail;
            document.getElementById('loginPassword').value = '';
            formRecoveryStep3.reset();
            switchView('login');
        }, 700);
    });

    // ==========================================
    // Utilities: Email Validation & UI Helpers
    // ==========================================
    function validateEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    function setButtonLoading(buttonId, isLoading) {
        const btn = document.getElementById(buttonId);
        if (!btn) return;
        const text = btn.querySelector('.btn-text');
        const spinner = btn.querySelector('.btn-spinner');

        if (isLoading) {
            btn.disabled = true;
            if (text) text.classList.add('hidden');
            if (spinner) spinner.classList.remove('hidden');
        } else {
            btn.disabled = false;
            if (text) text.classList.remove('hidden');
            if (spinner) spinner.classList.add('hidden');
        }
    }

    function showToast(message, type = 'info', duration = 4000) {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type === 'error' ? 'toast-error' : type === 'success' ? 'toast-success' : ''}`;

        let iconSvg = '';
        if (type === 'success') {
            iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
        } else if (type === 'error') {
            iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#ff4d6d" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
        } else {
            iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
        }

        toast.innerHTML = `${iconSvg}<span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-10px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    // ==========================================
    // Interactive Futuristic Background Canvas
    // ==========================================
    const canvas = document.getElementById('circuit-canvas');
    if (canvas) {
        const ctx = canvas.getContext('2d');
        let width, height;
        let particles = [];

        function resize() {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
        }
        window.addEventListener('resize', resize);
        resize();

        class Particle {
            constructor() {
                this.reset();
            }

            reset() {
                this.x = Math.random() * width;
                this.y = Math.random() * height;
                this.size = Math.random() * 2 + 1;
                this.speedX = (Math.random() - 0.5) * 0.4;
                this.speedY = (Math.random() - 0.5) * 0.4;
                this.opacity = Math.random() * 0.5 + 0.2;
                this.hue = Math.random() > 0.5 ? 190 : 210;
            }

            update() {
                this.x += this.speedX;
                this.y += this.speedY;

                if (this.x < 0 || this.x > width || this.y < 0 || this.y > height) {
                    this.reset();
                }
            }

            draw() {
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
                ctx.fillStyle = `hsla(${this.hue}, 100%, 50%, ${this.opacity})`;
                ctx.shadowBlur = 8;
                ctx.shadowColor = `hsl(${this.hue}, 100%, 50%)`;
                ctx.fill();
                ctx.shadowBlur = 0;
            }
        }

        for (let i = 0; i < 45; i++) {
            particles.push(new Particle());
        }

        function animateCanvas() {
            ctx.clearRect(0, 0, width, height);

            // Draw connecting lines if close
            for (let i = 0; i < particles.length; i++) {
                particles[i].update();
                particles[i].draw();

                for (let j = i + 1; j < particles.length; j++) {
                    const dx = particles[i].x - particles[j].x;
                    const dy = particles[i].y - particles[j].y;
                    const dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist < 120) {
                        ctx.beginPath();
                        ctx.moveTo(particles[i].x, particles[i].y);
                        ctx.lineTo(particles[j].x, particles[j].y);
                        ctx.strokeStyle = `rgba(0, 180, 216, ${0.15 * (1 - dist / 120)})`;
                        ctx.lineWidth = 1;
                        ctx.stroke();
                    }
                }
            }

            requestAnimationFrame(animateCanvas);
        }
        animateCanvas();
    }
});
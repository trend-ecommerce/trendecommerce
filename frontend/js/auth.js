/**
 * TrendCommerce AI - Multi-Page Auth Controller
 * Gerencia formulários em login.html, cadastro.html, recuperar-senha.html,
 * codigo-verificacao.html e nova-senha.html.
 */

document.addEventListener('DOMContentLoaded', () => {
    setupPasswordToggles();
    setupLoginForm();
    setupRegisterForm();
    setupRecoveryStep1();
    setupRecoveryStep2();
    setupRecoveryStep3();
});

function setupPasswordToggles() {
    document.querySelectorAll('.password-container').forEach(container => {
        const input = container.querySelector('input');
        const btn = container.querySelector('button');
        if (input && btn) {
            btn.onclick = (e) => {
                e.preventDefault();
                const isPass = input.type === 'password';
                input.type = isPass ? 'text' : 'password';
                const icon = btn.querySelector('i');
                if (icon) {
                    icon.className = isPass ? 'ph ph-eye-slash' : 'ph ph-eye';
                }
            };
        }
    });
}

// 1. Login
function setupLoginForm() {
    const form = document.getElementById('formLogin');
    if (!form) return;

    const emailInput = document.getElementById('loginEmail');
    const passInput = document.getElementById('loginPassword');
    const submitBtn = document.getElementById('btnLoginSubmit');
    const emailErr = document.getElementById('loginEmailError');
    const passErr = document.getElementById('loginPasswordError');
    const coldStartNotice = document.getElementById('coldStartNotice');

    form.onsubmit = async (e) => {
        e.preventDefault();
        if (emailErr) emailErr.textContent = '';
        if (passErr) passErr.textContent = '';

        const email = (emailInput?.value || '').trim();
        const password = passInput?.value || '';

        let hasError = false;
        if (!email) {
            if (emailErr) emailErr.textContent = 'Informe seu email.';
            hasError = true;
        }
        if (!password) {
            if (passErr) passErr.textContent = 'Informe sua senha.';
            hasError = true;
        }
        if (hasError) return;

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="login-spinner"></span>';
        if (coldStartNotice) coldStartNotice.style.display = 'none';

        const timer = setTimeout(() => {
            if (coldStartNotice) coldStartNotice.style.display = 'block';
        }, 3500);

        try {
            const data = await window.apiService.auth.login(email, password);
            clearTimeout(timer);
            window.showToast?.(`Bem-vindo, ${data.user.email}!`, 'success');
            setTimeout(() => {
                window.location.replace('ia-preditiva.html');
            }, 600);
        } catch (err) {
            clearTimeout(timer);
            if (coldStartNotice) coldStartNotice.style.display = 'none';
            if (passErr) passErr.textContent = err.message || 'Email ou senha incorretos.';
            window.showToast?.(err.message || 'Falha ao autenticar.', 'error');
        } finally {
            clearTimeout(timer);
            submitBtn.disabled = false;
            submitBtn.textContent = 'ENTRAR';
        }
    };
}

// 2. Cadastro
function setupRegisterForm() {
    const form = document.getElementById('formRegister');
    if (!form) return;

    const emailInput = document.getElementById('registerEmail');
    const passInput = document.getElementById('registerPassword');
    const confirmInput = document.getElementById('registerConfirmPassword');
    const submitBtn = document.getElementById('btnRegisterSubmit');
    const emailErr = document.getElementById('registerEmailError');
    const passErr = document.getElementById('registerPasswordError');
    const confirmErr = document.getElementById('registerConfirmPasswordError');

    form.onsubmit = async (e) => {
        e.preventDefault();
        if (emailErr) emailErr.textContent = '';
        if (passErr) passErr.textContent = '';
        if (confirmErr) confirmErr.textContent = '';

        const email = (emailInput?.value || '').trim();
        const password = passInput?.value || '';
        const confirm = confirmInput?.value || '';

        let hasError = false;
        if (!email) {
            if (emailErr) emailErr.textContent = 'Informe um email válido.';
            hasError = true;
        }
        if (password.length < 6) {
            if (passErr) passErr.textContent = 'A senha deve ter no mínimo 6 caracteres.';
            hasError = true;
        }
        if (password !== confirm) {
            if (confirmErr) confirmErr.textContent = 'As senhas não coincidem.';
            hasError = true;
        }
        if (hasError) return;

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="login-spinner"></span>';

        try {
            await window.apiService.auth.register(email, password);
            window.showToast?.('Cadastro realizado com sucesso! Redirecionando para login...', 'success');
            setTimeout(() => {
                window.location.replace('login.html');
            }, 1000);
        } catch (err) {
            if (emailErr) emailErr.textContent = err.message || 'Erro ao realizar cadastro.';
            window.showToast?.(err.message || 'Erro ao cadastrar.', 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'CADASTRAR';
        }
    };
}

// 3. Recuperação - Etapa 1
function setupRecoveryStep1() {
    const form = document.getElementById('formRecoveryStep1');
    if (!form) return;

    const emailInput = document.getElementById('recoveryEmailStep1');
    const submitBtn = document.getElementById('btnRecoveryStep1Submit');
    const errEl = document.getElementById('recoveryStep1Error');

    form.onsubmit = async (e) => {
        e.preventDefault();
        if (errEl) errEl.textContent = '';
        const email = (emailInput?.value || '').trim();
        if (!email) {
            if (errEl) errEl.textContent = 'Informe seu email cadastrado.';
            return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="login-spinner"></span>';

        try {
            const res = await window.apiService.auth.forgotPassword(email);
            sessionStorage.setItem('recovery_email', email);
            window.showToast?.(res.message, 'success', 5000);
            setTimeout(() => {
                window.location.href = 'codigo-verificacao.html';
            }, 800);
        } catch (err) {
            if (errEl) errEl.textContent = err.message || 'Email não encontrado.';
            window.showToast?.(err.message || 'Erro ao enviar código.', 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'ENVIAR';
        }
    };
}

// 4. Recuperação - Etapa 2
function setupRecoveryStep2() {
    const form = document.getElementById('formRecoveryStep2');
    if (!form) return;

    const otpInputs = [
        document.getElementById('otp1'),
        document.getElementById('otp2'),
        document.getElementById('otp3'),
        document.getElementById('otp4')
    ];
    const errEl = document.getElementById('recoveryStep2Error');
    const resendBtn = document.getElementById('btnRecoveryResend');
    const recoveryEmail = sessionStorage.getItem('recovery_email') || '';

    if (otpInputs[0]) otpInputs[0].focus();

    otpInputs.forEach((inp, idx) => {
        if (!inp) return;
        inp.oninput = (e) => {
            const cleanVal = e.target.value.replace(/\D/g, '');
            inp.value = cleanVal ? cleanVal[0] : '';
            if (cleanVal && idx < 3 && otpInputs[idx + 1]) {
                otpInputs[idx + 1].focus();
            }
        };

        inp.onkeydown = (e) => {
            if (e.key === 'Backspace' && !inp.value && idx > 0 && otpInputs[idx - 1]) {
                otpInputs[idx - 1].focus();
            }
        };

        inp.onpaste = (e) => {
            e.preventDefault();
            const pasted = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '').slice(0, 4);
            if (pasted) {
                for (let i = 0; i < pasted.length; i++) {
                    if (otpInputs[i]) otpInputs[i].value = pasted[i];
                }
                const nextIdx = Math.min(pasted.length, 3);
                if (otpInputs[nextIdx]) otpInputs[nextIdx].focus();
            }
        };
    });

    if (resendBtn) {
        resendBtn.onclick = async () => {
            if (!recoveryEmail) {
                window.showToast?.('Email não identificado. Reinicie a recuperação.', 'error');
                return;
            }
            try {
                const res = await window.apiService.auth.forgotPassword(recoveryEmail);
                window.showToast?.(res.message, 'info', 5000);
                otpInputs.forEach(i => { if (i) i.value = ''; });
                if (otpInputs[0]) otpInputs[0].focus();
            } catch (err) {
                window.showToast?.(err.message, 'error');
            }
        };
    }

    form.onsubmit = (e) => {
        e.preventDefault();
        if (errEl) errEl.textContent = '';
        const code = otpInputs.map(i => i?.value || '').join('');
        if (code.length < 4) {
            if (errEl) errEl.textContent = 'Digite os 4 dígitos do código de verificação.';
            return;
        }

        sessionStorage.setItem('recovery_code', code);
        window.showToast?.('Código confirmado! Defina sua nova senha.', 'success');
        setTimeout(() => {
            window.location.href = 'nova-senha.html';
        }, 600);
    };
}

// 5. Recuperação - Etapa 3
function setupRecoveryStep3() {
    const form = document.getElementById('formRecoveryStep3');
    if (!form) return;

    const emailInput = document.getElementById('recoveryEmailStep3');
    const passInput = document.getElementById('recoveryNewPassword');
    const confirmInput = document.getElementById('recoveryConfirmNewPassword');
    const submitBtn = document.getElementById('btnRecoveryStep3Submit');
    const passErr = document.getElementById('recoveryNewPassError');
    const confirmErr = document.getElementById('recoveryConfirmPassError');

    const storedEmail = sessionStorage.getItem('recovery_email') || '';
    const storedCode = sessionStorage.getItem('recovery_code') || '';
    if (emailInput && storedEmail) {
        emailInput.value = storedEmail;
    }

    form.onsubmit = async (e) => {
        e.preventDefault();
        if (passErr) passErr.textContent = '';
        if (confirmErr) confirmErr.textContent = '';

        const email = (emailInput?.value || storedEmail || '').trim();
        const newPass = passInput?.value || '';
        const confirmPass = confirmInput?.value || '';

        let hasError = false;
        if (!email) {
            window.showToast?.('Informe o email.', 'error');
            hasError = true;
        }
        if (newPass.length < 6) {
            if (passErr) passErr.textContent = 'A senha deve ter no mínimo 6 caracteres.';
            hasError = true;
        }
        if (newPass !== confirmPass) {
            if (confirmErr) confirmErr.textContent = 'As senhas não coincidem.';
            hasError = true;
        }
        if (hasError) return;

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="login-spinner"></span>';

        try {
            const res = await window.apiService.auth.resetPassword(email, storedCode, newPass);
            sessionStorage.removeItem('recovery_email');
            sessionStorage.removeItem('recovery_code');
            window.showToast?.(res.message, 'success');
            setTimeout(() => {
                window.location.replace('login.html');
            }, 800);
        } catch (err) {
            if (passErr) passErr.textContent = err.message || 'Erro ao redefinir senha.';
            window.showToast?.(err.message || 'Erro ao redefinir senha.', 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'LOGIN';
        }
    };
}

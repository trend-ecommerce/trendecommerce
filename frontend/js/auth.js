/**
 * TrendCommerce AI - Multi-Page Auth Controller
 * Gerencia formulários em login.html, cadastro.html, recuperar-senha.html,
 * codigo-verificacao.html e nova-senha.html.
 */

const BLOCKED_DOMAINS_CLIENT = new Set([
    'teste.com', 'teste.com.br', 'test.com', 'example.com', 'example.org', 'example.net',
    'falso.com', 'fake.com', 'fakemail.com', 'email.com', 'dominio.com', 'meudominio.com',
    'tempmail.com', 'temp-mail.org', '10minutemail.com', 'mailinator.com', 'yopmail.com',
    'guerrillamail.com', 'sharklasers.com', 'trashmail.com', 'getnada.com', 'maildrop.cc',
    'dispostable.com', 'throwawaymail.com', 'mohmal.com', 'mailnesia.com',
    'gamil.com', 'gmial.com', 'gnail.com', 'gmai.com', 'gmail.co', 'gmail.con',
    'outlok.com', 'outllok.com', 'outlook.co', 'hotmal.com', 'hotmial.com', 'htmail.com',
    'yaho.com', 'yahooo.com'
]);

function validateRealEmailClient(email) {
    const clean = (email || '').trim().toLowerCase();
    if (!clean) {
        return { valid: false, message: 'Informe seu email.' };
    }
    if (clean === 'admin@trendecommerce.com') {
        return { valid: true, message: '' };
    }
    const emailRegex = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;
    if (!emailRegex.test(clean)) {
        return { valid: false, message: 'Formato de email inválido. Digite um email verdadeiro (ex: nome@gmail.com).' };
    }
    const parts = clean.split('@');
    const local = parts[0];
    const domain = parts[1];
    if (local.length < 2 || local.startsWith('.') || local.endsWith('.') || local.includes('..')) {
        return { valid: false, message: 'Endereço de email inválido.' };
    }
    if (BLOCKED_DOMAINS_CLIENT.has(domain)) {
        return { valid: false, message: `O domínio @${domain} não é permitido. Use um email verdadeiro (ex: Gmail, Outlook, Hotmail).` };
    }
    return { valid: true, message: '' };
}

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

    // Criar banner de verificação de e-mail se necessário
    let verifyBanner = document.getElementById('emailVerificationBanner');
    if (!verifyBanner) {
        verifyBanner = document.createElement('div');
        verifyBanner.id = 'emailVerificationBanner';
        verifyBanner.style.cssText = 'display: none; width: 100%; margin-top: 10px; padding: 10px 14px; border-radius: 12px; font-size: 12px; line-height: 1.45; text-align: center;';
        submitBtn.insertAdjacentElement('beforebegin', verifyBanner);
    }

    const showVerificationBanner = (type, htmlContent, targetEmail) => {
        if (!verifyBanner) return;
        verifyBanner.style.display = 'block';
        if (type === 'success') {
            verifyBanner.style.background = 'rgba(16, 185, 129, 0.14)';
            verifyBanner.style.border = '1px solid rgba(16, 185, 129, 0.45)';
            verifyBanner.style.color = '#34d399';
            verifyBanner.innerHTML = htmlContent;
        } else {
            verifyBanner.style.background = 'rgba(0, 212, 255, 0.1)';
            verifyBanner.style.border = '1px solid rgba(0, 212, 255, 0.35)';
            verifyBanner.style.color = '#e0f2fe';
            verifyBanner.innerHTML = `
                <div>${htmlContent}</div>
                ${targetEmail ? `<button type="button" id="btnResendVerifyEmail" style="margin-top: 8px; background: rgba(0, 212, 255, 0.2); border: 1px solid rgba(0, 212, 255, 0.5); color: #00f0ff; border-radius: 999px; padding: 4px 14px; font-size: 11px; font-weight: 700; cursor: pointer;">Reenviar e-mail de confirmação</button>` : ''}
            `;
            const resendBtn = document.getElementById('btnResendVerifyEmail');
            if (resendBtn && targetEmail) {
                resendBtn.onclick = async () => {
                    resendBtn.disabled = true;
                    resendBtn.textContent = 'Enviando...';
                    try {
                        const res = await window.apiService.auth.resendVerification(targetEmail);
                        window.showToast?.(res.message || 'E-mail de confirmação reenviado!', 'success', 5000);
                        resendBtn.textContent = 'E-mail reenviado!';
                    } catch (err) {
                        window.showToast?.(err.message || 'Aguarde alguns instantes para reenviar.', 'warning');
                        resendBtn.disabled = false;
                        resendBtn.textContent = 'Reenviar e-mail de confirmação';
                    }
                };
            }
        }
    };

    const params = new URLSearchParams(window.location.search);
    const hash = window.location.hash || '';
    const pendingEmail = sessionStorage.getItem('pending_verify_email') || '';

    if (pendingEmail && emailInput && !emailInput.value) {
        emailInput.value = pendingEmail;
    }

    if (params.get('verified') === '1' || hash.includes('access_token=')) {
        showVerificationBanner(
            'success',
            '✅ <strong>E-mail confirmado com sucesso!</strong> Sua conta foi ativada. Digite sua senha para entrar.'
        );
        window.showToast?.('E-mail verificado com sucesso! Faça seu login.', 'success', 5000);
    } else if (params.get('pending_verify') === '1' && pendingEmail) {
        showVerificationBanner(
            'info',
            `📧 <strong>Confirme seu e-mail para liberar o login!</strong><br>Enviamos um link de confirmação para <strong>${pendingEmail}</strong>. Verifique sua caixa de entrada e spam.`,
            pendingEmail
        );
    }

    form.onsubmit = async (e) => {
        e.preventDefault();
        if (emailErr) emailErr.textContent = '';
        if (passErr) passErr.textContent = '';

        const email = (emailInput?.value || '').trim();
        const password = passInput?.value || '';

        let hasError = false;
        const emailCheck = validateRealEmailClient(email);
        if (!emailCheck.valid) {
            if (emailErr) emailErr.textContent = emailCheck.message;
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
            sessionStorage.removeItem('pending_verify_email');
            window.showToast?.(`Bem-vindo, ${data.user.email}!`, 'success');
            setTimeout(() => {
                window.location.replace('ia-preditiva.html');
            }, 600);
        } catch (err) {
            clearTimeout(timer);
            if (coldStartNotice) coldStartNotice.style.display = 'none';
            const msg = err.message || 'Email ou senha incorretos.';
            if (msg.toLowerCase().includes('verificado') || msg.toLowerCase().includes('confirmação')) {
                showVerificationBanner(
                    'info',
                    `⚠️ <strong>E-mail ainda não confirmado!</strong><br>${msg}`,
                    email
                );
            } else if (passErr) {
                passErr.textContent = msg;
            }
            window.showToast?.(msg, 'error', 5000);
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
        const emailCheck = validateRealEmailClient(email);
        if (!emailCheck.valid) {
            if (emailErr) emailErr.textContent = emailCheck.message;
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
            sessionStorage.setItem('pending_verify_email', email.toLowerCase());
            window.showToast?.(
                `Enviamos um e-mail de confirmação para ${email}! Confirme na sua caixa de entrada para ativar o login.`,
                'info',
                6000
            );
            setTimeout(() => {
                window.location.replace('login.html?pending_verify=1');
            }, 1400);
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
        const emailCheck = validateRealEmailClient(email);
        if (!emailCheck.valid) {
            if (errEl) errEl.textContent = emailCheck.message;
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

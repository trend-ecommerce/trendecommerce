/**
 * TrendCommerce AI - Multi-Page Auth Controller
 * Gerencia autenticação em login.html, cadastro.html, recuperarsenha.html / recuperar-senha.html,
 * codigosenha.html / codigo-verificacao.html e novasenha.html / nova-senha.html.
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
        if (input && btn && !btn.dataset.toggleInitialized) {
            btn.dataset.toggleInitialized = 'true';
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
    const form = document.getElementById('formLogin') || document.querySelector('.login-right');
    // Apenas executa se for página de login
    const pagePath = window.location.pathname.toLowerCase();
    const isLoginPage = pagePath.endsWith('login.html') || (!pagePath.includes('cadastro') && !pagePath.includes('recuperar') && !pagePath.includes('codigo') && !pagePath.includes('nova') && document.getElementById('formLogin'));
    if (!form || !isLoginPage) return;

    const emailInput = document.getElementById('loginEmail') || form.querySelector('input[type="email"]');
    const passInput = document.getElementById('loginPassword') || document.getElementById('senha') || form.querySelector('input[type="password"]');
    const submitBtn = document.getElementById('btnLoginSubmit') || form.querySelector('.button-right');
    const emailErr = document.getElementById('loginEmailError');
    const passErr = document.getElementById('loginPasswordError');
    const coldStartNotice = document.getElementById('coldStartNotice');

    // Banner simples de verificação de e-mail
    let verifyBanner = document.getElementById('emailVerificationBanner');
    if (!verifyBanner && submitBtn) {
        verifyBanner = document.createElement('div');
        verifyBanner.id = 'emailVerificationBanner';
        submitBtn.insertAdjacentElement('beforebegin', verifyBanner);
    }

    const showVerificationBanner = (type, message) => {
        if (!verifyBanner) return;
        verifyBanner.className = type === 'success' ? 'success' : '';
        verifyBanner.textContent = message;
        verifyBanner.style.display = 'block';
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
            'E-mail confirmado com sucesso! Digite sua senha para entrar.'
        );
    } else if (params.get('pending_verify') === '1' && pendingEmail) {
        showVerificationBanner(
            'info',
            'Confirme seu e-mail para acessar sua conta.'
        );
    }

    form.onsubmit = async (e) => {
        e.preventDefault();
        if (emailErr) emailErr.textContent = '';
        if (passErr) passErr.textContent = '';
        if (verifyBanner) verifyBanner.style.display = 'none';

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

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="login-spinner"></span>';
        }
        if (coldStartNotice) coldStartNotice.style.display = 'none';

        const timer = setTimeout(() => {
            if (coldStartNotice) coldStartNotice.style.display = 'block';
        }, 3500);

        try {
            await window.apiService.auth.login(email, password);
            clearTimeout(timer);
            sessionStorage.removeItem('pending_verify_email');
            window.location.replace('ia-preditiva.html');
        } catch (err) {
            clearTimeout(timer);
            if (coldStartNotice) coldStartNotice.style.display = 'none';
            const msg = err.message || 'Email ou senha incorretos.';
            const lower = msg.toLowerCase();
            if (lower.includes('verificado') || lower.includes('confirma') || lower.includes('e-mail ainda não')) {
                showVerificationBanner(
                    'info',
                    'Confirme seu e-mail para acessar sua conta.'
                );
            } else if (passErr) {
                passErr.textContent = msg;
            }
        } finally {
            clearTimeout(timer);
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'ENTRAR';
            }
        }
    };
}

// 2. Cadastro
function setupRegisterForm() {
    const form = document.getElementById('formRegister');
    const pagePath = window.location.pathname.toLowerCase();
    const isRegisterPage = pagePath.includes('cadastro') || form !== null;
    if (!form && !isRegisterPage) return;

    const activeForm = form || document.querySelector('.login-right');
    if (!activeForm) return;

    const emailInput = document.getElementById('registerEmail') || activeForm.querySelector('input[type="email"]');
    const passInput = document.getElementById('registerPassword') || document.getElementById('senha');
    const confirmInput = document.getElementById('registerConfirmPassword') || document.getElementById('confirmarSenha');
    const submitBtn = document.getElementById('btnRegisterSubmit') || activeForm.querySelector('.button-right');
    const emailErr = document.getElementById('registerEmailError');
    const passErr = document.getElementById('registerPasswordError');
    const confirmErr = document.getElementById('registerConfirmPasswordError');

    activeForm.onsubmit = async (e) => {
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

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="login-spinner"></span>';
        }

        try {
            await window.apiService.auth.register(email, password);
            sessionStorage.setItem('pending_verify_email', email.toLowerCase());
            window.location.replace('login.html?pending_verify=1');
        } catch (err) {
            if (emailErr) emailErr.textContent = err.message || 'Erro ao realizar cadastro.';
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'CADASTRAR';
            }
        }
    };
}

// 3. Recuperação - Etapa 1 (Solicitar Código)
function setupRecoveryStep1() {
    const pagePath = window.location.pathname.toLowerCase();
    const isStep1Page = pagePath.includes('recuperarsenha') || pagePath.includes('recuperar-senha');
    const form = document.getElementById('formRecoveryStep1') || (isStep1Page ? document.querySelector('.login-right') : null);
    if (!form || !isStep1Page) return;

    const emailInput = document.getElementById('recoveryEmailStep1') || form.querySelector('input[type="email"]');
    const submitBtn = document.getElementById('btnRecoveryStep1Submit') || form.querySelector('.button-right');
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

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="login-spinner"></span>';
        }

        try {
            await window.apiService.auth.forgotPassword(email);
            sessionStorage.setItem('recovery_email', email);
            const targetPage = pagePath.includes('recuperarsenha') ? 'codigosenha.html' : 'codigosenha.html';
            window.location.href = targetPage;
        } catch (err) {
            if (errEl) errEl.textContent = err.message || 'Email não encontrado.';
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'ENVIAR';
            }
        }
    };
}

// 4. Recuperação - Etapa 2 (Inserir Código OTP)
function setupRecoveryStep2() {
    const pagePath = window.location.pathname.toLowerCase();
    const isStep2Page = pagePath.includes('codigosenha') || pagePath.includes('codigo-verificacao');
    const form = document.getElementById('formRecoveryStep2') || (isStep2Page ? document.querySelector('.login-right') : null);
    if (!form || !isStep2Page) return;

    const otpInputs = Array.from(form.querySelectorAll('.codigo-input'));
    const errEl = document.getElementById('recoveryStep2Error');
    const resendBtn = document.getElementById('btnRecoveryResend');
    const recoveryEmail = sessionStorage.getItem('recovery_email') || '';

    if (otpInputs[0]) otpInputs[0].focus();

    otpInputs.forEach((inp, idx) => {
        inp.maxLength = 1;
        inp.inputMode = 'numeric';
        inp.autocomplete = 'off';

        inp.oninput = (e) => {
            const cleanVal = e.target.value.replace(/\D/g, '');
            inp.value = cleanVal ? cleanVal[0] : '';
            if (cleanVal && idx < otpInputs.length - 1) {
                otpInputs[idx + 1].focus();
            }
        };

        inp.onkeydown = (e) => {
            if (e.key === 'Backspace' && !inp.value && idx > 0) {
                otpInputs[idx - 1].focus();
            }
        };

        inp.onpaste = (e) => {
            e.preventDefault();
            const pasted = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '').slice(0, otpInputs.length);
            if (pasted) {
                for (let i = 0; i < pasted.length; i++) {
                    if (otpInputs[i]) otpInputs[i].value = pasted[i];
                }
                const nextIdx = Math.min(pasted.length, otpInputs.length - 1);
                if (otpInputs[nextIdx]) otpInputs[nextIdx].focus();
            }
        };
    });

    if (resendBtn) {
        resendBtn.onclick = async () => {
            if (!recoveryEmail) {
                if (errEl) {
                    errEl.style.color = '#ff6b81';
                    errEl.textContent = 'Email não identificado. Reinicie a recuperação.';
                }
                return;
            }
            try {
                const res = await window.apiService.auth.forgotPassword(recoveryEmail);
                if (errEl) {
                    errEl.style.color = '#34d399';
                    errEl.textContent = res.message || 'Código reenviado com sucesso!';
                }
                otpInputs.forEach(i => { if (i) i.value = ''; });
                if (otpInputs[0]) otpInputs[0].focus();
            } catch (err) {
                if (errEl) {
                    errEl.style.color = '#ff6b81';
                    errEl.textContent = err.message || 'Erro ao reenviar código.';
                }
            }
        };
    }

    form.onsubmit = (e) => {
        e.preventDefault();
        if (errEl) {
            errEl.style.color = '';
            errEl.textContent = '';
        }
        const code = otpInputs.map(i => i?.value || '').join('');
        if (code.length < 4) {
            if (errEl) {
                errEl.style.color = '#ff6b81';
                errEl.textContent = 'Digite os 4 dígitos do código de verificação.';
            }
            return;
        }

        sessionStorage.setItem('recovery_code', code);
        const targetPage = pagePath.includes('codigosenha') ? 'novasenha.html' : 'novasenha.html';
        window.location.href = targetPage;
    };
}

// 5. Recuperação - Etapa 3 (Definir Nova Senha)
function setupRecoveryStep3() {
    const pagePath = window.location.pathname.toLowerCase();
    const isStep3Page = pagePath.includes('novasenha') || pagePath.includes('nova-senha');
    const form = document.getElementById('formRecoveryStep3') || (isStep3Page ? document.querySelector('.login-right') : null);
    if (!form || !isStep3Page) return;

    const emailInput = document.getElementById('recoveryEmailStep3') || form.querySelector('input[type="email"]');
    const passInput = document.getElementById('recoveryNewPassword') || document.getElementById('senha');
    const confirmInput = document.getElementById('recoveryConfirmNewPassword') || document.getElementById('confirmarSenha');
    const submitBtn = document.getElementById('btnRecoveryStep3Submit') || form.querySelector('.button-right');
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
            if (passErr) passErr.textContent = 'Informe o email.';
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

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="login-spinner"></span>';
        }

        try {
            await window.apiService.auth.resetPassword(email, storedCode, newPass);
            sessionStorage.removeItem('recovery_email');
            sessionStorage.removeItem('recovery_code');
            window.location.replace('login.html');
        } catch (err) {
            if (passErr) passErr.textContent = err.message || 'Erro ao redefinir senha.';
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'LOGIN';
            }
        }
    };
}

/**
 * TrendCommerce AI - Vanilla Auth Controller
 * Gerencia Login, Cadastro, Recuperação de Senha (3 Etapas) e Autenticação Google com 2FA.
 */

const GOOGLE_CLIENT_ID = '33242244365-ubjiqb1h7thh0t6n5hdg3e3ugsuebm6e.apps.googleusercontent.com';

/**
 * Abre diretamente a janela oficial do Google (Google Identity Services)
 */
window.launchGoogleAuth = function({ onAccountSelected, onError, setLoading }) {
    const clientId = window.GOOGLE_CLIENT_ID || GOOGLE_CLIENT_ID;

    const executeGIS = () => {
        if (window.google?.accounts?.oauth2) {
            try {
                const tokenClient = window.google.accounts.oauth2.initTokenClient({
                    client_id: clientId,
                    scope: 'email profile openid',
                    prompt: 'select_account',
                    callback: async (tokenResponse) => {
                        if (tokenResponse && tokenResponse.access_token) {
                            try {
                                if (setLoading) setLoading(true);
                                const userInfoRes = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
                                    headers: { Authorization: `Bearer ${tokenResponse.access_token}` }
                                });
                                const profile = await userInfoRes.json();
                                if (profile && profile.email) {
                                    if (onAccountSelected) {
                                        onAccountSelected({
                                            email: profile.email,
                                            name: profile.name || profile.given_name || profile.email.split('@')[0],
                                            picture: profile.picture,
                                            sub: profile.sub
                                        });
                                    }
                                    return;
                                }
                            } catch (fetchErr) {
                                console.error('[GIS Profile Error]', fetchErr);
                                if (onError) onError('Falha ao obter perfil da conta Google selecionada.');
                            } finally {
                                if (setLoading) setLoading(false);
                            }
                        } else if (tokenResponse?.error) {
                            console.warn('[GIS Error]', tokenResponse.error);
                            if (setLoading) setLoading(false);
                        }
                    },
                    error_callback: (err) => {
                        console.warn('[GIS Error Callback]', err);
                        if (setLoading) setLoading(false);
                        if (err?.type === 'popup_closed') {
                            return;
                        }
                        if (onError) onError('A janela de seleção do Google foi fechada ou bloqueada pelo navegador.');
                    }
                });

                tokenClient.requestAccessToken({ prompt: 'select_account' });
            } catch (err) {
                console.error('[GIS Launch Error]', err);
                if (setLoading) setLoading(false);
                if (onError) onError('Erro ao abrir o seletor de contas do Google.');
            }
        } else if (window.google?.accounts?.id) {
            try {
                window.google.accounts.id.initialize({
                    client_id: clientId,
                    callback: async (response) => {
                        if (response && response.credential) {
                            try {
                                if (setLoading) setLoading(true);
                                const data = await window.apiService.auth.loginWithGoogle({ token: response.credential });
                                if (onAccountSelected) {
                                    onAccountSelected({ directLoginSuccess: true, data });
                                }
                            } catch (e) {
                                if (onError) onError(e.message);
                            } finally {
                                if (setLoading) setLoading(false);
                            }
                        }
                    }
                });
                window.google.accounts.id.prompt();
            } catch (e) {
                if (setLoading) setLoading(false);
                if (onError) onError('Não foi possível inicializar o Google Identity Services.');
            }
        } else {
            const script = document.createElement('script');
            script.src = 'https://accounts.google.com/gsi/client';
            script.async = true;
            script.defer = true;
            script.onload = () => {
                setTimeout(executeGIS, 150);
            };
            script.onerror = () => {
                if (setLoading) setLoading(false);
                if (onError) onError('Não foi possível carregar o serviço do Google. Verifique sua conexão.');
            };
            document.head.appendChild(script);
        }
    };

    executeGIS();
};

const AuthModule = (function() {
    let currentView = 'login'; // 'login' | 'register' | 'recovery-1' | 'recovery-2' | 'recovery-3'
    let recoveryEmail = '';
    let recoveryCode = '';
    let googleAccount = null;
    let googleCooldownTimer = null;
    let googleCooldownSeconds = 45;

    function init() {
        setupLeftPanelEvents();
        setupLoginForm();
        setupRegisterForm();
        setupRecoveryForms();
        setupGoogleModal();
        setupPasswordToggles();
    }

    function switchView(viewName, pushHistory = true) {
        currentView = viewName;

        // Atualizar painel esquerdo (.login-left)
        const leftPanel = document.getElementById('loginLeftPanel');
        if (leftPanel) {
            if (viewName === 'login') {
                leftPanel.innerHTML = `
                    <h1>BEM-VINDO<br />DE VOLTA!</h1>
                    <button type="button" class="login-button" id="btnLeftToRegister">
                        CADASTRAR
                    </button>
                `;
            } else if (viewName === 'register') {
                leftPanel.innerHTML = `
                    <h1>ACESSE SUA CONTA</h1>
                    <button type="button" class="login-button" id="btnLeftToLogin">
                        ENTRAR
                    </button>
                `;
            } else if (viewName.startsWith('recovery')) {
                leftPanel.innerHTML = `
                    <h1>RECUPERE<br />SUA SENHA</h1>
                    <button type="button" class="login-button" id="btnLeftRecoveryToLogin">
                        ENTRAR
                    </button>
                `;
            }
            setupLeftPanelEvents();
        }

        // Atualizar formulários no painel direito (.login-right)
        const forms = {
            'login': document.getElementById('formLogin'),
            'register': document.getElementById('formRegister'),
            'recovery-1': document.getElementById('formRecoveryStep1'),
            'recovery-2': document.getElementById('formRecoveryStep2'),
            'recovery-3': document.getElementById('formRecoveryStep3')
        };

        Object.keys(forms).forEach((key) => {
            if (forms[key]) {
                if (key === viewName) {
                    forms[key].style.display = 'block';
                } else {
                    forms[key].style.display = 'none';
                }
            }
        });

        if (viewName === 'recovery-2') {
            const firstOtp = document.getElementById('otp1');
            if (firstOtp) firstOtp.focus();
        } else if (viewName === 'recovery-3') {
            const emailInput = document.getElementById('recoveryEmailStep3');
            if (emailInput && recoveryEmail) {
                emailInput.value = recoveryEmail;
            }
        }

        if (pushHistory && window.updateBrowserUrl) {
            const viewRouteMap = {
                'login': 'login',
                'register': 'cadastro',
                'recovery-1': 'recuperar-senha',
                'recovery-2': 'recuperar-senha/codigo',
                'recovery-3': 'recuperar-senha/nova-senha'
            };
            window.updateBrowserUrl(viewRouteMap[viewName] || 'login');
        }
    }

    function setupLeftPanelEvents() {
        const btnReg = document.getElementById('btnLeftToRegister');
        if (btnReg) {
            btnReg.onclick = () => switchView('register');
        }
        const btnLogin = document.getElementById('btnLeftToLogin');
        if (btnLogin) {
            btnLogin.onclick = () => switchView('login');
        }
        const btnRecLogin = document.getElementById('btnLeftRecoveryToLogin');
        if (btnRecLogin) {
            btnRecLogin.onclick = () => switchView('login');
        }
    }

    function setupPasswordToggles() {
        document.querySelectorAll('.password-container').forEach(container => {
            const input = container.querySelector('input');
            const btn = container.querySelector('button');
            if (input && btn) {
                btn.onclick = () => {
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

    // ==========================================
    // Login Form
    // ==========================================
    function setupLoginForm() {
        const form = document.getElementById('formLogin');
        if (!form) return;

        const emailInput = document.getElementById('loginEmail');
        const passInput = document.getElementById('loginPassword');
        const submitBtn = document.getElementById('btnLoginSubmit');
        const emailErr = document.getElementById('loginEmailError');
        const passErr = document.getElementById('loginPasswordError');
        const forgotLink = document.getElementById('linkForgotPassword');
        const coldStartNotice = document.getElementById('coldStartNotice');
        const googleBtn = document.getElementById('btnLoginGoogle');

        if (forgotLink) {
            forgotLink.onclick = () => switchView('recovery-1');
        }

        if (googleBtn) {
            googleBtn.onclick = handleGoogleTrigger;
        }

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
                if (coldStartNotice) coldStartNotice.style.display = 'none';
                window.showToast(`Bem-vindo, ${data.user.email}!`, 'success');
                if (window.onAuthSuccess) {
                    window.onAuthSuccess(data.user);
                }
            } catch (err) {
                clearTimeout(timer);
                if (coldStartNotice) coldStartNotice.style.display = 'none';
                if (passErr) passErr.textContent = err.message || 'Email ou senha incorretos.';
                window.showToast(err.message || 'Falha ao autenticar.', 'error');
            } finally {
                clearTimeout(timer);
                submitBtn.disabled = false;
                submitBtn.textContent = 'ENTRAR';
            }
        };
    }

    // ==========================================
    // Register Form
    // ==========================================
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
        const googleBtn = document.getElementById('btnRegisterGoogle');

        if (googleBtn) {
            googleBtn.onclick = handleGoogleTrigger;
        }

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
                window.showToast('Cadastro realizado com sucesso! Faça login para continuar.', 'success');
                switchView('login');
            } catch (err) {
                if (emailErr) emailErr.textContent = err.message || 'Erro ao realizar cadastro.';
                window.showToast(err.message || 'Erro ao cadastrar.', 'error');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'CADASTRAR';
            }
        };
    }

    // ==========================================
    // Recovery Forms (1, 2, 3)
    // ==========================================
    function setupRecoveryForms() {
        // Step 1
        const f1 = document.getElementById('formRecoveryStep1');
        if (f1) {
            const emailInput = document.getElementById('recoveryEmailStep1');
            const submitBtn = document.getElementById('btnRecoveryStep1Submit');
            const errEl = document.getElementById('recoveryStep1Error');

            f1.onsubmit = async (e) => {
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
                    window.showToast(res.message, 'success', 7000);
                    recoveryEmail = email;
                    switchView('recovery-2');
                } catch (err) {
                    if (errEl) errEl.textContent = err.message || 'Email não encontrado.';
                    window.showToast(err.message || 'Erro ao enviar código.', 'error');
                } finally {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'ENVIAR';
                }
            };
        }

        // Step 2
        const f2 = document.getElementById('formRecoveryStep2');
        if (f2) {
            const otpInputs = [
                document.getElementById('otp1'),
                document.getElementById('otp2'),
                document.getElementById('otp3'),
                document.getElementById('otp4')
            ];
            const errEl = document.getElementById('recoveryStep2Error');
            const resendBtn = document.getElementById('btnRecoveryResend');

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
                    try {
                        const res = await window.apiService.auth.forgotPassword(recoveryEmail);
                        window.showToast(res.message, 'info', 7000);
                        otpInputs.forEach(i => { if (i) i.value = ''; });
                        if (otpInputs[0]) otpInputs[0].focus();
                    } catch (err) {
                        window.showToast(err.message, 'error');
                    }
                };
            }

            f2.onsubmit = (e) => {
                e.preventDefault();
                if (errEl) errEl.textContent = '';
                const code = otpInputs.map(i => i?.value || '').join('');
                if (code.length < 4) {
                    if (errEl) errEl.textContent = 'Digite os 4 dígitos do código de verificação.';
                    return;
                }

                recoveryCode = code;
                window.showToast('Código confirmado! Defina sua nova senha.', 'success');
                switchView('recovery-3');
            };
        }

        // Step 3
        const f3 = document.getElementById('formRecoveryStep3');
        if (f3) {
            const emailInput = document.getElementById('recoveryEmailStep3');
            const passInput = document.getElementById('recoveryNewPassword');
            const confirmInput = document.getElementById('recoveryConfirmNewPassword');
            const submitBtn = document.getElementById('btnRecoveryStep3Submit');
            const passErr = document.getElementById('recoveryNewPassError');
            const confirmErr = document.getElementById('recoveryConfirmPassError');

            f3.onsubmit = async (e) => {
                e.preventDefault();
                if (passErr) passErr.textContent = '';
                if (confirmErr) confirmErr.textContent = '';

                const email = (emailInput?.value || recoveryEmail || '').trim();
                const newPass = passInput?.value || '';
                const confirmPass = confirmInput?.value || '';

                let hasError = false;
                if (!email) {
                    window.showToast('Informe o email.', 'error');
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
                    const res = await window.apiService.auth.resetPassword(email, recoveryCode, newPass);
                    window.showToast(res.message, 'success');
                    switchView('login');
                } catch (err) {
                    if (passErr) passErr.textContent = err.message || 'Erro ao redefinir senha.';
                    window.showToast(err.message || 'Erro ao redefinir senha.', 'error');
                } finally {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'LOGIN';
                }
            };
        }
    }

    // ==========================================
    // Google Auth & 2FA Modal
    // ==========================================
    function handleGoogleTrigger() {
        if (typeof window.launchGoogleAuth !== 'function') {
            window.showToast('Inicializando serviço do Google...', 'info');
            return;
        }

        const setLoading = (loading) => {
            const btn1 = document.getElementById('btnLoginGoogle');
            const btn2 = document.getElementById('btnRegisterGoogle');
            [btn1, btn2].forEach(b => {
                if (b) {
                    b.disabled = loading;
                    const span = b.querySelector('span');
                    if (span) {
                        span.textContent = loading ? 'Abrindo Google...' : (b.id === 'btnLoginGoogle' ? 'Entrar com o Google' : 'Cadastrar com o Google');
                    }
                }
            });
        };

        window.launchGoogleAuth({
            setLoading,
            onError: (msg) => {
                window.showToast(msg, 'error');
            },
            onAccountSelected: async (account) => {
                if (account.directLoginSuccess) {
                    window.showToast(`Bem-vindo, ${account.data.user.email}!`, 'success');
                    if (window.onAuthSuccess) {
                        window.onAuthSuccess(account.data.user);
                    }
                    return;
                }

                try {
                    window.showToast(`Enviando código de verificação para ${account.email}...`, 'info');
                    await window.apiService.auth.requestGoogleCode(account.email, account.name);
                    window.showToast(`Código 2FA enviado para ${account.email}!`, 'success');
                    googleAccount = account;
                    openGoogle2FAModal(account);
                } catch (err) {
                    window.showToast(err.message || 'Falha ao enviar código 2FA para o e-mail selecionado.', 'error');
                }
            }
        });
    }

    function setupGoogleModal() {
        const modalBackdrop = document.getElementById('googleAuthModal');
        if (!modalBackdrop) return;

        const closeBtn = document.getElementById('googleModalCloseBtn');
        const switchAccBtn = document.getElementById('googleSwitchAccountBtn');
        const resendBtn = document.getElementById('googleResendBtn');
        const form2FA = document.getElementById('google2FAForm');

        if (closeBtn) closeBtn.onclick = closeGoogle2FAModal;
        modalBackdrop.onclick = (e) => {
            if (e.target === modalBackdrop) closeGoogle2FAModal();
        };

        if (switchAccBtn) {
            switchAccBtn.onclick = () => {
                closeGoogle2FAModal();
                handleGoogleTrigger();
            };
        }

        if (resendBtn) {
            resendBtn.onclick = async () => {
                if (googleCooldownSeconds > 0) return;
                try {
                    window.showToast('Reenviando código 2FA...', 'info');
                    await window.apiService.auth.requestGoogleCode(googleAccount.email, googleAccount.name);
                    window.showToast(`Novo código 2FA enviado para ${googleAccount.email}!`, 'success');
                    startGoogleResendTimer();
                } catch (err) {
                    window.showToast(err.message || 'Erro ao reenviar código.', 'error');
                }
            };
        }

        const inputs = [0, 1, 2, 3].map(i => document.getElementById(`google-2fa-${i}`));
        inputs.forEach((inp, idx) => {
            if (!inp) return;
            inp.oninput = (e) => {
                const cleaned = e.target.value.replace(/\D/g, '');
                if (cleaned.length > 1) {
                    const chars = cleaned.slice(0, 4).split('');
                    for (let i = 0; i < 4; i++) {
                        if (inputs[i]) inputs[i].value = chars[i] || '';
                    }
                    const lastIdx = Math.min(chars.length - 1, 3);
                    if (inputs[lastIdx]) inputs[lastIdx].focus();
                    return;
                }
                inp.value = cleaned.slice(-1);
                if (cleaned && idx < 3 && inputs[idx + 1]) {
                    inputs[idx + 1].focus();
                }
            };

            inp.onkeydown = (e) => {
                if (e.key === 'Backspace' && !inp.value && idx > 0 && inputs[idx - 1]) {
                    inputs[idx - 1].focus();
                    inputs[idx - 1].value = '';
                }
            };
        });

        if (form2FA) {
            form2FA.onsubmit = async (e) => {
                e.preventDefault();
                const code = inputs.map(i => i?.value || '').join('').trim();
                const errBox = document.getElementById('google2FAError');
                if (errBox) errBox.style.display = 'none';

                if (code.length < 4) {
                    if (errBox) {
                        errBox.style.display = 'flex';
                        errBox.querySelector('span').textContent = 'Digite os 4 dígitos do código recebido no seu e-mail.';
                    }
                    return;
                }

                const submitBtn = document.getElementById('google2FASubmitBtn');
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<span class="login-spinner"></span>';
                }

                try {
                    const data = await window.apiService.auth.verifyGoogleCode(
                        googleAccount.email,
                        code,
                        googleAccount.name
                    );
                    window.showToast(`Autenticação de 2 fatores aprovada! Bem-vindo, ${data.user.name || data.user.email}!`, 'success');
                    closeGoogle2FAModal();
                    if (window.onAuthSuccess) {
                        window.onAuthSuccess(data.user);
                    }
                } catch (err) {
                    if (errBox) {
                        errBox.style.display = 'flex';
                        errBox.querySelector('span').textContent = err.message || 'Código 2FA incorreto ou expirado.';
                    }
                    window.showToast(err.message || 'Código de verificação inválido.', 'error');
                } finally {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Confirmar';
                    }
                }
            };
        }
    }

    function openGoogle2FAModal(account) {
        const modal = document.getElementById('googleAuthModal');
        if (!modal) return;

        const emailBadge = document.getElementById('google2FAEmailBadge');
        if (emailBadge) {
            if (account.picture) {
                emailBadge.innerHTML = `
                    <img src="${account.picture}" alt="${account.name}" class="google-row-avatar-img" style="width: 24px; height: 24px; margin-right: 8px; border-radius: 50%;" />
                    <strong>${account.email}</strong>
                `;
            } else {
                emailBadge.innerHTML = `
                    <i class="ph ph-envelope-simple" style="margin-right: 6px;"></i>
                    <strong>${account.email}</strong>
                `;
            }
        }

        [0, 1, 2, 3].forEach(i => {
            const inp = document.getElementById(`google-2fa-${i}`);
            if (inp) inp.value = '';
        });
        const errBox = document.getElementById('google2FAError');
        if (errBox) errBox.style.display = 'none';

        startGoogleResendTimer();
        modal.style.display = 'flex';

        setTimeout(() => {
            const first = document.getElementById('google-2fa-0');
            if (first) first.focus();
        }, 100);
    }

    function closeGoogle2FAModal() {
        const modal = document.getElementById('googleAuthModal');
        if (modal) modal.style.display = 'none';
        if (googleCooldownTimer) clearInterval(googleCooldownTimer);
    }

    function startGoogleResendTimer() {
        if (googleCooldownTimer) clearInterval(googleCooldownTimer);
        googleCooldownSeconds = 45;
        const timerWrap = document.getElementById('google2FAResendWrap');
        if (!timerWrap) return;

        const updateUI = () => {
            if (googleCooldownSeconds > 0) {
                timerWrap.innerHTML = `
                    <span class="google-resend-timer">
                        Reenviar código em <strong>${googleCooldownSeconds}s</strong>
                    </span>
                `;
            } else {
                timerWrap.innerHTML = `
                    <button type="button" class="google-resend-link" id="googleResendBtn">
                        Não recebi o código. Reenviar agora
                    </button>
                `;
                const btn = document.getElementById('googleResendBtn');
                if (btn) {
                    btn.onclick = async () => {
                        try {
                            window.showToast('Reenviando código 2FA...', 'info');
                            await window.apiService.auth.requestGoogleCode(googleAccount.email, googleAccount.name);
                            window.showToast(`Novo código 2FA enviado para ${googleAccount.email}!`, 'success');
                            startGoogleResendTimer();
                        } catch (err) {
                            window.showToast(err.message || 'Erro ao reenviar código.', 'error');
                        }
                    };
                }
                clearInterval(googleCooldownTimer);
            }
        };

        updateUI();
        googleCooldownTimer = setInterval(() => {
            googleCooldownSeconds--;
            updateUI();
        }, 1000);
    }

    return {
        init,
        switchView,
        getCurrentView: () => currentView
    };
})();

window.AuthModule = AuthModule;

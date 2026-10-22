/**
 * GoogleAuthModal.jsx
 * Modal de Verificação em Duas Etapas (2FA) para Login com Google e
 * Utilitário Global para Inicialização do Pop-up Nativo do Google (GIS).
 */

const GOOGLE_CLIENT_ID = '33242244365-ubjiqb1h7thh0t6n5hdg3e3ugsuebm6e.apps.googleusercontent.com';

/**
 * Abre diretamente a janela pop-up oficial do Google (Google Identity Services)
 * para que o usuário selecione uma de suas contas conectadas no navegador.
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
            // Se a biblioteca GIS ainda não estiver pronta no DOM, carrega sob demanda
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

/**
 * Componente do Modal 2FA de Autenticação Segura com o Google
 */
function GoogleAuthModal({ isOpen, onClose, onLoginSuccess, showToast, account, onSwitchAccount }) {
    const [otpCode, setOtpCode] = React.useState(['', '', '', '']);
    const [loading, setLoading] = React.useState(false);
    const [resendCooldown, setResendCooldown] = React.useState(45);
    const [errorMessage, setErrorMessage] = React.useState('');

    React.useEffect(() => {
        if (isOpen) {
            setOtpCode(['', '', '', '']);
            setErrorMessage('');
            setLoading(false);
            setResendCooldown(45);
        }
    }, [isOpen]);

    // Timer de contagem regressiva para reenvio do código 2FA
    React.useEffect(() => {
        if (resendCooldown > 0) {
            const timer = setTimeout(() => setResendCooldown(c => c - 1), 1000);
            return () => clearTimeout(timer);
        }
    }, [resendCooldown]);

    if (!isOpen || !account) return null;

    // Submissão do código 2FA
    const handleVerify2FA = async (e) => {
        if (e) e.preventDefault();
        const code = otpCode.join('').trim();
        if (code.length < 4) {
            setErrorMessage('Digite os 4 dígitos do código recebido no seu e-mail.');
            return;
        }

        setErrorMessage('');
        setLoading(true);

        try {
            const data = await window.apiService.auth.verifyGoogleCode(
                account.email,
                code,
                account.name
            );
            showToast(`Autenticação de 2 fatores aprovada! Bem-vindo, ${data.user.name || data.user.email}!`, 'success');
            onClose();
            onLoginSuccess(data.user);
        } catch (err) {
            setErrorMessage(err.message || 'Código 2FA incorreto ou expirado.');
            showToast(err.message || 'Código de verificação inválido.', 'error');
        } finally {
            setLoading(false);
        }
    };

    // Reenviar código 2FA
    const handleResend = async () => {
        if (resendCooldown > 0 || loading) return;
        setErrorMessage('');
        setLoading(true);
        try {
            const resp = await window.apiService.auth.requestGoogleCode(account.email, account.name);
            showToast(resp.message || `Novo código 2FA enviado para ${account.email}!`, 'success');
            setResendCooldown(45);
        } catch (err) {
            setErrorMessage(err.message || 'Falha ao reenviar código.');
            showToast(err.message || 'Erro no reenvio do código.', 'error');
        } finally {
            setLoading(false);
        }
    };

    // Gerenciador de digitação e auto-focus dos 4 dígitos
    const handleOtpChange = (index, value) => {
        const cleaned = value.replace(/\D/g, '');
        const newCode = [...otpCode];

        if (cleaned.length > 1) {
            const chars = cleaned.slice(0, 4).split('');
            for (let i = 0; i < 4; i++) {
                newCode[i] = chars[i] || '';
            }
            setOtpCode(newCode);
            const lastIdx = Math.min(chars.length - 1, 3);
            const nextInput = document.getElementById(`google-2fa-${lastIdx}`);
            if (nextInput) nextInput.focus();
            return;
        }

        newCode[index] = cleaned.slice(-1);
        setOtpCode(newCode);

        if (cleaned && index < 3) {
            const nextInput = document.getElementById(`google-2fa-${index + 1}`);
            if (nextInput) nextInput.focus();
        }
    };

    const handleOtpKeyDown = (index, e) => {
        if (e.key === 'Backspace' && !otpCode[index] && index > 0) {
            const prevInput = document.getElementById(`google-2fa-${index - 1}`);
            if (prevInput) {
                prevInput.focus();
                const newCode = [...otpCode];
                newCode[index - 1] = '';
                setOtpCode(newCode);
            }
        }
    };

    return (
        <div className="google-oauth-backdrop" onClick={onClose}>
            <div className="google-oauth-window" onClick={(e) => e.stopPropagation()}>
                {/* Barra Superior Oficial Google */}
                <div className="google-oauth-topbar">
                    <div className="google-topbar-brand">
                        <svg className="google-topbar-icon" viewBox="0 0 24 24" width="20" height="20">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
                        </svg>
                        <span>Fazer Login com o Google</span>
                    </div>

                    <button type="button" className="google-oauth-close-btn" onClick={onClose} aria-label="Fechar">
                        <i className="ph ph-x"></i>
                    </button>
                </div>

                {/* Conteúdo do 2FA */}
                <div className="google-oauth-body">
                    <div className="google-oauth-grid">
                        <div className="google-oauth-left">
                            <div className="google-2fa-shield-icon">
                                <i className="ph ph-shield-check"></i>
                            </div>
                            <h1 className="google-oauth-headline">Verificação em duas etapas</h1>
                            <p className="google-oauth-subheadline">
                                Para confirmar sua identidade, enviamos um código de 4 dígitos para:
                            </p>
                            <div className="google-2fa-badge">
                                {account.picture ? (
                                    <img
                                        src={account.picture}
                                        alt={account.name}
                                        className="google-row-avatar-img"
                                        style={{ width: '24px', height: '24px', marginRight: '8px', borderRadius: '50%' }}
                                    />
                                ) : (
                                    <i className="ph ph-envelope-simple" style={{ marginRight: '6px' }}></i>
                                )}
                                <strong>{account.email}</strong>
                            </div>
                        </div>

                        <div className="google-oauth-right">
                            {errorMessage && (
                                <div className="google-error-alert">
                                    <i className="ph ph-warning-circle"></i>
                                    <span>{errorMessage}</span>
                                </div>
                            )}

                            <form className="google-2fa-form" onSubmit={handleVerify2FA}>
                                <p className="google-2fa-instruction">
                                    Digite o código de 4 dígitos para concluir o login seguro com o Google:
                                </p>

                                <div className="codigo-container google-2fa-inputs">
                                    {otpCode.map((digit, idx) => (
                                        <input
                                            key={idx}
                                            id={`google-2fa-${idx}`}
                                            type="text"
                                            inputMode="numeric"
                                            maxLength={1}
                                            className="codigo-input"
                                            value={digit}
                                            onChange={(e) => handleOtpChange(idx, e.target.value)}
                                            onKeyDown={(e) => handleOtpKeyDown(idx, e)}
                                            autoFocus={idx === 0}
                                            required
                                        />
                                    ))}
                                </div>

                                <div className="google-2fa-resend-wrap">
                                    {resendCooldown > 0 ? (
                                        <span className="google-resend-timer">
                                            Reenviar código em <strong>{resendCooldown}s</strong>
                                        </span>
                                    ) : (
                                        <button
                                            type="button"
                                            className="google-resend-link"
                                            onClick={handleResend}
                                            disabled={loading}
                                        >
                                            Não recebi o código. Reenviar agora
                                        </button>
                                    )}
                                </div>

                                <div className="google-form-actions">
                                    <button
                                        type="button"
                                        className="google-btn-text"
                                        onClick={() => {
                                            onClose();
                                            if (onSwitchAccount) onSwitchAccount();
                                        }}
                                    >
                                        Escolher outra conta
                                    </button>

                                    <button
                                        type="submit"
                                        className="google-btn-primary"
                                        disabled={loading || otpCode.join('').length < 4}
                                    >
                                        {loading ? <span className="login-spinner"></span> : 'Confirmar'}
                                    </button>
                                </div>
                            </form>

                            <div className="google-oauth-disclaimer">
                                A Verificação em duas etapas do Google protege sua conta contra acessos não autorizados.
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
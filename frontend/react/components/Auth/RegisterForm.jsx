/**
 * RegisterForm.jsx
 * Formulário de Cadastro de Novo Usuário em React.
 */

function RegisterForm({ onSwitchView, onLoginSuccess, showToast }) {
    const [email, setEmail] = React.useState('');
    const [password, setPassword] = React.useState('');
    const [confirmPassword, setConfirmPassword] = React.useState('');
    const [showPassword, setShowPassword] = React.useState(false);
    const [showConfirm, setShowConfirm] = React.useState(false);
    const [errors, setErrors] = React.useState({});
    const [loading, setLoading] = React.useState(false);
    const [googleLoading, setGoogleLoading] = React.useState(false);
    const [googleAccount, setGoogleAccount] = React.useState(null);
    const [is2FAModalOpen, setIs2FAModalOpen] = React.useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        const newErrors = {};

        if (!email.trim()) newErrors.email = 'Informe um email válido.';
        if (password.length < 6) newErrors.password = 'A senha deve ter no mínimo 6 caracteres.';
        if (password !== confirmPassword) newErrors.confirmPassword = 'As senhas não coincidem.';

        if (Object.keys(newErrors).length > 0) {
            setErrors(newErrors);
            return;
        }

        setErrors({});
        setLoading(true);

        try {
            await window.apiService.auth.register(email.trim(), password);
            showToast('Cadastro realizado com sucesso! Faça login para continuar.', 'success');
            onSwitchView('login');
        } catch (err) {
            setErrors({ email: err.message || 'Erro ao realizar cadastro.' });
            showToast(err.message || 'Erro ao cadastrar.', 'error');
        } finally {
            setLoading(false);
        }
    };

    // Abre diretamente a janela oficial do Google (pop-up nativo)
    const handleGoogleRegister = () => {
        if (typeof window.launchGoogleAuth !== 'function') {
            showToast('Inicializando serviço do Google...', 'info');
            return;
        }

        window.launchGoogleAuth({
            setLoading: setGoogleLoading,
            onError: (msg) => {
                showToast(msg, 'error');
            },
            onAccountSelected: async (account) => {
                if (account.directLoginSuccess) {
                    showToast(`Bem-vindo, ${account.data.user.email}!`, 'success');
                    onLoginSuccess(account.data.user);
                    return;
                }

                try {
                    showToast(`Enviando código de verificação para ${account.email}...`, 'info');
                    await window.apiService.auth.requestGoogleCode(account.email, account.name);
                    showToast(`Código 2FA enviado para ${account.email}!`, 'success');
                    setGoogleAccount(account);
                    setIs2FAModalOpen(true);
                } catch (err) {
                    showToast(err.message || 'Falha ao enviar código 2FA para o e-mail selecionado.', 'error');
                }
            }
        });
    };

    return (
        <form className="login-form-content" onSubmit={handleSubmit} noValidate>
            <h1>EMAIL:</h1>
            <input
                type="email"
                className="login-input"
                placeholder="Digite seu email..."
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
            />
            {errors.email && <span className="login-field-error">{errors.email}</span>}

            <h1>SENHA:</h1>
            <div className="password-container">
                <input
                    type={showPassword ? 'text' : 'password'}
                    id="senha"
                    className="login-input"
                    placeholder="Digite sua senha..."
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoComplete="new-password"
                />
                <button
                    type="button"
                    id="toggleSenha"
                    aria-label="Mostrar ou ocultar senha"
                    onClick={() => setShowPassword(!showPassword)}
                >
                    <i className={showPassword ? "ph ph-eye-slash" : "ph ph-eye"}></i>
                </button>
            </div>
            {errors.password && <span className="login-field-error">{errors.password}</span>}

            <h1>CONFIRMAR SENHA:</h1>
            <div className="password-container">
                <input
                    type={showConfirm ? 'text' : 'password'}
                    id="confirmarSenha"
                    className="login-input"
                    placeholder="Digite sua senha..."
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    autoComplete="new-password"
                />
                <button
                    type="button"
                    id="toggleConfirmarSenha"
                    aria-label="Mostrar ou ocultar confirmação de senha"
                    onClick={() => setShowConfirm(!showConfirm)}
                >
                    <i className={showConfirm ? "ph ph-eye-slash" : "ph ph-eye"}></i>
                </button>
            </div>
            {errors.confirmPassword && <span className="login-field-error">{errors.confirmPassword}</span>}

            <button type="submit" className="button-right" disabled={loading || googleLoading}>
                {loading ? <span className="login-spinner"></span> : 'CADASTRAR'}
            </button>

            <div className="auth-divider">
                <span>OU</span>
            </div>

            <button
                type="button"
                className="btn-google-auth"
                onClick={handleGoogleRegister}
                disabled={loading || googleLoading}
            >
                <svg className="google-svg-icon" viewBox="0 0 24 24" width="18" height="18">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
                </svg>
                <span>{googleLoading ? 'Abrindo Google...' : 'Cadastrar com o Google'}</span>
            </button>

            {/* Modal de 2 Fatores exibido após selecionar a conta no Google */}
            <GoogleAuthModal
                isOpen={is2FAModalOpen}
                account={googleAccount}
                onClose={() => setIs2FAModalOpen(false)}
                onLoginSuccess={onLoginSuccess}
                showToast={showToast}
                onSwitchAccount={handleGoogleRegister}
            />
        </form>
    );
}
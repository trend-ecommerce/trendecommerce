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
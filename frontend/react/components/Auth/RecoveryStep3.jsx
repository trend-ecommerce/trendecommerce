/**
 * RecoveryStep3.jsx
 * Redefinição de senha com nova senha e confirmação.
 */

function RecoveryStep3({ recoveryEmail, recoveryCode, onFinish, showToast }) {
    const [email, setEmail] = React.useState(recoveryEmail || '');
    const [newPassword, setNewPassword] = React.useState('');
    const [confirmNewPassword, setConfirmNewPassword] = React.useState('');
    const [showNew, setShowNew] = React.useState(false);
    const [showConfirm, setShowConfirm] = React.useState(false);
    const [errors, setErrors] = React.useState({});
    const [loading, setLoading] = React.useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        const newErrors = {};

        if (!email.trim()) newErrors.email = 'Informe o email.';
        if (newPassword.length < 6) newErrors.newPassword = 'A senha deve ter no mínimo 6 caracteres.';
        if (newPassword !== confirmNewPassword) newErrors.confirmNewPassword = 'As senhas não coincidem.';

        if (Object.keys(newErrors).length > 0) {
            setErrors(newErrors);
            return;
        }

        setErrors({});
        setLoading(true);

        try {
            const res = await window.apiService.auth.resetPassword(email.trim(), recoveryCode, newPassword);
            showToast(res.message, 'success');
            onFinish();
        } catch (err) {
            setErrors({ newPassword: err.message || 'Erro ao redefinir senha.' });
            showToast(err.message || 'Erro ao redefinir senha.', 'error');
        } finally {
            setLoading(false);
        }
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
                    type={showNew ? 'text' : 'password'}
                    id="senha"
                    className="login-input"
                    placeholder="Digite sua senha..."
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    autoComplete="new-password"
                />
                <button
                    type="button"
                    id="toggleSenha"
                    aria-label="Mostrar ou ocultar nova senha"
                    onClick={() => setShowNew(!showNew)}
                >
                    <i className={showNew ? "ph ph-eye-slash" : "ph ph-eye"}></i>
                </button>
            </div>
            {errors.newPassword && <span className="login-field-error">{errors.newPassword}</span>}

            <h1>CONFIRMAR SENHA:</h1>
            <div className="password-container">
                <input
                    type={showConfirm ? 'text' : 'password'}
                    id="confirmarSenha"
                    className="login-input"
                    placeholder="Digite sua senha..."
                    value={confirmNewPassword}
                    onChange={(e) => setConfirmNewPassword(e.target.value)}
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
            {errors.confirmNewPassword && <span className="login-field-error">{errors.confirmNewPassword}</span>}

            <button type="submit" className="button-right" disabled={loading}>
                {loading ? <span className="login-spinner"></span> : 'LOGIN'}
            </button>
        </form>
    );
}
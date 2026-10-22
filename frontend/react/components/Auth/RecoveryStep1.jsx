/**
 * RecoveryStep1.jsx
 * Solicitação de código de recuperação de senha por email.
 */

function RecoveryStep1({ onNext, showToast }) {
    const [email, setEmail] = React.useState('');
    const [error, setError] = React.useState('');
    const [loading, setLoading] = React.useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!email.trim()) {
            setError('Informe seu email cadastrado.');
            return;
        }

        setError('');
        setLoading(true);

        try {
            const res = await window.apiService.auth.forgotPassword(email.trim());
            showToast(res.message, 'success', 7000);
            onNext(email.trim());
        } catch (err) {
            setError(err.message || 'Email não encontrado.');
            showToast(err.message || 'Erro ao enviar código.', 'error');
        } finally {
            setLoading(false);
        }
    };

    return (
        <form className="login-form-content" onSubmit={handleSubmit} noValidate>
            <h1 className="login-title">ENVIAREMOS UM CÓDIGO<br />PARA SEU EMAIL</h1>
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
            {error && <span className="login-field-error">{error}</span>}

            <button type="submit" className="button-right" disabled={loading}>
                {loading ? <span className="login-spinner"></span> : 'ENVIAR'}
            </button>
        </form>
    );
}
/**
 * AuthContainer.jsx
 * Container unificado da tela de Autenticação (Login / Cadastro / Recuperação de Senha).
 */

function AuthContainer({ onLoginSuccess, showToast, currentView, onSwitchView }) {
    const [internalView, setInternalView] = React.useState(currentView || 'login');
    const view = currentView || internalView;
    const [recoveryEmail, setRecoveryEmail] = React.useState('');
    const [recoveryCode, setRecoveryCode] = React.useState('');

    React.useEffect(() => {
        if (currentView) {
            // Se o usuário acessar recovery-2 ou recovery-3 diretamente sem ter email em memória, faz fallback seguro
            if ((currentView === 'recovery-2' || currentView === 'recovery-3') && !recoveryEmail) {
                setInternalView('recovery-1');
                if (onSwitchView) onSwitchView('recovery-1');
            } else {
                setInternalView(currentView);
            }
        }
    }, [currentView, recoveryEmail]);

    const setView = (nextView) => {
        setInternalView(nextView);
        if (onSwitchView) {
            onSwitchView(nextView);
        }
    };

    return (
        <div className="auth-root-wrapper">
            <Header />

            <div className="login-pai">
                <div className="login-container">
                    {/* Painel Esquerdo .login-left */}
                    <div className="login-left">
                        {view === 'login' && (
                            <React.Fragment>
                                <h1>BEM-VINDO<br />DE VOLTA!</h1>
                                <button
                                    type="button"
                                    className="login-button"
                                    onClick={() => setView('register')}
                                >
                                    CADASTRAR
                                </button>
                            </React.Fragment>
                        )}

                        {view === 'register' && (
                            <React.Fragment>
                                <h1>ACESSE SUA CONTA</h1>
                                <button
                                    type="button"
                                    className="login-button"
                                    onClick={() => setView('login')}
                                >
                                    ENTRAR
                                </button>
                            </React.Fragment>
                        )}

                        {view.startsWith('recovery') && (
                            <React.Fragment>
                                <h1>RECUPERE<br />SUA SENHA</h1>
                            </React.Fragment>
                        )}
                    </div>

                    {/* Painel Direito .login-right com o formulário da etapa */}
                    <div className="login-right">
                        {view === 'login' && (
                            <LoginForm
                                onSwitchView={setView}
                                onLoginSuccess={onLoginSuccess}
                                showToast={showToast}
                            />
                        )}

                        {view === 'register' && (
                            <RegisterForm
                                onSwitchView={setView}
                                onLoginSuccess={onLoginSuccess}
                                showToast={showToast}
                            />
                        )}

                        {view === 'recovery-1' && (
                            <RecoveryStep1
                                onNext={(email) => {
                                    setRecoveryEmail(email);
                                    setView('recovery-2');
                                }}
                                showToast={showToast}
                            />
                        )}

                        {view === 'recovery-2' && (
                            <RecoveryStep2
                                recoveryEmail={recoveryEmail}
                                onNext={(code) => {
                                    setRecoveryCode(code);
                                    setView('recovery-3');
                                }}
                                showToast={showToast}
                            />
                        )}

                        {view === 'recovery-3' && (
                            <RecoveryStep3
                                recoveryEmail={recoveryEmail}
                                recoveryCode={recoveryCode}
                                onFinish={() => setView('login')}
                                showToast={showToast}
                            />
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
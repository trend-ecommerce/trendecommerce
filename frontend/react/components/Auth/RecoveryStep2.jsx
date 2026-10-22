/**
 * RecoveryStep2.jsx
 * Entrada de 4 dígitos (código OTP de recuperação).
 */

function RecoveryStep2({ recoveryEmail, onNext, showToast }) {
    const [otp, setOtp] = React.useState(['', '', '', '']);
    const [error, setError] = React.useState('');
    const inputRefs = [React.useRef(null), React.useRef(null), React.useRef(null), React.useRef(null)];

    React.useEffect(() => {
        if (inputRefs[0].current) {
            inputRefs[0].current.focus();
        }
    }, []);

    const handleChange = (index, value) => {
        const cleanVal = value.replace(/\D/g, '');
        const newOtp = [...otp];
        newOtp[index] = cleanVal ? cleanVal[0] : '';
        setOtp(newOtp);

        if (cleanVal && index < 3) {
            inputRefs[index + 1].current.focus();
        }
    };

    const handleKeyDown = (index, e) => {
        if (e.key === 'Backspace' && !otp[index] && index > 0) {
            inputRefs[index - 1].current.focus();
        }
    };

    const handlePaste = (e) => {
        e.preventDefault();
        const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 4);
        if (pasted) {
            const newOtp = [...otp];
            for (let i = 0; i < pasted.length; i++) {
                newOtp[i] = pasted[i];
            }
            setOtp(newOtp);
            const nextIdx = Math.min(pasted.length, 3);
            inputRefs[nextIdx].current.focus();
        }
    };

    const handleResend = async () => {
        try {
            const res = await window.apiService.auth.forgotPassword(recoveryEmail);
            showToast(res.message, 'info', 7000);
            setOtp(['', '', '', '']);
            inputRefs[0].current.focus();
        } catch (err) {
            showToast(err.message, 'error');
        }
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        const code = otp.join('');
        if (code.length < 4) {
            setError('Digite os 4 dígitos do código de verificação.');
            return;
        }

        setError('');
        showToast('Código confirmado! Defina sua nova senha.', 'success');
        onNext(code);
    };

    return (
        <form className="login-form-content" onSubmit={handleSubmit} noValidate>
            <h1 className="login-title">DIGITE SEU CÓDIGO:</h1>

            <div className="codigo-container">
                {otp.map((digit, idx) => (
                    <input
                        key={idx}
                        ref={inputRefs[idx]}
                        type="text"
                        maxLength="1"
                        inputMode="numeric"
                        className="codigo-input"
                        value={digit}
                        onChange={(e) => handleChange(idx, e.target.value)}
                        onKeyDown={(e) => handleKeyDown(idx, e)}
                        onPaste={handlePaste}
                        autoComplete="off"
                    />
                ))}
            </div>

            {error && <span className="login-field-error center">{error}</span>}

            <div className="codigo-resend">
                <span>Não recebeu o código? </span>
                <button type="button" onClick={handleResend}>
                    Reenviar código
                </button>
            </div>

            <button type="submit" className="button-right">
                ENVIAR
            </button>
        </form>
    );
}
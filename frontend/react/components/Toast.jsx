/**
 * Toast.jsx
 * Sistema de Notificações Flutuantes Cyberpunk em React.
 */

function ToastContainer({ toasts }) {
    return (
        <div id="toast-container" className="toast-container" aria-live="polite">
            {toasts.map((toast) => (
                <div
                    key={toast.id}
                    className={`toast ${toast.type === 'error' ? 'toast-error' : toast.type === 'success' ? 'toast-success' : ''}`}
                >
                    {toast.type === 'success' && (
                        <svg className="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                    )}
                    {toast.type === 'error' && (
                        <svg className="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#ff4d6d" strokeWidth="2.5">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="12" y1="8" x2="12" y2="12"></line>
                            <line x1="12" y1="16" x2="12.01" y2="16"></line>
                        </svg>
                    )}
                    {toast.type === 'info' && (
                        <svg className="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" strokeWidth="2.5">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="12" y1="16" x2="12" y2="12"></line>
                            <line x1="12" y1="8" x2="12.01" y2="8"></line>
                        </svg>
                    )}
                    <span>{toast.message}</span>
                </div>
            ))}
        </div>
    );
}
/**
 * TrendCommerce AI - Cyberpunk Toast Notification System
 * Gerencia alertas flutuantes no container #toast-container.
 */

window.showToast = function(message, type = 'info', duration = 4000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        container.setAttribute('aria-live', 'polite');
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type === 'error' ? 'toast-error' : type === 'success' ? 'toast-success' : ''}`;

    let iconHtml = '';
    if (type === 'success') {
        iconHtml = `
            <svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
        `;
    } else if (type === 'error') {
        iconHtml = `
            <svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#ff4d6d" stroke-width="2.5">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
        `;
    } else {
        iconHtml = `
            <svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2.5">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="16" x2="12" y2="12"></line>
                <line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
        `;
    }

    toast.innerHTML = `${iconHtml}<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        setTimeout(() => {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 300);
    }, duration);
};

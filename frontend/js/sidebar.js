/**
 * TrendCommerce AI - Sidebar & Session Controller
 * Compartilhado entre todas as páginas do Dashboard (ia-preditiva.html, ranking.html, analise-especifica.html).
 */

(function initDashboardCommon() {
    // Verificação de autenticação: redireciona para login.html se não autenticado
    const token = window.apiService?.getToken() || localStorage.getItem('trendecommerce_token');
    const user = window.apiService?.getUser() || (() => {
        try {
            return JSON.parse(localStorage.getItem('trendecommerce_user') || 'null');
        } catch {
            return null;
        }
    })();

    if (!token || !user) {
        window.location.replace('login.html');
        return;
    }

    document.addEventListener('DOMContentLoaded', () => {
        // Exibir nome do usuário no perfil da sidebar
        const userNameEl = document.getElementById('dashUserName');
        if (userNameEl) {
            userNameEl.textContent = user.name || user.email || 'Administrador';
        }

        // Controle de abertura / fechamento da barra lateral
        const sidebar = document.getElementById('dashSidebar');
        const layout = document.getElementById('dashboardSection');
        const toggleBtn = document.getElementById('sidebarToggleBtn');
        const savedSidebar = localStorage.getItem('trend_sidebar_open');
        let isSidebarOpen = savedSidebar !== null ? savedSidebar === 'true' : true;

        const applySidebarState = () => {
            if (isSidebarOpen) {
                sidebar?.classList.add('open');
                sidebar?.classList.remove('collapsed');
                sidebar?.setAttribute('aria-hidden', 'false');
                layout?.classList.add('sidebar-open');
                layout?.classList.remove('sidebar-collapsed');
            } else {
                sidebar?.classList.remove('open');
                sidebar?.classList.add('collapsed');
                sidebar?.setAttribute('aria-hidden', 'true');
                layout?.classList.remove('sidebar-open');
                layout?.classList.add('sidebar-collapsed');
            }
        };

        applySidebarState();

        if (toggleBtn) {
            toggleBtn.onclick = () => {
                isSidebarOpen = !isSidebarOpen;
                localStorage.setItem('trend_sidebar_open', String(isSidebarOpen));
                applySidebarState();
                window.dispatchEvent(new Event('resize'));
            };
        }

        // Botão de Logout
        const logoutBtn = document.getElementById('btnLogout');
        if (logoutBtn) {
            logoutBtn.onclick = () => {
                window.apiService?.auth?.logout();
                localStorage.removeItem('trendecommerce_token');
                localStorage.removeItem('trendecommerce_user');
                window.location.replace('login.html');
            };
        }
    });
})();

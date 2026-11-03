/**
 * TrendCommerce AI - Vanilla App Controller & Router
 * Sincroniza Estado de Autenticação, Roteamento Dinâmico por URL e Alternância de Telas.
 */

(function() {
    let currentUser = null;
    let pendingTabAfterLogin = null;

    function getRouteFromHash() {
        return (window.location.hash || '').replace(/^#\/?/, '').trim().toLowerCase();
    }

    window.updateBrowserUrl = function(route, replace = false) {
        if (!route) return;
        const targetHash = '#/' + route;

        if (window.location.protocol === 'file:') {
            if (window.location.hash !== targetHash) {
                if (replace) {
                    window.location.replace(targetHash);
                } else {
                    window.location.hash = targetHash;
                }
            }
            return;
        }

        let pathname = window.location.pathname;
        if (pathname.endsWith('/index.html')) {
            pathname = pathname.slice(0, -10) || '/';
        }
        const search = window.location.search || '';
        const targetUrl = pathname + search + targetHash;

        const currentUrl = window.location.pathname + window.location.search + window.location.hash;
        if (currentUrl === targetUrl) {
            return;
        }

        try {
            if (replace) {
                window.history.replaceState({ route }, '', targetUrl);
            } else {
                window.history.pushState({ route }, '', targetUrl);
            }
        } catch {
            window.location.hash = targetHash;
        }
    };

    function parseRoute(routeStr) {
        const r = (routeStr || '').trim().toLowerCase();
        if (r === 'ranking' || r === 'ranking-produtos' || r === 'produtos') {
            return { isDash: true, tab: 'ranking', route: 'ranking' };
        }
        if (r === 'analise-especifica' || r === 'analise' || r === 'analise-produtos') {
            return { isDash: true, tab: 'analise-especifica', route: 'analise-especifica' };
        }
        if (r === 'ia-preditiva' || r === 'dashboard' || r === 'preditiva') {
            return { isDash: true, tab: 'ia-preditiva', route: 'ia-preditiva' };
        }

        if (r === 'cadastro' || r === 'register' || r === 'cadastrar') {
            return { isDash: false, view: 'register', route: 'cadastro' };
        }
        if (r === 'recuperar-senha' || r === 'recovery' || r === 'esqueci-senha') {
            return { isDash: false, view: 'recovery-1', route: 'recuperar-senha' };
        }
        if (r === 'recuperar-senha/codigo' || r === 'recovery/code') {
            return { isDash: false, view: 'recovery-2', route: 'recuperar-senha/codigo' };
        }
        if (r === 'recuperar-senha/nova-senha' || r === 'recovery/reset') {
            return { isDash: false, view: 'recovery-3', route: 'recuperar-senha/nova-senha' };
        }
        if (r === 'login') {
            return { isDash: false, view: 'login', route: 'login' };
        }

        return null;
    }

    function syncLocationRoute() {
        const raw = getRouteFromHash();
        const parsed = parseRoute(raw);

        if (currentUser) {
            if (parsed && parsed.isDash) {
                window.DashboardModule.selectTab(parsed.tab, false);
                window.updateBrowserUrl(parsed.route, true);
            } else {
                window.DashboardModule.selectTab('ia-preditiva', false);
                window.updateBrowserUrl('ia-preditiva', true);
            }
        } else {
            if (parsed && !parsed.isDash) {
                window.AuthModule.switchView(parsed.view, false);
                window.updateBrowserUrl(parsed.route, true);
            } else if (parsed && parsed.isDash) {
                pendingTabAfterLogin = parsed.tab;
                window.AuthModule.switchView('login', false);
                window.updateBrowserUrl('login', true);
            } else {
                window.AuthModule.switchView('login', false);
                window.updateBrowserUrl('login', true);
            }
        }
    }

    function updateAppViewMode(isAuth) {
        const appRoot = document.getElementById('appRoot');
        const authContainer = document.getElementById('authContainer');
        const dashboardSection = document.getElementById('dashboardSection');
        const bgEffects = document.getElementById('backgroundEffects');

        if (isAuth) {
            document.body.classList.remove('auth-mode');
            document.body.classList.add('dashboard-mode');
            appRoot?.classList.remove('auth-view');
            appRoot?.classList.add('dashboard-view');

            if (authContainer) authContainer.style.display = 'none';
            if (dashboardSection) dashboardSection.style.display = 'flex';
            if (bgEffects) bgEffects.style.display = 'block';
        } else {
            document.body.classList.add('auth-mode');
            document.body.classList.remove('dashboard-mode');
            appRoot?.classList.add('auth-view');
            appRoot?.classList.remove('dashboard-view');

            if (authContainer) authContainer.style.display = 'block';
            if (dashboardSection) dashboardSection.style.display = 'none';
            if (bgEffects) bgEffects.style.display = 'none';
        }
    }

    window.onAuthSuccess = function(authenticatedUser) {
        currentUser = authenticatedUser;
        updateAppViewMode(true);
        window.DashboardModule.init(authenticatedUser);

        const targetTab = pendingTabAfterLogin || 'ia-preditiva';
        pendingTabAfterLogin = null;
        window.DashboardModule.selectTab(targetTab, true);
    };

    window.onLogoutSuccess = function() {
        currentUser = null;
        updateAppViewMode(false);
        window.AuthModule.switchView('login', true);
    };

    document.addEventListener('DOMContentLoaded', () => {
        const token = window.apiService.getToken();
        const storedUser = window.apiService.getUser();
        currentUser = (token && storedUser) ? storedUser : null;

        // Inicializar módulos
        window.AuthModule.init();
        if (currentUser) {
            updateAppViewMode(true);
            window.DashboardModule.init(currentUser);
        } else {
            updateAppViewMode(false);
        }

        syncLocationRoute();

        // Ouve navegações no histórico do navegador
        window.addEventListener('popstate', syncLocationRoute);
        window.addEventListener('hashchange', syncLocationRoute);

        // Previne rolagem desnecessária no login
        window.addEventListener('wheel', (e) => {
            if (!currentUser) {
                e.preventDefault();
            }
        }, { passive: false });
    });
})();

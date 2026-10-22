/**
 * App.jsx
 * Aplicação Principal TrendCommerce AI em React 18 com Roteamento Dinâmico de URLs.
 */

// Utilitários de Rota do TrendCommerce
function getRouteFromHash() {
    return (window.location.hash || '').replace(/^#\/?/, '').trim().toLowerCase();
}

function updateBrowserUrl(route, replace = false) {
    if (!route) return;
    const targetHash = '#/' + route;

    // Se estiver usando protocolo file://, manipula estritamente o hash
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

    // Em HTTP / HTTPS: remove 'index.html' da barra para visual limpo e profissional
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
}

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

function App() {
    const [user, setUser] = React.useState(() => {
        const token = window.apiService?.getToken();
        const storedUser = window.apiService?.getUser();
        return (token && storedUser) ? storedUser : null;
    });

    const [activeTab, setActiveTab] = React.useState('ia-preditiva');
    const [authView, setAuthView] = React.useState('login');
    const [pendingTabAfterLogin, setPendingTabAfterLogin] = React.useState(null);
    const [toasts, setToasts] = React.useState([]);

    // Sincroniza a rota inicial ao carregar a página
    React.useEffect(() => {
        const raw = getRouteFromHash();
        const parsed = parseRoute(raw);

        if (user) {
            if (parsed && parsed.isDash) {
                setActiveTab(parsed.tab);
                updateBrowserUrl(parsed.route, true);
            } else {
                setActiveTab('ia-preditiva');
                updateBrowserUrl('ia-preditiva', true);
            }
        } else {
            if (parsed && !parsed.isDash) {
                setAuthView(parsed.view);
                updateBrowserUrl(parsed.route, true);
            } else if (parsed && parsed.isDash) {
                // Usuário tentou acessar tela do dashboard sem estar autenticado
                setPendingTabAfterLogin(parsed.tab);
                setAuthView('login');
                updateBrowserUrl('login', true);
            } else {
                setAuthView('login');
                updateBrowserUrl('login', true);
            }
        }
    }, [user !== null]);

    // Ouve eventos de histórico do navegador (popstate / hashchange)
    React.useEffect(() => {
        const handleLocationChange = () => {
            const raw = getRouteFromHash();
            const parsed = parseRoute(raw);

            if (user) {
                if (parsed && parsed.isDash) {
                    setActiveTab(parsed.tab);
                } else {
                    setActiveTab('ia-preditiva');
                    updateBrowserUrl('ia-preditiva', true);
                }
            } else {
                if (parsed && !parsed.isDash) {
                    setAuthView(parsed.view);
                } else if (parsed && parsed.isDash) {
                    setPendingTabAfterLogin(parsed.tab);
                    setAuthView('login');
                    updateBrowserUrl('login', true);
                } else {
                    setAuthView('login');
                    updateBrowserUrl('login', true);
                }
            }
        };

        window.addEventListener('popstate', handleLocationChange);
        window.addEventListener('hashchange', handleLocationChange);
        return () => {
            window.removeEventListener('popstate', handleLocationChange);
            window.removeEventListener('hashchange', handleLocationChange);
        };
    }, [user]);

    const showToast = React.useCallback((message, type = 'info', duration = 4000) => {
        const id = Date.now() + Math.random();
        setToasts((prev) => [...prev, { id, message, type }]);

        setTimeout(() => {
            setToasts((prev) => prev.filter((t) => t.id !== id));
        }, duration);
    }, []);

    const handleSelectTab = (tabId) => {
        if (activeTab === tabId) return;
        setActiveTab(tabId);
        updateBrowserUrl(tabId, false);
    };

    const handleSwitchAuthView = (nextView) => {
        setAuthView(nextView);
        const viewRouteMap = {
            'login': 'login',
            'register': 'cadastro',
            'recovery-1': 'recuperar-senha',
            'recovery-2': 'recuperar-senha/codigo',
            'recovery-3': 'recuperar-senha/nova-senha'
        };
        const targetRoute = viewRouteMap[nextView] || 'login';
        updateBrowserUrl(targetRoute, false);
    };

    const handleLoginSuccess = (authenticatedUser) => {
        setUser(authenticatedUser);
        const destinationTab = pendingTabAfterLogin || 'ia-preditiva';
        setPendingTabAfterLogin(null);
        setActiveTab(destinationTab);
        updateBrowserUrl(destinationTab, false);
    };

    const handleLogout = () => {
        window.apiService.auth.logout();
        setUser(null);
        setAuthView('login');
        updateBrowserUrl('login', false);
        showToast('Sessão encerrada com sucesso.', 'info');
    };

    React.useEffect(() => {
        if (user) {
            document.body.classList.remove('auth-mode');
            document.body.classList.add('dashboard-mode');
        } else {
            document.body.classList.add('auth-mode');
            document.body.classList.remove('dashboard-mode');
        }

        const handleWheel = (e) => {
            if (!user) {
                e.preventDefault();
            }
        };

        window.addEventListener('wheel', handleWheel, { passive: false });
        return () => window.removeEventListener('wheel', handleWheel);
    }, [user]);

    return (
        <div className={`app-root ${user ? 'dashboard-view' : 'auth-view'}`}>
            {user && <BackgroundEffects />}
            <ToastContainer toasts={toasts} />

            {user ? (
                <DashboardLayout
                    user={user}
                    activeTab={activeTab}
                    onSelectTab={handleSelectTab}
                    onLogout={handleLogout}
                    showToast={showToast}
                />
            ) : (
                <AuthContainer
                    currentView={authView}
                    onSwitchView={handleSwitchAuthView}
                    onLoginSuccess={handleLoginSuccess}
                    showToast={showToast}
                />
            )}
        </div>
    );
}
/**
 * Sidebar.jsx
 * Barra lateral de navegação do Dashboard TrendCommerce AI.
 */

function Sidebar({ user, activeTab, onSelectTab, onLogout, isOpen = true }) {
    const navItems = [
        { id: 'ia-preditiva', label: 'IA PREDITIVA' },
        { id: 'ranking', label: 'RANKING PRODUTOS' },
        { id: 'analise-especifica', label: 'ANÁLISE ESPECÍFICA' }
    ];

    return (
        <aside className={`dash-sidebar ${isOpen ? 'open' : 'collapsed'}`} aria-hidden={!isOpen}>
            <div className="dash-user-profile">
                <div className="user-avatar-circle">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                        <circle cx="12" cy="7" r="4"></circle>
                    </svg>
                </div>
                <div className="user-info-text">
                    <span className="user-info-name">{user?.name || user?.email || 'Administrador'}</span>
                    <button type="button" className="btn-logout-link" onClick={onLogout}>
                        Sair
                    </button>
                </div>
            </div>

            <nav className="dash-nav-menu">
                {navItems.map((item) => (
                    <button
                        key={item.id}
                        type="button"
                        className={`dash-nav-btn ${activeTab === item.id ? 'active' : ''}`}
                        onClick={() => onSelectTab(item.id)}
                    >
                        <span>{item.label}</span>
                    </button>
                ))}
            </nav>
        </aside>
    );
}
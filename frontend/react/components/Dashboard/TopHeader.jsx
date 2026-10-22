/**
 * TopHeader.jsx
 * Barra superior de status do Dashboard com indicador em tempo real da IA.
 */

function TopHeader({ isSidebarOpen = true, onToggleSidebar }) {
    return (
        <header className="dash-top-header">
            <div className="dash-header-left">
                <button
                    type="button"
                    className="sidebar-toggle-btn"
                    onClick={onToggleSidebar}
                    title={isSidebarOpen ? "Fechar menu lateral" : "Abrir menu lateral"}
                    aria-label={isSidebarOpen ? "Fechar menu lateral" : "Abrir menu lateral"}
                >
                    <span className="toggle-dot"></span>
                    <span className="toggle-dot"></span>
                    <span className="toggle-dot"></span>
                </button>
            </div>
            <div className="dash-header-right">
                <div className="dash-brand-logo">
                    <img src="assets/logo.png" alt="TrendEcommerce Logo" className="dash-brand-img" />
                </div>
            </div>
        </header>
    );
}
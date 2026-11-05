function configurarToggleSenha(inputId, buttonId) {
    const senha = document.getElementById(inputId);
    const toggleSenha = document.getElementById(buttonId);

    // Algumas páginas não possuem campo de senha ou o toggle já foi inicializado.
    if (!senha || !toggleSenha || toggleSenha.dataset.toggleInitialized) {
        return;
    }

    toggleSenha.dataset.toggleInitialized = "true";
    toggleSenha.setAttribute("aria-label", "Ver senha");
    toggleSenha.setAttribute("title", "Ver senha");

    toggleSenha.addEventListener("click", (e) => {
        e.preventDefault();
        const isPass = senha.type === "password";
        senha.type = isPass ? "text" : "password";

        const label = isPass ? "Ocultar senha" : "Ver senha";
        toggleSenha.setAttribute("aria-label", label);
        toggleSenha.setAttribute("title", label);

        const icon = toggleSenha.querySelector("i");
        if (icon) {
            icon.className = isPass ? "ph ph-eye-slash" : "ph ph-eye";
        } else {
            toggleSenha.innerHTML = isPass
                ? '<i class="ph ph-eye-slash"></i>'
                : '<i class="ph ph-eye"></i>';
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    if (typeof setupPasswordToggles === "function") {
        setupPasswordToggles();
    }
    configurarToggleSenha("senha", "toggleSenha");
    configurarToggleSenha("confirmarSenha", "toggleConfirmarSenha");
    configurarToggleSenha("loginPassword", "toggleSenha");
    configurarToggleSenha("registerPassword", "toggleRegisterSenha");
    configurarToggleSenha("registerConfirmPassword", "toggleConfirmarSenha");
    configurarToggleSenha("recoveryNewPassword", "toggleRecoverySenha");
    configurarToggleSenha("recoveryConfirmNewPassword", "toggleRecoveryConfirmar");
});

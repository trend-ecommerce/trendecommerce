function configurarToggleSenha(inputId, buttonId) {
    const senha = document.getElementById(inputId);
    const toggleSenha = document.getElementById(buttonId);

    // Algumas páginas não possuem campo de senha.
    if (!senha || !toggleSenha) {
        return;
    }

    toggleSenha.addEventListener("click", (e) => {
        e.preventDefault();
        const mostrandoSenha = senha.type === "text";

        senha.type = mostrandoSenha ? "password" : "text";
        toggleSenha.innerHTML = mostrandoSenha
            ? '<i class="ph ph-eye"></i>'
            : '<i class="ph ph-eye-slash"></i>';
    });
}

document.addEventListener("DOMContentLoaded", () => {
    configurarToggleSenha("senha", "toggleSenha");
    configurarToggleSenha("confirmarSenha", "toggleConfirmarSenha");
    configurarToggleSenha("loginPassword", "toggleSenha");
    configurarToggleSenha("registerPassword", "toggleRegisterSenha");
    configurarToggleSenha("registerConfirmPassword", "toggleConfirmarSenha");
    configurarToggleSenha("recoveryNewPassword", "toggleRecoverySenha");
    configurarToggleSenha("recoveryConfirmNewPassword", "toggleRecoveryConfirmar");
});

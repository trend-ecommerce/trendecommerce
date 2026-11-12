# TrendEcommerce AI - Frontend (Autenticação)

Interface web moderna com tema dark/cyberpunk de alta fidelidade para o sistema **TrendEcommerce AI - Sistema Preditivo de Vendas e Inteligência de Dados**.

---

## 📸 Telas e Fluxos Implementados

1. **Tela de Login (`BEM-VINDO DE VOLTA!`)**:
   - Campos: Email e Senha com alternador de visibilidade (ícone de olho).
   - Botão **ENTRAR** e link para recuperação *"Esqueceu a senha? Clique aqui."*.
   - Transição dinâmica para a tela de cadastro.

2. **Tela de Cadastro (`ACESSE SUA CONTA` / `CADASTRAR`)**:
   - Campos: Email, Senha e Confirmação de Senha.
   - Validações em tempo real de formato de email e tamanho de senha.
   - Botão **CADASTRAR** e botão lateral **ENTRAR**.

3. **Recuperação de Senha - Etapa 1 (`ENVIAREMOS UM CÓDIGO PARA SEU EMAIL`)**:
   - Campo: Email para envio do código de 6 dígitos via Supabase Auth.
   - Botão **ENVIAR**.

4. **Recuperação de Senha - Etapa 2 (`DIGITE SEU CÓDIGO`)**:
   - 6 campos circulares de dígitos OTP com avanço automático, suporte a backspace, colagem direta e preenchimento automático (`one-time-code`).
   - Opção de reenviar código.
   - Botão **ENVIAR**.

5. **Recuperação de Senha - Etapa 3 (`NOVA SENHA / LOGIN`)**:
   - Campos: Email, Nova Senha e Confirmação de Senha com alternador de visualização.
   - Botão **LOGIN** para redefinição (sincronizada no banco local e no Supabase Auth) e acesso imediato.

6. **Painel de Sessão Conectada (`ia-preditiva.html`)**:
   - Interface principal autenticada com dados do usuário ativo, gráficos e análises preditivas.

---

## 🚀 Como Executar

Execute no terminal a partir da raiz do projeto:

```bash
python main.py
```
Abra o navegador em: **`http://localhost:8000/app/login.html`** (ou **`http://localhost:8000/`**).

---

## 🔑 Credenciais Padrão para Teste

- **Email:** `admin@trendecommerce.com`
- **Senha:** `admin123`

*(Você também pode cadastrar novas contas ou recuperar a senha interativamente direto na interface).*

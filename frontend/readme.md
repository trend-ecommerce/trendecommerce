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
   - Campo: Email para envio do código de 4 dígitos.
   - Botão **ENVIAR**.

4. **Recuperação de Senha - Etapa 2 (`DIGITE SEU CÓDIGO`)**:
   - 4 campos circulares de dígitos OTP com avanço automático, suporte a backspace e colagem direta.
   - Opção de reenviar código.
   - Botão **ENVIAR**.

5. **Recuperação de Senha - Etapa 3 (`NOVA SENHA / LOGIN`)**:
   - Campos: Nova Senha e Confirmação de Senha com alternador de visualização.
   - Botão **LOGIN** para redefinição e acesso imediato.

6. **Painel de Sessão Conectada**:
   - Demonstração do estado pós-login com dados do usuário ativo e status online.

---

## 🚀 Como Executar

### Opção 1: Via Python Server (Recomendado)
Execute no terminal a partir da raiz do projeto:

```bash
python frontend/server.py
```
Abra o navegador em: **`http://localhost:8000`**

### Opção 2: Abertura Direta
Abra o arquivo `frontend/index.html` diretamente em qualquer navegador moderno.

---

## 🔑 Credenciais Padrão para Teste

- **Email:** `admin@trendecommerce.com`
- **Senha:** `admin123`

*(Você também pode cadastrar novas contas ou recuperar a senha interativamente direto na interface).*

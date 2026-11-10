<div align="center">

  <img src="frontend/img/banner.png" alt="TrendEcommerce AI Logo" width="750" style="max-width: 100%; height: auto; border-radius: 8px; margin-bottom: 20px;" />

  # 🚀 TrendEcommerce AI

  <p><strong>Plataforma Fullstack de Inteligência Preditiva de Demanda, Gestão de Catálogo e Análise Estratégica de Vendas para E-commerce</strong></p>

  <p>
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.14-blue.svg" alt="Python Version" /></a>
    <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white" alt="FastAPI" /></a>
    <a href="https://xgboost.readthedocs.io/"><img src="https://img.shields.io/badge/XGBoost-2.0+-eb6024.svg" alt="XGBoost" /></a>
    <a href="https://www.sqlalchemy.org/"><img src="https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg" alt="SQLAlchemy" /></a>
    <a href="tests/"><img src="https://img.shields.io/badge/Tests-50%20passed%20%7C%20100%25-brightgreen.svg" alt="Tests" /></a>
  </p>

  <p>
    <a href="#-visão-geral">Visão Geral</a> •
    <a href="#-funcionalidades-chave">Funcionalidades</a> •
    <a href="#-arquitetura-do-sistema">Arquitetura</a> •
    <a href="#-estrutura-de-pastas">Estrutura</a> •
    <a href="#-instalação-e-configuração">Instalação</a> •
    <a href="#-como-executar">Como Executar</a> •
    <a href="#-documentação-da-api-endpoints">Endpoints da API</a> •
    <a href="#-qualidade-e-testes">Testes</a> •
    <a href="#-deploy">Deploy</a>
  </p>

</div>

---

## 📌 Visão Geral

O **TrendEcommerce AI** é uma plataforma web fullstack voltada à previsão de demanda e inteligência comercial para e-commerce. O sistema conecta-se à **API de Histórico de Vendas** (composta por **500 produtos** distribuídos em **5 categorias** e **1.253.000 registros históricos diários**), combinando **engenharia de features temporais e estatísticas** com **Machine Learning (XGBoost)** para oferecer:

- **Projeções de demanda futura e Linha do Tempo Híbrida** para horizontes de **7, 14 e 30 dias** combinados a janelas históricas de **1 mês, 6 meses, 1 ano e 5 anos**, com intervalos de confiança (`confidence_min` / `confidence_max`), estimativa de faturamento e cálculo de estoque de segurança recomendado.
- **Explicabilidade de Inteligência Artificial (XAI)** calculada dinamicamente a partir do *gain* real das árvores do XGBoost, detalhando o peso percentual e o impacto de cada fator determinante da previsão (*Média Recente*, *Tendência de Mercado*, *Sazonalidade Semanal* e *Competitividade*).
- **Busca Inteligente com Similaridade de Caracteres (Fuzzy Search)** no catálogo oficial, sugerindo produtos cadastrados mesmo quando o usuário digita termos com erros de grafia e informando claramente quando um produto não existe no catálogo.
- **Rankings Preditivos orientados pelo Índice de Tração Preditiva (PTI)** (*Top 7 Geral* com equilíbrio setorial e *Top 5 por Categoria*), **Matriz de Oportunidades Comerciais (POI)** e **Exportação Executiva de Relatórios em `.CSV` (Excel)**.
- **Autenticação Completa e Segura** com JWT, integração com **Supabase Auth**, **Google Identity Services (OAuth / OTP)** e envio de códigos de verificação por e-mail via **SMTP Gmail**.

---

## ⚡ Funcionalidades Chave

### 🧠 1. Motor Preditivo de Machine Learning (`src/ml/`)
- **Previsões para 7, 14 e 30 Dias e Linha do Tempo Híbrida (`FutureForecaster`)**: Projeção diária autoregressiva de demanda e receita para qualquer produto do catálogo, com carregamento otimizado do artefato pré-treinado (`models/xgboost_demand_v1.json`, `<80MB RAM`) no startup do servidor e cache em memória para respostas instantâneas (`<30ms`).
- **Pipeline de Treinamento de Baixa Memória (`train_pipeline.py`)**: Treinamento do `XGBRegressor` (100 árvores, `max_depth=5`, `learning_rate=0.08`, `R² ≈ 0.986` em teste) sobre os 1,25M de registros históricos com *downcasting* numérico (`float32`).
- **Intervalos de Confiança e Estoque Recomendado (`DemandPredictor`)**: Cálculo dinâmico de limites inferior e superior e recomendação automática de buffer de estoque.
- **Explicabilidade Dinâmica da IA (XAI)**: Decomposição transparente de cada previsão em 4 pilares calculados a partir da importância real (`gain`) das features do modelo XGBoost:
  1. *Média Recente (~52%)*: Base orientada pelos volumes e médias móveis de 7 e 30 dias.
  2. *Tendência de Mercado (~42%)*: Taxa de variação percentual e aceleração de curto prazo da demanda.
  3. *Sazonalidade Semanal (~3%)*: Variação cíclica por dia da semana, mês e padrão de compra.
  4. *Competitividade (~3%)*: Posicionamento e variação do preço unitário frente ao histórico.
- **Comparador Preditivo Lado a Lado (`/api/v1/forecast/compare`)**: Confronto direto entre dois produtos (`product_id_a` vs. `product_id_b`), apontando o líder em volume de vendas, o líder em faturamento e um veredito estratégico automático.
- **Auditoria e Recomendações (`DemandComparator` & `OpportunityRecommender`)**: Validação histórica (*backtesting* Real vs. Previsto com `RMSE`, `MAE`, `MAPE` e `R²`) e classificação de produtos em quadrantes estratégicos (`OPORTUNIDADE_EXPLOSIVA`, `ALTA_RENTABILIDADE`, `DEMANDA_MODERADA`, `BAIXA_PRIORIDADE`).

### 📦 2. Integração com a API de Histórico de Vendas (`VendasApiClient`)
- **Catálogo Oficial**: 500 produtos ativos em 5 categorias (*Eletrônicos*, *Moda e acessórios*, *Casa e decoração*, *Esportes e fitness*, *Beleza e cuidados pessoais*) e 1.253.000 registros de vendas históricas (2020 a 2026).
- **Duplo Canal de Operação (HTTP + SQLite `ATTACH DATABASE`)**: Consome a API externa em `http://127.0.0.1:8001` e realiza sincronização em lote de alta velocidade diretamente a partir do arquivo `historico_vendas.db` caso o servidor externo não esteja em execução.
- **Auto-Seed no Startup (`seed_loader.py`)**: Ao iniciar a aplicação, o sistema verifica automaticamente se o banco local (`data/trendcommerce_dev.db`) está vazio ou desatualizado e sincroniza todos os produtos e séries temporais da API oficial.
- **Busca por Similaridade de Caracteres (`search_catalog_products`)**: Utiliza normalização Unicode e `difflib.SequenceMatcher` para recomendar produtos cadastrados com grafia parecida (ex.: `notbook` → *Notebook*, `cretina` → *Creatina*) e bloqueia termos inválidos/inexistentes com mensagem clara de produto não encontrado.

### 🔬 3. Engenharia de Features (`FeatureEngineer`)
- **Sanitização Determinística de Séries (`sanitize_sales_series`)**: Tratamento automático de quedas bruscas/zeros espúrios e picos isolados preservando a sazonalidade real entre janelas de `1m`, `6m`, `1y` e `5y`.
- **Features de Vendas e Preço (`create_sales_features`)**:
  - Somas e médias móveis de 7 e 30 dias (`vendas_7_dias`, `vendas_30_dias`, `media_vendas_7_dias`, `media_vendas_30_dias`).
  - Taxas de crescimento (`crescimento_vendas`, `crescimento_vendas_7d`).
  - Dinâmica de preços (`preco_medio_7_dias`, `variacao_preco`, `preco_min_30d`, `preco_max_30d`, `preco_posicao_range`).
- **Features Temporais e Cíclicas (`create_temporal_features`)**:
  - Calendário (`dia_semana`, `dia_mes`, `mes`, `semana_ano`, `eh_fim_semana`, `eh_inicio_mes`, `eh_fim_mes`).
  - Transformações trigonométricas cíclicas (`dia_semana_sin`, `dia_semana_cos`, `mes_sin`, `mes_cos`).

### 💻 4. Frontend Web Multi-Páginas (`frontend/`)
Interface construída em **HTML5**, **CSS3 (Glassmorphism / Cyberpunk UI)** e **Vanilla JavaScript**, servida diretamente pelo FastAPI em `/app`:
- **IA Preditiva (`ia-preditiva.html` / `ia-preditiva.js`)**: Painel principal com gráfico interativo em Canvas para Linha do Tempo Híbrida (histórico passado de **1m, 6m, 1y, 5y** + projeções futuras de **7, 14 e 30 dias**), filtro por categoria, **Top 5 Produtos Mais Vendidos no Mês** e modal de **Exportação Executiva para Excel (`.CSV`)**.
- **Ranking de Produtos (`ranking.html` / `ranking.js`)**: Exibição do **Top 7 Produtos no Geral** e **Top 5 por Categoria** para os próximos 30 dias baseados no **Índice de Tração Preditiva (PTI)**, com **Modal de Explicabilidade (XAI)** ao clicar em qualquer item do ranking.
- **Análise Específica (`analise-especifica.html` / `analise-especifica.js`)**: Busca inteligente com autocomplete e tolerância a erros de digitação, cards de KPIs preditivos (Unidades Previstas, Faturamento Projetado, Média Diária e Estoque de Segurança), gráfico diário interativo e **Painel XAI completo** com os 4 fatores determinantes.
- **Autenticação Completa (`login.html`, `cadastro.html`, `recuperar-senha.html` / `recuperarsenha.html`, `codigo-verificacao.html` / `codigosenha.html`, `nova-senha.html` / `novasenha.html`)**: Fluxo de login tradicional, login com Google, confirmação de e-mail e redefinição de senha via código OTP.

---

## 🏗️ Arquitetura do Sistema

```text
                    ┌───────────────────────────────────────────────┐
                    │          API de Histórico de Vendas           │
                    │  (500 Produtos | 5 Categorias | 1.25M Vendas) │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │         VendasApiClient & SeedLoader          │
                    │  - Cliente HTTP (Porta 8001)                  │
                    │  - Sincronização Rápida SQLite (ATTACH DB)    │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │          Camada de Dados (SQLAlchemy)         │
                    │  - Tabelas: users, products, sales_history    │
                    │  - SQLite (Local) / PostgreSQL & Supabase     │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │      FeatureEngineer & Núcleo ML (XGBoost)    │
                    │  - 23 Features de Vendas (7d/30d) e Temporais │
                    │  - DemandTrainer, DemandPredictor & Comparator│
                    │  - FutureForecaster (7/14/30d + XAI Dinâmico) │
                    │  - OpportunityRecommender (Matriz POI)        │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │           API REST FastAPI (/api/v1)          │
                    │  - /auth (JWT, Google OAuth, Supabase, OTP)   │
                    │  - /products (Catálogo, Top Sales, Fuzzy)     │
                    │  - /forecast (Predict, Timeline, Ranking, Cmp)│
                    │  - /recommendations (Top Products POI)        │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │       Frontend Web (HTML5 / CSS3 / JS)        │
                    │  - IA Preditiva (Timeline Híbrida + CSV)      │
                    │  - Ranking 30d (PTI + Modal XAI)              │
                    │  - Análise Específica (Busca Fuzzy + XAI)     │
                    └───────────────────────────────────────────────┘
```

---

## 📂 Estrutura de Pastas

```text
trendecommerce/
├── config/
│   └── settings.py                        # Configurações globais (Pydantic Settings)
├── data/
│   └── trendcommerce_dev.db               # Banco de dados SQLite local (gerado automaticamente)
├── frontend/                              # Aplicação Web Frontend (HTML5, CSS3 e Vanilla JS)
│   ├── assets/                            # Imagens de fundo (bg-logins.png) e logotipo (logo.png)
│   ├── img/
│   │   └── banner.png                     # Banner oficial do TrendEcommerce AI
│   ├── css/
│   │   ├── login.css                      # Estilos das páginas de autenticação
│   │   └── style.css                      # Estilos do dashboard, modais e componentes
│   ├── js/
│   │   ├── analise-especifica.js          # Busca inteligente no catálogo, KPIs, gráfico e painel XAI
│   │   ├── api.js                         # Cliente HTTP centralizado para consumo de /api/v1
│   │   ├── auth.js                        # Autenticação JWT, Google OAuth, OTP e validação de sessão
│   │   ├── effects.js                     # Efeitos visuais de interface
│   │   ├── ia-preditiva.js                # Linha do tempo híbrida (1m..5y + 7/14/30d), Top 5 e exportação CSV
│   │   ├── ranking.js                     # Top 7 geral, Top 5 por categoria e modal XAI
│   │   └── sidebar.js                     # Barra de navegação lateral e controle de usuário
│   ├── analise-especifica.html            # Página de Análise Específica por Produto
│   ├── cadastro.html                      # Página de Cadastro de Usuário
│   ├── codigo-verificacao.html            # Página de Confirmação de Código OTP
│   ├── codigosenha.html                   # Etapa de código OTP na recuperação de senha
│   ├── ia-preditiva.html                  # Página Principal (IA Preditiva & Relatório Executivo)
│   ├── index.html                         # Ponto de entrada do Frontend
│   ├── login.html                         # Página de Login
│   ├── nova-senha.html / novasenha.html   # Página de Redefinição de Senha
│   ├── ranking.html                       # Página de Ranking Preditivo de Produtos
│   ├── recuperar-senha.html / recuperarsenha.html # Solicitação de Recuperação de Senha
│   ├── script.js                          # Controlador de fluxos de autenticação das telas de login
│   └── server.py                          # Servidor HTTP auxiliar opcional para o frontend
├── models/                                # Artefatos pré-treinados do modelo XGBoost
│   ├── features_metadata.json             # Metadados das 23 features, hiperparâmetros e métricas (R² 0.986)
│   └── xgboost_demand_v1.json             # Modelo XGBRegressor serializado para inferência rápida (<80MB RAM)
├── scripts/
│   └── update_historical_data_to_nov30.py # Script de recalibração sazonal e sincronização histórica (2020-2026)
├── src/
│   ├── api/                               # Aplicação FastAPI e Rotas REST
│   │   ├── routers/
│   │   │   ├── auth_router.py             # Login, Cadastro, Google OAuth, Verificação de E-mail e OTP
│   │   │   ├── forecast_router.py         # Previsões XGBoost, Timeline Híbrida, Resumo, Ranking e Comparador
│   │   │   ├── opportunity_router.py      # Recomendações de produtos e Matriz de Oportunidades (POI)
│   │   │   └── products_router.py         # Catálogo, Top Vendas, Autocomplete Fuzzy e Sincronização
│   │   ├── services/
│   │   │   ├── email_service.py           # Envio de e-mails transacionais e códigos OTP via SMTP
│   │   │   └── supabase_service.py        # Sincronização e validação de usuários com Supabase Auth
│   │   ├── dependencies.py                # Sessão de banco, segurança JWT/Bcrypt e warmup do XGBoost
│   │   └── main.py                        # Configuração do FastAPI, CORS, lifespan e montagem do /app
│   ├── database/                          # Persistência e ORM (SQLAlchemy)
│   │   ├── connection.py                  # Gerenciador de conexões e sessões (SQLite / PostgreSQL)
│   │   ├── models.py                      # Modelos ORM: User, Product e SalesHistory
│   │   ├── seed_loader.py                 # Auto-sincronização inicial com a API de Vendas
│   │   └── setup.py                       # CLI de gerenciamento do banco (create, drop, seed, sync, status, reset)
│   ├── features/
│   │   └── feature_engineering.py         # Sanitização de séries e criação de features de vendas, preços e temporais
│   ├── ml/                                # Núcleo de Machine Learning (XGBoost)
│   │   ├── comparator.py                  # Backtesting e auditoria Real vs. Previsto
│   │   ├── evaluation.py                  # Métricas de avaliação (RMSE, MAE, MAPE, R²)
│   │   ├── future_forecaster.py           # Projeção para 7, 14 e 30 dias com explicabilidade dinâmica (XAI)
│   │   ├── opportunity_recommender.py     # Cálculo de Opportunity Score e quadrantes estratégicos
│   │   ├── predictor.py                   # Inferência com cálculo de intervalos de confiança
│   │   ├── train_pipeline.py              # Pipeline executável de treinamento do XGBoost em baixa memória
│   │   └── trainer.py                     # Treinamento, validação e persistência do XGBRegressor
│   ├── schemas/                           # Modelos Pydantic de Request/Response
│   │   ├── auth_schema.py
│   │   ├── forecast_schema.py
│   │   └── product_schema.py
│   └── services/                          # Serviços de Negócio e Integração
│       ├── forecast_service.py            # Orquestração de treinamento e relatórios de previsão
│       ├── recommendation_service.py      # Serviço de recomendações comerciais
│       └── vendas_api_client.py           # Cliente HTTP e sincronizador SQLite da API de Histórico de Vendas
├── tests/                                 # Suíte de Testes Automatizados (Pytest - 50 testes)
│   ├── conftest.py                        # Fixtures compartilhadas de vendas e produtos
│   ├── test_acceptance_e2e.py             # Testes E2E de aceitação (jornadas CA-01 a CA-05)
│   ├── test_api.py                        # Testes de rotas REST, autenticação, busca fuzzy, timeline e previsão
│   ├── test_comparator.py                 # Testes de validação e backtesting
│   ├── test_feature_engineering.py        # Testes de geração de features de vendas e temporais
│   ├── test_integration_system.py         # Testes de integração de ponta a ponta entre módulos
│   ├── test_ml.py                         # Testes de treinamento, predição e métricas do XGBoost
│   ├── test_opportunity_recommender.py    # Testes da matriz de oportunidades
│   └── test_unit_core.py                  # Testes unitários de segurança, validação de e-mail, XAI e sanitização
├── .env.example                           # Modelo de variáveis de ambiente
├── iniciar_api_vendas.bat                 # Script Windows para iniciar a API de Vendas na porta 8001
├── main.py                                # Ponto de entrada principal do servidor (Porta 8000)
├── render.yaml                            # Configuração de deploy em nuvem (Render)
├── requirements.txt                       # Dependências Python do projeto
├── setup.py                               # Metadados do pacote Python
└── vercel.json                            # Configuração de deploy do frontend (Vercel)
```

---

## ⚙️ Instalação e Configuração

### Pré-requisitos
- **Python 3.11+**
- **Git**

### 1. Clonar o Repositório
```bash
git clone https://github.com/trend-ecommerce/trendecommerce.git
cd trendecommerce
```

### 2. Criar e Ativar o Ambiente Virtual

- **Windows (PowerShell):**
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```

- **Linux / macOS:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

### 3. Instalar as Dependências
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### 4. Variáveis de Ambiente (`.env`)
O projeto já funciona localmente por padrão utilizando SQLite (`data/trendcommerce_dev.db`). Para configurar credenciais de e-mail SMTP, Google OAuth ou Supabase, copie o arquivo `.env.example` para `.env`:

```powershell
copy .env.example .env
```

Principais variáveis disponíveis em `.env`:
```env
# Segurança & Criptografia JWT
JWT_SECRET_KEY=sua-chave-secreta-super-segura-aqui-troque-em-producao
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Banco de Dados (SQLite local por padrão, ou PostgreSQL para produção)
DATABASE_URL=sqlite:///data/trendcommerce_dev.db

# Microserviço API de Histórico de Vendas
VENDAS_API_URL=http://127.0.0.1:8001

# Serviço de Envio de E-mail (Recuperação de senha e OTP via SMTP Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=trendeccomerceai@gmail.com
SMTP_PASSWORD=sua-senha-de-app-gerada-no-google

# Google Identity Services & Supabase
GOOGLE_CLIENT_ID=seu_client_id.apps.googleusercontent.com
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_ANON_KEY=sua_chave_anon_supabase
```

---

## 🚀 Como Executar

### Passo 1: Iniciar a API de Histórico de Vendas (Porta 8001)
No Windows, você pode iniciar o servidor da API de Histórico de Vendas executando:
```powershell
.\iniciar_api_vendas.bat
```
- **Swagger da API de Vendas:** `http://127.0.0.1:8001/docs`
- **Health Check:** `http://127.0.0.1:8001/health`

> **Nota:** Caso o executável da porta `8001` não esteja aberto, o `VendasApiClient` localiza automaticamente o arquivo `historico_vendas.db` e sincroniza os **500 produtos** e **1.253.000 registros de vendas** diretamente para o banco local.

### Passo 2: Iniciar o Servidor Principal TrendEcommerce AI (Porta 8000)
```powershell
python main.py
```
*(Ou `python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000`)*

Acesse no navegador:
- 🌐 **Aplicação Web (Frontend):** **`http://localhost:8000/app/login.html`** (ou **`http://localhost:8000/`**, que redireciona para `/app/ia-preditiva.html`)
- 📖 **Documentação Interativa (Swagger UI):** **`http://localhost:8000/docs`**
- 📑 **Documentação ReDoc:** **`http://localhost:8000/redoc`**

> **Credenciais Padrão de Administrador (criadas automaticamente no startup):**
> - **E-mail:** `admin@trendecommerce.com`
> - **Senha:** `admin123`

---

### Utilitário CLI de Banco de Dados e Treinamento ML

```powershell
# Verificar status e contagem de registros (usuários, produtos e vendas)
python -m src.database.setup status

# Recriar todas as tabelas do zero e ressincronizar os 500 produtos da API de Vendas
python -m src.database.setup reset

# Sincronizar/atualizar catálogo e histórico de vendas
python -m src.database.setup sync

# Re-treinar o modelo XGBoost sobre a base histórica completa
python -m src.ml.train_pipeline
```

---

## 📖 Documentação da API (Endpoints)

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| **Autenticação (`/api/v1/auth`)** | | |
| `POST` | `/api/v1/auth/register` | Cadastra novo usuário ativo (`is_active=True`) e sincroniza com o Supabase |
| `POST` | `/api/v1/auth/verify-email` | Confirma o código OTP de verificação de cadastro e retorna token JWT |
| `POST` | `/api/v1/auth/resend-verification` | Reenvia o e-mail/código de confirmação de cadastro |
| `POST` | `/api/v1/auth/login` | Autentica usuário (com rate limiting) e retorna token JWT |
| `POST` | `/api/v1/auth/google` | Autentica ou cadastra usuário via Google Identity Services (GIS) |
| `POST` | `/api/v1/auth/google/request-code` | Solicita código OTP por e-mail para validação de conta Google |
| `POST` | `/api/v1/auth/google/verify-code` | Valida código OTP do Google e retorna token JWT |
| `GET` | `/api/v1/auth/me` | Retorna os dados do perfil do usuário autenticado |
| `POST` | `/api/v1/auth/forgot-password` | Gera e envia código OTP de 4 dígitos para recuperação de senha |
| `POST` | `/api/v1/auth/verify-reset-code` | Valida o código OTP de recuperação antes da redefinição de senha |
| `POST` | `/api/v1/auth/reset-password` | Redefine a senha do usuário validando o código OTP |
| **Produtos & Catálogo (`/api/v1/products`)** | | |
| `GET` | `/api/v1/products` | Lista paginada de produtos com filtros de busca, categoria e plataforma |
| `POST` | `/api/v1/products` | Cadastra um novo produto no catálogo |
| `GET` | `/api/v1/products/categories` | Lista todas as categorias com produtos ativos |
| `GET` | `/api/v1/products/top-sales` | Ranking dos produtos mais vendidos no período (padrão: últimos 30 dias) |
| `GET` | `/api/v1/products/autocomplete` | Sugestões de produtos por correspondência direta ou similaridade de caracteres |
| `POST` | `/api/v1/products/discover-live` | Busca produtos no catálogo oficial (retorna `404` se não cadastrado) |
| `GET` | `/api/v1/products/{product_id}` | Detalhes de um produto específico e histórico recente |
| `GET` | `/api/v1/products/{product_id}/history` | Série temporal de vendas do produto (`days=7..1000`) |
| `POST` | `/api/v1/products/{product_id}/sales` | Registra uma nova venda para o produto |
| `GET` | `/api/v1/products/api-status` | Verifica o status de conexão com a API de Histórico de Vendas |
| `POST` | `/api/v1/products/sync-categories` | Sincroniza manualmente os produtos e vendas da API oficial |
| **Previsão de Demanda & IA (`/api/v1/forecast`)** | | |
| `POST` | `/api/v1/forecast/predict` | Projeção de demanda para 7, 14 ou 30 dias com intervalos de confiança e XAI |
| `GET` | `/api/v1/forecast/timeline/{product_id}` | Linha do tempo híbrida (histórico `1m`, `6m`, `1y`, `5y` + projeção XGBoost `7/14/30d`) |
| `GET` | `/api/v1/forecast/product/{product_id}/timeline` | Alias para a rota de linha do tempo híbrida do produto |
| `GET` | `/api/v1/forecast/summary` | Resumo executivo consolidado de previsões de todos os produtos ativos |
| `GET` | `/api/v1/forecast/ranking` | Ranking preditivo Top 7 Geral e Top 5 por Categoria (PTI) com justificativas da IA |
| `POST` | `/api/v1/forecast/compare` | Comparador preditivo lado a lado (`product_id_a` vs. `product_id_b`) |
| **Recomendações & Saúde do Sistema** | | |
| `GET` | `/api/v1/recommendations/top-products` | Melhores oportunidades comerciais classificadas por score e quadrante (POI) |
| `GET` | `/api/v1/health` | Health check da API, banco de dados e modelo XGBoost |
| `GET/POST` | `/api/v1/admin/reseed` | Recarrega e sincroniza o catálogo e histórico inicial |
| `GET` | `/api/v1/debug/status` | Contagem detalhada de usuários, produtos e histórico de vendas |

---

## 🧪 Qualidade e Testes

A suíte de testes automatizados utiliza **Pytest** e cobre testes unitários, de integração e de aceitação (E2E): autenticação (login, registro, Google OAuth, OTP e recuperação de senha), rotas de catálogo, busca por similaridade de caracteres, linha do tempo híbrida (`1m`, `6m`, `1y`, `5y`), engenharia de features, treinamento/inferência do modelo XGBoost, backtesting (`DemandComparator`) e recomendação de oportunidades (`OpportunityRecommender`).

Para executar todos os testes:
```powershell
pytest -v
```

Status atual da suíte:
```text
======================= 50 passed in 26.15s =======================
```

---

## ☁️ Deploy

- **Render (Backend + Frontend integrados):** Configurado no arquivo [`render.yaml`](render.yaml), inicializando o servidor via `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`.
- **Vercel (Frontend Estático):** Configurado no arquivo [`vercel.json`](vercel.json), servindo os arquivos estáticos do diretório `frontend/`.

---

<div align="center">
Desenvolvido com Python, FastAPI, SQLAlchemy e XGBoost por <b>TrendEcommerce AI Team</b>.
</div>

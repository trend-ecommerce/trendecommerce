<div align="center">

  <img src="frontend/img/banner.png" alt="TrendCommerce AI Logo" width="750" style="max-width: 100%; height: auto; border-radius: 8px; margin-bottom: 20px;" />

  # 🚀 TrendCommerce AI

  <p><strong>Plataforma Fullstack de Inteligência Preditiva de Demanda, Gestão de Catálogo e Análise Estratégica de Vendas para E-commerce</strong></p>

  <p>
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.14-blue.svg" alt="Python Version" /></a>
    <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white" alt="FastAPI" /></a>
    <a href="https://xgboost.readthedocs.io/"><img src="https://img.shields.io/badge/XGBoost-2.0+-eb6024.svg" alt="XGBoost" /></a>
    <a href="https://www.sqlalchemy.org/"><img src="https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg" alt="SQLAlchemy" /></a>
    <a href="tests/"><img src="https://img.shields.io/badge/Tests-30%20passed%20%7C%20100%25-brightgreen.svg" alt="Tests" /></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
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

O **TrendCommerce AI** é uma plataforma de inteligência comercial e previsão de demanda para e-commerce. O sistema integra-se à **API Oficial de Histórico de Vendas** (500 produtos distribuídos em 5 categorias e mais de 518 mil registros históricos diários), combinando **engenharia de features temporais e estatísticas** com **modelagem preditiva via XGBoost** para entregar:

- **Projeções de demanda futura** para horizontes de **7, 14 e 30 dias**, acompanhadas de intervalos de confiança e recomendações de estoque.
- **Explicabilidade de Inteligência Artificial (XAI)** detalhando os fatores que impulsionam cada previsão (média recente, sazonalidade semanal, competitividade de preço e tendência de mercado).
- **Busca Inteligente com Tolerância a Erros (Fuzzy Matching)** no catálogo oficial, sugerindo produtos cadastrados por similaridade de caracteres.
- **Matriz Estratégica de Oportunidades (POI)** e **Rankings Preditivos** por categoria e volume mensal de vendas.
- **Interface Web Moderna em HTML5, CSS3 (Glassmorphism) e Vanilla JS**, com páginas dedicadas e gráficos interativos em Canvas.

---

## ⚡ Funcionalidades Chave

### 🧠 1. Motor Preditivo de Machine Learning (XGBoost)
- **Previsões Autoregressivas Flexíveis**: Suporte nativo a horizontes de projeção de **7, 14 e 30 dias**.
- **Intervalos de Confiança Estatísticos**: Cálculo de limites inferior e superior para dimensionamento seguro de estoque.
- **Explicabilidade do Modelo (XAI)**: Decomposição transparente das previsões em 4 pilares:
  1. *Média Recente*: Ritmo de vendas observado nos últimos 14 dias.
  2. *Sazonalidade Semanal*: Comportamento cíclico entre dias úteis e finais de semana.
  3. *Competitividade de Preço*: Posicionamento do preço atual frente ao histórico da categoria.
  4. *Tendência de Mercado*: Aceleração ou desaceleração recente da demanda.
- **Comparador Preditivo Lado a Lado**: Confronto direto de demanda projetada e receita estimada entre dois produtos do catálogo (`Produto A vs. Produto B`).
- **Rankings Preditivos Automatizados**: Identificação do *Top 7 Geral* e *Top 5 por Categoria* para os próximos 30 dias.

### 📦 2. Integração com a API de Histórico de Vendas (`VendasApiClient`)
- **Catálogo Oficial Unificado**: 500 produtos ativos em 5 categorias (*Eletrônicos*, *Moda e acessórios*, *Casa e decoração*, *Esportes e fitness*, *Beleza e cuidados pessoais*) e mais de 518.500 registros de vendas.
- **Duplo Canal de Sincronização (HTTP + Fallback SQLite)**: Consome o serviço externo na porta `8001` e possui fallback automático via `ATTACH DATABASE` diretamente no banco SQLite de histórico caso o serviço externo esteja offline.
- **Auto-Seed Inteligente no Startup**: Ao iniciar o servidor, o módulo `seed_loader.py` verifica automaticamente se o banco está vazio ou desatualizado e sincroniza o catálogo oficial.
- **Busca por Similaridade de Caracteres**: Na aba de *Análise Específica*, pesquisas com erros de digitação (ex.: `notbook`, `baton`, `cretina`, `smartfone`) recomendam produtos reais cadastrados com grafia semelhante, e buscas por itens inexistentes retornam aviso claro de produto não encontrado.

### 🔬 3. Engenharia de Features (`FeatureEngineer`)
- **Features de Histórico de Vendas**: Médias móveis (`media_movel_7d`, `media_movel_30d`), desvios, somatórios móveis, taxas de variação (`crescimento_vendas`, `crescimento_vendas_7d`) e posição relativa de preço.
- **Features Temporais e Cíclicas**: Codificação trigonométrica (`dia_semana_sin/cos`, `mes_sin/cos`), flags de fim de semana, início/fim de mês e proximidade de feriados nacionais.

### 📊 4. Auditoria e Recomendações (`DemandComparator` & `OpportunityRecommender`)
- **Backtesting Histórico**: Validação do modelo comparando previsões com vendas reais consumidas (`RMSE`, `MAE`, `R²` e `Hit Rate %`).
- **Matriz de Oportunidades (POI)**: Classificação de produtos em quadrantes estratégicos com score de 0 a 100 e recomendação de estoque.

### 💻 5. Frontend Web Multi-Páginas (HTML5 + CSS3 + Vanilla JS)
- Arquitetura limpa sem dependência de bundlers pesados, utilizando **HTML5 semântico**, **CSS3 com efeito Glassmorphism** alinhado aos protótipos do Figma e **JavaScript puro modular**:
  - **IA Preditiva (`ia-preditiva.html`)**: Visão geral de métricas, top 10 vendas no mês por categoria e comparador preditivo.
  - **Ranking de Produtos (`ranking.html`)**: Destaques preditivos gerais e filtrados por categoria com justificativa da IA.
  - **Análise Específica (`analise-especifica.html`)**: Busca inteligente no catálogo, curva projetada para 7/14/30 dias e painel XAI.
  - **Fluxo Completo de Autenticação**: Telas dedicadas de Login (`login.html`), Cadastro (`cadastro.html`), Recuperação de Senha (`recuperar-senha.html`), Código de Verificação OTP (`codigo-verificacao.html`) e Nova Senha (`nova-senha.html`).

---

## 🏗️ Arquitetura do Sistema

```text
                    ┌───────────────────────────────────────────────┐
                    │       API Oficial de Histórico de Vendas      │
                    │   (500 Produtos | 5 Categorias | 518k Vendas) │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │         VendasApiClient & SeedLoader          │
                    │   - Conector HTTP (Porta 8001)                │
                    │   - Fallback Instantâneo SQLite (ATTACH DB)   │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │           Camada de Dados (SQLAlchemy)        │
                    │   - Tabelas: users, products, sales_history   │
                    │   - SQLite (Local) / PostgreSQL (Produção)    │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │            Engenharia de Features             │
                    │   - Médias Móveis (7d/30d) e Variação %       │
                    │   - Sazonalidade Cíclica (Sen/Cos) e Feriados │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │         Núcleo de Machine Learning            │
                    │   - DemandTrainer & DemandPredictor (XGBoost) │
                    │   - FutureForecaster (7/14/30d + XAI)         │
                    │   - DemandComparator & OpportunityRecommender │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │           API REST FastAPI (/api/v1)          │
                    │   - Auth & OTP Email  - Products & Fuzzy Search│
                    │   - Forecast & XAI    - Recommendations       │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │        Frontend Web (HTML5 / CSS3 / JS)       │
                    │   - Design Glassmorphism & Gráficos em Canvas │
                    └───────────────────────────────────────────────┘
```

---

## 📂 Estrutura de Pastas

```text
trendecommerce/
├── config/                          # Configurações globais e parâmetros do projeto
│   └── settings.py
├── data/                            # Banco de dados SQLite local (ignorado no Git)
│   └── trendcommerce_dev.db
├── frontend/                        # Aplicação Web Frontend (HTML5, CSS3 e Vanilla JS)
│   ├── assets/                      # Imagens e logotipos da interface
│   ├── css/
│   │   ├── login.css                # Estilos das telas de autenticação e glassmorphism
│   │   └── style.css                # Estilos do dashboard, cards e gráficos
│   ├── js/
│   │   ├── analise-especifica.js    # Controlador de busca no catálogo, gráfico e XAI
│   │   ├── api.js                   # Cliente HTTP para comunicação com /api/v1
│   │   ├── auth.js                  # Controle de sessão, login, cadastro e recuperação
│   │   ├── effects.js               # Efeitos visuais de fundo
│   │   ├── ia-preditiva.js          # Controlador da visão principal e comparador A vs B
│   │   ├── ranking.js               # Controlador do ranking preditivo de 30 dias
│   │   └── sidebar.js               # Navegação lateral e perfil do usuário
│   ├── analise-especifica.html      # Página de Análise Específica de Produtos
│   ├── cadastro.html                # Página de Criação de Conta
│   ├── codigo-verificacao.html      # Página de Validação de Código OTP
│   ├── ia-preditiva.html            # Página Principal do Dashboard Preditivo
│   ├── index.html                   # Redirecionador de entrada do Frontend
│   ├── login.html                   # Página de Login
│   ├── nova-senha.html              # Página de Redefinição de Senha
│   ├── ranking.html                 # Página de Ranking de Produtos
│   ├── recuperar-senha.html         # Página de Solicitação de Recuperação de Senha
│   └── server.py                    # Servidor HTTP opcional para o frontend (Porta 3000)
├── src/
│   ├── api/                         # Camada REST FastAPI
│   │   ├── routers/
│   │   │   ├── auth_router.py       # Autenticação JWT, cadastro e recuperação via OTP
│   │   │   ├── forecast_router.py   # Previsões XGBoost, ranking, comparador e backtest
│   │   │   ├── opportunity_router.py# Recomendações de oportunidades (Matriz POI)
│   │   │   └── products_router.py   # Catálogo, top vendas 30d e busca por similaridade
│   │   ├── services/
│   │   │   ├── email_service.py     # Disparo de códigos OTP via SMTP
│   │   │   └── supabase_service.py  # Integração opcional com Supabase
│   │   ├── dependencies.py          # Injeção de sessão de BD, JWT e warmup do modelo ML
│   │   └── main.py                  # Inicialização FastAPI, lifespan, CORS e arquivos estáticos
│   ├── database/                    # Camada de Persistência (SQLAlchemy ORM)
│   │   ├── connection.py            # Gerenciamento de Engine e Sessões (SQLite/PostgreSQL)
│   │   ├── models.py                # Modelos ORM: User, Product e SalesHistory
│   │   ├── seed_loader.py           # Sincronização automática do catálogo no startup
│   │   └── setup.py                 # CLI de manutenção do banco (create, drop, seed, sync, status, reset)
│   ├── features/
│   │   └── feature_engineering.py   # Extração de variáveis temporais, cíclicas e médias móveis
│   ├── ml/                          # Núcleo de Inteligência Artificial
│   │   ├── comparator.py            # Backtesting e validação histórica Real vs. Previsto
│   │   ├── evaluation.py            # Cálculo de RMSE, MAE, MAPE e R²
│   │   ├── future_forecaster.py     # Projeções futuras de 7/14/30 dias e motor XAI
│   │   ├── opportunity_recommender.py # Avaliação de score comercial e quadrantes POI
│   │   ├── predictor.py             # Inferência com margem de segurança
│   │   └── trainer.py               # Treinamento do XGBoost Regressor
│   ├── schemas/                     # Contratos Pydantic (Auth, Product, Forecast)
│   └── services/
│       └── vendas_api_client.py     # Cliente de integração com a API de Histórico de Vendas
├── tests/                           # Suíte de testes automatizados (Pytest)
│   ├── test_api.py                  # Testes de integração das rotas REST e busca fuzzy
│   ├── test_comparator.py           # Testes de backtesting
│   ├── test_feature_engineering.py  # Testes de engenharia de variáveis
│   ├── test_ml.py                   # Testes de treinamento, avaliação e predição XGBoost
│   └── test_opportunity_recommender.py # Testes do recomendador de oportunidades
├── iniciar_api_vendas.bat           # Script para iniciar a API externa de Histórico de Vendas (Porta 8001)
├── main.py                          # Ponto de entrada da aplicação principal (Porta 8000)
├── requirements.txt                 # Dependências Python do projeto
├── setup.py                         # Empacotamento e metadados do projeto
├── render.yaml                      # Configuração de deploy para o Render
└── vercel.json                      # Configuração de deploy para a Vercel
```

---

## ⚙️ Instalação e Configuração

### Pré-requisitos
- **Python 3.11** ou superior
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

### 4. Variáveis de Ambiente (Opcional)
Para desenvolvimento local, o sistema funciona imediatamente sem necessidade de configuração extra, utilizando SQLite em `data/trendcommerce_dev.db`. Caso deseje personalizar, crie um arquivo `.env` na raiz:

```env
# Banco de Dados (Padrão local: sqlite:///./data/trendcommerce_dev.db)
DATABASE_URL=sqlite:///./data/trendcommerce_dev.db

# URL ou Caminho da API de Histórico de Vendas
VENDAS_API_URL=http://127.0.0.1:8001

# Segurança e Autenticação JWT
JWT_SECRET_KEY=sua_chave_secreta_super_segura
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Envio de E-mails OTP (Opcional)
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=sua_senha_de_app
```

---

## 🚀 Como Executar

### 1. Iniciando o Sistema Completo

#### Passo 1: Iniciar a API de Histórico de Vendas (Opcional se o arquivo `.db` da API estiver presente)
No Windows, execute:
```powershell
.\iniciar_api_vendas.bat
```
- **Swagger da API de Vendas:** `http://127.0.0.1:8001/docs`
- **Health Check:** `http://127.0.0.1:8001/health`

> **Nota:** Mesmo que o executável da porta `8001` não esteja aberto, o `VendasApiClient` localiza automaticamente o banco `historico_vendas.db` e sincroniza os 500 produtos e 518.500 registros de vendas de forma transparente.

#### Passo 2: Iniciar o Servidor TrendCommerce AI (Porta 8000)
```powershell
python main.py
```
*(Ou `uvicorn src.api.main:app --reload --port 8000`)*

Acesse no navegador:
- 🌐 **Aplicação Web (Frontend Integrado):** **`http://localhost:8000/app/login.html`** (ou **`http://localhost:8000/`**)
- 📖 **Documentação Interativa (Swagger UI):** **`http://localhost:8000/docs`**
- 📑 **Documentação ReDoc:** **`http://localhost:8000/redoc`**

> **Credenciais Padrão de Acesso:**
> - **E-mail:** `admin@trendecommerce.com`
> - **Senha:** `admin123`

---

### 2. Gerenciamento do Banco de Dados (CLI)

O utilitário `src.database.setup` permite gerenciar as tabelas (`users`, `products`, `sales_history`) e a sincronização com a API:

```powershell
# Verificar status e contagem de registros nas tabelas
python -m src.database.setup status

# Recriar o banco do zero e importar os 500 produtos e vendas da API oficial
python -m src.database.setup reset

# Atualizar datas de histórico até o dia atual
python -m src.database.setup sync
```

---

## 📖 Documentação da API (Endpoints)

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| **Autenticação** | | |
| `POST` | `/api/v1/auth/login` | Autenticação de usuário com retorno de token JWT |
| `POST` | `/api/v1/auth/register` | Cadastro de novo usuário |
| `GET` | `/api/v1/auth/me` | Dados do perfil do usuário autenticado |
| `POST` | `/api/v1/auth/forgot-password` | Solicitação de código OTP para recuperação de senha |
| `POST` | `/api/v1/auth/reset-password` | Redefinição de senha com validação de código OTP |
| **Produtos & Catálogo** | | |
| `GET` | `/api/v1/products` | Listagem paginada de produtos com filtros de busca e categoria |
| `POST` | `/api/v1/products` | Cadastro de novo produto no catálogo |
| `GET` | `/api/v1/products/categories` | Lista as categorias de produtos ativas |
| `GET` | `/api/v1/products/top-sales` | Ranking dos produtos mais vendidos nos últimos 30 dias |
| `GET` | `/api/v1/products/autocomplete` | Sugestões de produtos por correspondência exata ou similaridade de caracteres |
| `POST` | `/api/v1/products/discover-live` | Busca de produtos no catálogo oficial (retorna `404` se não cadastrado) |
| `GET` | `/api/v1/products/{id}` | Detalhes de um produto e histórico recente |
| `GET` | `/api/v1/products/{id}/history` | Série temporal de vendas do produto (`days=7..1000`) |
| `POST` | `/api/v1/products/{id}/sales` | Registro de nova venda para um produto |
| `GET` | `/api/v1/products/api-status` | Status de conectividade com a API de Histórico de Vendas |
| `POST` | `/api/v1/products/sync-categories` | Sincronização manual do catálogo e histórico da API oficial |
| **Previsão de Demanda (IA / XGBoost)** | | |
| `POST` | `/api/v1/forecast/predict` | Projeção futura para 7, 14 ou 30 dias com explicabilidade (XAI) |
| `GET` | `/api/v1/forecast/ranking` | Ranking preditivo Top 7 geral e Top 5 por categoria |
| `POST` | `/api/v1/forecast/compare` | Comparativo preditivo lado a lado (`product_id_a` vs. `product_id_b`) |
| `POST` | `/api/v1/forecast/backtest` | Auditoria histórica confrontando Demanda Real vs. Prevista |
| **Recomendações & Saúde** | | |
| `GET` | `/api/v1/recommendations/top-products` | Melhores oportunidades de venda e quadrantes estratégicos (POI) |
| `GET` | `/api/v1/health` | Health check da API e status do banco de dados |
| `GET` | `/api/v1/debug/status` | Contagem detalhada de usuários, produtos e vendas |

---

## 🧪 Qualidade e Testes

A suíte automatizada valida os endpoints da API, autenticação, busca por similaridade de caracteres, engenharia de features, treinamento/inferência XGBoost, backtesting e recomendação de oportunidades:

```powershell
pytest -v
```

Status atual da suíte:
```text
======================= 30 passed in 37.59s =======================
```

---

## ☁️ Deploy

- **Render (Backend + Frontend unificados):** Configurado via [`render.yaml`](render.yaml) executando `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`.
- **Vercel (Frontend Estático):** Configurado via [`vercel.json`](vercel.json) apontando para o diretório `frontend/`.

---

## 📄 Licença

Distribuído sob a licença **MIT**. Consulte o arquivo [`LICENSE`](LICENSE) para mais informações.

---

<div align="center">
Desenvolvido com Python, FastAPI, XGBoost e Inteligência Artificial por <b>TrendCommerce AI Team</b>.
</div>

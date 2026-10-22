# 🚀 TrendCommerce AI

<div align="center">

![TrendCommerce AI Banner](frontend/img/favicon.png)

**Plataforma Fullstack de Inteligência Preditiva de Vendas, Governança de APIs e Análise Estratégica de Mercado para E-commerce**

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.0+-eb6024.svg)](https://xgboost.readthedocs.io/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/Tests-81%20passed%20%7C%20100%25-brightgreen.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Visão Geral](#-visão-geral) •
[Funcionalidades](#-funcionalidades-chave) •
[Arquitetura](#-arquitetura-do-sistema) •
[Instalação](#-instalação-e-configuração) •
[Execução](#-como-executar) •
[Endpoints da API](#-documentação-da-api-endpoints) •
[Testes](#-qualidade-e-testes) •
[Deploy](#-deploy)

</div>

---

## 📌 Visão Geral

O **TrendCommerce AI** é uma solução completa de inteligência comercial para e-commerces e marketplaces (Mercado Livre, Amazon, etc.). A plataforma combina **engenharia de dados multi-canal**, **governança e segurança de requisições externas (API Guardian)**, **engenharia de features estatísticas/macroeconômicas** e **modelagem preditiva com XGBoost**, fornecendo:

- Projeções de demanda futura com **intervalos de confiança** e **recomendações de estoque de segurança**.
- **Explicabilidade de Inteligência Artificial (XAI)** indicando os principais fatores que influenciam as vendas (sazonalidade, histórico recente, competitividade e tendências macro).
- **Matriz Estratégica de Oportunidades (POI)** classificando o catálogo em quadrantes de ação rápida.
- **Painel Analítico Web Interativo** com identidade visual moderna, gráficos de evolução e suporte a exportações.

---

## ⚡ Funcionalidades Chave

### 🧠 1. Motor Preditivo de Machine Learning (XGBoost)
- **Previsões Autoregressivas Flexíveis**: Suporte nativo a horizontes de projeção de **7, 14 e 30 dias**.
- **Intervalos de Confiança Estatísticos**: Faixas superior e inferior projetadas com margem adaptativa de incerteza.
- **Explicabilidade do Modelo (XAI)**: Decomposição das previsões em 4 pilares:
  1. *Média Recente*: Volume histórico recente dos últimos 14 dias.
  2. *Sazonalidade Semanal*: Ponderação dos picos em dias úteis vs. finais de semana.
  3. *Competitividade de Preço*: Comparativo frente à faixa praticada no mercado.
  4. *Tendência de Mercado*: Variações de interesse e volume de buscas.
- **Comparador Preditivo Lado a Lado**: Confronto direto de métricas de giro e receita prevista entre dois produtos.
- **Rankings Preditivos Automatizados**: Identificação do *Top 7 Geral* e *Top 5 por Categoria* para tomadas de decisão rápidas de reposição e compra.

### 🔬 2. Engenharia de Features Robusta (`FeatureEngineer`)
- **Features de Histórico de Vendas**: Médias móveis (7d, 30d), somatórios móveis, taxas de aceleração (`crescimento_vendas`, `crescimento_vendas_7d`) e posicionamento de preço no range histórico.
- **Features Temporais & Cíclicas**: Codificação trigonométrica periódica (`dia_semana_sin/cos`, `mes_sin/cos`), indicadores de fim de semana, início e encerramento de mês.
- **Variáveis Exógenas & Macroeconômicas**: Integração com APIs externas para enriquecimento de dados:
  - Feriados Nacionais (BrasilAPI / Nager.Date) e distância em dias até o próximo feriado.
  - Cotação do Dólar PTAX e Taxa Selic (Banco Central do Brasil - SGS).
  - Indicadores de engajamento do marketplace (volume de dúvidas e avaliações médias).
- **Features de Tendências de Busca**: Extração de médias de interesse, volatilidade e cálculo de inclinação de tendência por regressão linear.

### 🛡️ 3. Governança e Segurança (`API Guardian`)
- **Scanner Preventivo de Credenciais**: Detecção estática em tempo real para evitar vazamento acidental de tokens (AWS, Mercado Livre, JWT, Private Keys).
- **Controle de Políticas & Whitelist**: Filtragem rigorosa de domínios externos autorizados para evitar requisições SSRF ou consumo indevido de cotas.
- **Normalização Multi-Canal**: Padronização unificada de dados heterogêneos originados de diferentes marketplaces.

### 📊 4. Auditoria e Validação (`DemandComparator`)
- **Backtesting Histórico**: Mecanismo automatizado de auditoria que compara as previsões inferidas pelo modelo com os valores reais consumidos.
- **Métricas de Confiabilidade**: Cálculo de `Taxa de Acerto na Faixa` (Hit Rate %), `Acurácia Média`, `RMSE` e `MAE`.
- **Relatórios Formatados**: Tabela detalhada em texto e endpoint REST para auditorias contínuas.

### 💻 5. Frontend Dashboard SPA Moderno
- Interface responsiva com tema Dark/Cyberpunk.
- Telas integradas:
  - **IA Preditiva**: Gráficos temporais de demanda, faixas de incerteza e fatores determinantes.
  - **Análise Específica**: Projeções individuais com recomendações de compra de estoque.
  - **Ranking de Oportunidades**: Visão consolidada de líderes por categoria.
  - **Autenticação Segura**: Suporte a login, cadastro, verificação em duas etapas (2FA OTP) e redefinição de credenciais.

---

## 🏗️ Arquitetura do Sistema

```
                    ┌───────────────────────────────────────────────┐
                    │          Fontes Externas & APIs               │
                    │  (Mercado Livre, Amazon, BCB SGS, BrasilAPI)  │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │           API Guardian & Coletores            │
                    │    - Whitelist Validator   - Scanner de Chaves │
                    │    - Rate Limiter          - Normalizador     │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │               Camada de Dados                 │
                    │    - PostgreSQL / SQLite   - SQLAlchemy ORM   │
                    │    - Seed Automático       - Histórico Vendas │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │         Engenharia de Features                │
                    │    - Médias Móveis (7d/30d) - Codificação Sen/Cos│
                    │    - Macro (Dólar, Selic)   - Feriados Nacionais│
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │         Núcleo de Machine Learning            │
                    │    - DemandTrainer (XGBoost Regressor)        │
                    │    - FutureForecaster (Horizontes 7/14/30d)   │
                    │    - DemandComparator (Backtest & Validação)  │
                    │    - OpportunityRecommender (Matriz POI)      │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │           API REST FastAPI (/api/v1)          │
                    │    - Auth (JWT/2FA)   - Forecast & XAI        │
                    │    - Products & Sync  - Trends & Ranking      │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │          Frontend SPA Dashboard               │
                    │        (HTML5, Tailwind, JavaScript)          │
                    └───────────────────────────────────────────────┘
```

---

## 📂 Estrutura de Pastas

```text
trendecommerce/
├── config/                  # Configurações de ambiente e constantes globais
├── data/                    # Banco SQLite local e seeds iniciais
├── frontend/                # Interface SPA (HTML, CSS, JS, Assets)
│   ├── assets/              # Estilos e fontes
│   ├── js/                  # Controladores client-side (api.js, auth.js, dashboard.js)
│   ├── react/               # Componentes complementares
│   ├── index.html           # Ponto de entrada do SPA
│   └── server.py            # Servidor local leve para desenvolvimento do frontend (Porta 3000)
├── src/
│   ├── api/                 # Camada REST FastAPI
│   │   ├── dependencies.py  # Injeção de dependências (Sessão de BD, Auth, Forecaster)
│   │   ├── main.py          # Configuração da aplicação FastAPI, middlewares e CORS
│   │   ├── router.py        # Agregador de rotas v1
│   │   └── routers/         # Endpoints separados por domínio funcional
│   ├── collectors/          # Módulos de extração de dados e rastreamento em tempo real
│   ├── database/            # Conexão, setup, seeds e modelos de dados (SQLAlchemy)
│   ├── features/            # Feature Engineering para treinamento e inferência
│   │   └── feature_engineering.py
│   ├── guardian/            # Camada de governança, whitelist e segurança de APIs
│   ├── ml/                  # Modelos de Machine Learning e lógicas analíticas
│   │   ├── comparator.py    # Backtesting e auditoria Real vs. Previsto
│   │   ├── evaluation.py    # Métricas de regressão (RMSE, MAE, R²)
│   │   ├── future_forecaster.py # Projeções futuras com explicabilidade
│   │   ├── opportunity_recommender.py # Matriz de oportunidades (POI)
│   │   ├── predictor.py     # Inferência XGBoost com margem de segurança
│   │   └── trainer.py       # Treinamento e validação cruzada
│   ├── normalization/       # Tratamento e higienização de dados
│   ├── schemas/             # Contratos Pydantic de entrada e saída
│   └── services/            # Serviços de integração interna
├── tests/                   # 81 testes automatizados (unitários e de integração)
├── main.py                  # Ponto de entrada alternativo da API (Porta 8000)
├── requirements.txt         # Dependências do projeto
├── render.yaml              # Configuração de deploy no Render
└── vercel.json              # Configuração de deploy no Vercel
```

---

## ⚙️ Instalação e Configuração

### Pré-requisitos
- **Python 3.11** ou superior
- **Git**
- Terminal Bash ou PowerShell

### 1. Clonar o Repositório
```bash
git clone https://github.com/seu-usuario/trendecommerce.git
cd trendecommerce
```

### 2. Criar e Ativar o Ambiente Virtual

- **Linux / macOS:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

- **Windows (PowerShell):**
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```

### 3. Instalar as Dependências
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### 4. Configurar as Variáveis de Ambiente
Copie o arquivo de exemplo e ajuste os parâmetros conforme necessário:
```bash
cp .env.example .env
```

Exemplo básico de `.env`:
```env
# Banco de Dados (deixe vazio ou sqlite:///./data/trendcommerce_dev.db para ambiente local)
DATABASE_URL=sqlite:///./data/trendcommerce_dev.db

# Segurança e Autenticação
JWT_SECRET_KEY=sua_chave_secreta_super_segura_de_producao
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000
```

---

## 🚀 Como Executar

### 1. Executando o Backend (API FastAPI)

Com o ambiente virtual ativo:
```bash
uvicorn src.api.main:app --reload --port 8000
```
*(Ou execute `python main.py`).*

A API estará disponível em:
- **API Base:** `http://localhost:8000`
- **Swagger UI Interativo:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

> **Nota:** No primeiro startup, o banco de dados é gerado automaticamente com dados iniciais de catálogo e o usuário administrador padrão:
> - **Usuário:** `admin@trendecommerce.com`
> - **Senha:** `admin123`

---

### 2. Executando o Frontend

Em outro terminal (com o ambiente virtual ativo):
```bash
python frontend/server.py
```
Acesse a aplicação no navegador em:
👉 **`http://localhost:3000`**

---

## 📖 Documentação da API (Endpoints)

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `POST` | `/api/v1/auth/login` | Autenticação de usuário e emissão de JWT |
| `POST` | `/api/v1/auth/register` | Cadastro de nova conta |
| `GET` | `/api/v1/auth/me` | Dados do usuário autenticado |
| `GET` | `/api/v1/products` | Listagem paginada de produtos do catálogo |
| `POST` | `/api/v1/products/discover-live` | Descoberta e captura de produtos em tempo real |
| `POST` | `/api/v1/forecast/predict` | Projeção preditiva (7, 14 ou 30 dias) com explicabilidade |
| `GET` | `/api/v1/forecast/ranking` | Ranking Top 7 geral e Top 5 por categoria |
| `POST` | `/api/v1/forecast/compare` | Comparativo preditivo direto entre dois produtos |
| `POST` | `/api/v1/forecast/backtest` | Execução de auditoria preditiva (Real vs. Previsto) |
| `GET` | `/api/v1/recommendations/opportunities` | Matriz de oportunidades e quadrantes comerciais |
| `GET` | `/api/v1/trends/search` | Histórico e volume de tendências de busca |
| `GET` | `/api/v1/health` | Verificação de integridade operacional do sistema |

---

## 🧪 Qualidade e Testes

O projeto conta com uma suíte abrangente de **81 testes automatizados**, cobrindo validação de segurança de credenciais, normalizadores de marketplace, feature engineering, algoritmos preditivos e rotas da API.

Para rodar todos os testes:
```bash
pytest
```

Para executar com relatório detalhado de tempo e cobertura:
```bash
pytest -v --durations=10
```

Status atual:
```text
======================= 81 passed in 19.22s =======================
```

---

## ☁️ Deploy

### Render (API / Backend)
O arquivo [`render.yaml`](render.yaml) já vem pronto para orquestração automática:
- **Build Command:** `pip install --upgrade pip setuptools wheel && pip install -r requirements.txt`
- **Start Command:** `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`

### Vercel (Frontend Estático)
O arquivo [`vercel.json`](vercel.json) direciona o deploy estático apontando para a pasta `frontend/`.

---

## 📄 Licença

Este projeto é distribuído sob a licença **MIT**. Consulte o arquivo `LICENSE` para mais detalhes.

---

<div align="center">
Feito com ☕, Python e Inteligência Artificial por <b>TrendCommerce AI Team</b>.
</div>

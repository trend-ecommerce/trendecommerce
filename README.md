# API Guardian — TrendCommerce AI 🛡️

**API Guardian** is an automated local API security, compliance, code auditing, and runtime protection system inside the **TrendCommerce AI** repository.

It enforces strict HTTP request boundaries, blocks unauthorized external endpoints, detects hardcoded secrets/credentials, and validates code syntax and quality prior to execution or commit.

---

## 🏛️ Architecture

API Guardian operates **100% locally** using deterministic Python rules. Validation operations require **0 LLM tokens**.

```text
Application (amazon.py / mercadolivre.py)
                 │
                 ▼
          Runtime Guard (guarded_request)
                 │
                 ▼
          Policy Engine (YAML rules matching)
                 │
         ┌───────┴───────┐
         │               │
    ALLOW (200)      BLOCK (APIGuardianBlockedError)
         │               │
         ▼               ▼
   urllib.request    Reporter (Console/CI Log Output)
 (Network Executed)  (Network NEVER Executed)
```

---

## 🔒 Authorized APIs (7 Endpoints)

API Guardian enforces strict whitelisting for the following 7 authorized endpoints:

### Amazon SP-API
1. **Catalog Items**: `GET https://sellingpartnerapi-na.amazon.com/catalog/2022-04-01/items`
2. **Product Type Definitions**: `GET https://sellingpartnerapi-na.amazon.com/definitions/2020-09-01/productTypes/{type}`

### Mercado Livre
3. **Search**: `GET https://api.mercadolibre.com/sites/MLB/search` *(Required param: `q`)*
4. **Items**: `GET https://api.mercadolibre.com/items/{item_id}`
5. **Categories**: `GET https://api.mercadolibre.com/sites/MLB/categories`
6. **Trends**: `GET https://api.mercadolibre.com/trends/MLB` *(OAuth required)*
7. **Highlights**: `GET https://api.mercadolibre.com/highlights/MLB/category/{category_id}` *(OAuth required)*

> [!CAUTION]
> All other endpoints, unknown domains, wrong HTTP methods, or direct HTTP calls bypassing `guarded_request` are **BLOCKED** by default.

---

## 🚀 Quick Start & Usage

### 1. Using Runtime Guard in Code

Always route HTTP calls through `guarded_request`:

```python
from api_guardian.runtime_guard import guarded_request

response = guarded_request(
    method="GET",
    url="https://api.mercadolibre.com/sites/MLB/search",
    params={"q": "notebook"}
)
```

### 2. Running CLI Code Audit

To scan the repository locally:

```bash
python -m api_guardian.cli .
```

Output when clean (Exit Code `0`):

```text
API GUARDIAN AUDIT
==================

Files scanned: 12
API calls found: 7
Policies loaded: 7

Approved: 7
Warnings: 0
Blocked: 0

STATUS: 🟢 APROVADO
```

### 3. Running Unit Tests

```bash
python -m unittest discover tests
```

---

## 🔑 Secret Protection

API Guardian automatically scans `.py`, `.yaml`, `.yml`, `.json`, and `.env` files for hardcoded secrets (API keys, LWA tokens, AWS keys, Bearer tokens). Secrets are **never exposed** in console or CI output and are masked as `********`.

---

## ⚙️ Adding a New Policy

Policies are stored as YAML files in the `policies/` directory. To add an authorized API endpoint, create a new YAML file:

```yaml
id: new_api_policy
name: New API Service
provider: provider_name
base_urls:
  - https://api.example.com
endpoints:
  - path: /v1/resource/{id}
    methods:
      - GET
authentication:
  required: true
  type: Bearer
required_credentials:
  - API_KEY
security:
  allow_hardcoded_credentials: false
decision:
  unknown_endpoint: BLOCK
  invalid_method: BLOCK
  missing_authentication: BLOCK
  hardcoded_secret: BLOCK
```

---

## 🤖 GitHub Actions Integration

The repository includes `.github/workflows/api-guardian.yml` which automatically executes `python -m api_guardian.cli .` on `push` and `pull_request`. Builds fail (exit code `1`) if blocking security violations exist.

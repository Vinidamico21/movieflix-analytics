# MovieFlix Analytics

Aplicação didática para demonstrar **App Web + Nginx (proxy) + Pipeline CI/CD + Dados (Lake → DW → Mart)**.

## 📦 Componentes

- **API**: Node.js/Express (CRUD de filmes e avaliações).
- **Frontend**: HTML estático simples (pasta `web/`).
- **Nginx**: proxy reverso (serve o frontend em `/` e repassa `/api/*` para a API).
- **Banco**: PostgreSQL (schemas `app`, `dw` e `mart`).
- **ETL**: scripts SQL para montar o DW e Data Marts.
- **CI/CD**: GitHub Actions com build, smoke test e push da imagem do app para o Docker Hub.

---

## 🚀 Como rodar localmente

1. **Pré-requisitos**: Docker Desktop (ou Docker + Compose).
2. Crie o `.env` (se ainda não existir):
   ```bash
   cp .env.example .env
   ```

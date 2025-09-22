# MovieFlix Analytics

Aplicação simples para cadastrar filmes e avaliações, com um pipeline de dados que simula **Data Lake → Data Warehouse → Data Mart** e exibe **insights** no frontend.

## Stack

- **Nginx (80)**: serve o front e faz proxy para as APIs
- **App (Node, 3000)**: CRUD de filmes e avaliações
- **Py (FastAPI, 8000)**: ETL (carrega/trata CSVs) e APIs de insights
- **PostgreSQL**: DW e views do Data Mart

## Estrutura do projeto

- **web/** – frontend simples (`index.html`) que lista/cadastra filmes, avalia e mostra insights.
- **app/** – API Node (porta 3000) para CRUD:
  - `GET/POST/DELETE /api/movies`
  - `GET /api/ratings?movieId=...`
  - `POST /api/ratings`
- **app.py** – FastAPI (porta 8000): ETL + insights + export:
  - ETL: lê `data-lake/raw_v1/*.csv` → carrega `stg.*` → cria `dw.*` → cria views `mart.*`
  - Insights: `/api/insights/*` e métricas em `/api/quality/metrics`
  - Export: CSVs tratados em `data-lake/normalized_v1/`
- **data-lake/**
  - `raw_v1/` — **entrada** (CSV brutos: `movies.csv`, `users.csv`, `ratings.csv`)
  - `normalized_v1/` — **saída** (DW e marts em CSV)
- **nginx/nginx.conf** – proxy:
  - `/` → web
  - `/api` → app:3000
  - `/api/insights`, `/api/quality` → py:8000
- **docker/** – `docker-compose.local.yml` (sobe pg, app, py e nginx) e `Dockerfile.etl`.

## Como subir

Pré-requisitos: Docker e Docker Compose.

```bash
cd docker
docker compose -f docker-compose.local.yml up -d --build

Acessos:

Front: http://localhost

CRUD (via Nginx): http://localhost/api/movies

Insights (direto no Py): http://localhost:8000/api/insights/top10-by-genre

Rodar o ETL

Coloque os CSVs brutos em data-lake/raw_v1/:

movies.csv (id,title,year,genre,imdb_id)

users.csv (id,age_range,country)

ratings.csv (user_id,movie_id,rating,created_at)

Execute:
docker exec -it py python /app/app.py run-etl --phase raw_v1


Endpoints úteis
GET  http://localhost:8000/api/health
GET  http://localhost:8000/api/insights/top10-by-genre
GET  http://localhost:8000/api/insights/avg-by-age
GET  http://localhost:8000/api/insights/by-country
GET  http://localhost:8000/api/quality/metrics
```

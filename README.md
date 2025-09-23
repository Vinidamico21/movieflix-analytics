# MovieFlix Analytics

App simples para cadastrar filmes/avaliações e rodar um mini pipeline **Data Lake → DW → Data Mart**, exibindo **insights** no front.

## Stack (bem direto)

- **Nginx (80)** → serve front e faz proxy das APIs
- **App (Node, 3000)** → CRUD de filmes/ratings
- **Py (FastAPI, 8000)** → ETL (CSV → stg → dw → mart) + endpoints de insights
- **PostgreSQL** → armazena **stg**, **dw** e **mart** (views)

## Pastas (o que cada uma faz)

- **/web** → `index.html` básico: lista/cadastra filmes, envia rating e mostra insights
- **/app** → API Node (Express + pg): `/api/movies`, `/api/ratings`
- **/app.py** (raiz) → FastAPI do ETL e insights; exporta CSVs normalizados
- **/data-lake**
  - `raw_v1/` → CSV de entrada (`movies.csv`, `users.csv`, `ratings.csv`)
  - `normalized_v1/` → saída do ETL (DW + Marts em CSV)
- **/nginx** → `nginx.conf` com rotas: `/` → web, `/api` → app, `/api/insights|/api/quality` → py
- **/docker** → `docker-compose.local.yml` e Dockerfile do ETL

## Fluxo de dados (em 1 linha)

CSV em `data-lake/raw_v1` → **stg.\*** → regras/normalização → **dw.\*** → views **mart.\*** → front consome.

## Subir o ambiente

```bash
cd docker
docker compose -f docker-compose.local.yml up -d --build
```

Acessos:

- Front: **http://localhost/**
- CRUD (via Nginx): **http://localhost/api/movies**
- Swagger do App: **http://localhost/api/docs**

## Rodar o ETL

1. Coloque os CSVs em `data-lake/raw_v1/`
   - `movies.csv` (id,title,year,genre,imdb_id)
   - `users.csv` (id,age_range,country)
   - `ratings.csv`(user_id,movie_id,rating,created_at)
2. Execute:

```bash
docker exec -it py python /app/app.py run-etl --phase raw_v1
```

## Endpoints úteis (FastAPI/insights)

```text
GET  http://localhost:8000/api/health
GET  http://localhost:8000/api/insights/top10-by-genre
GET  http://localhost:8000/api/insights/avg-by-age
GET  http://localhost:8000/api/insights/by-country
GET  http://localhost:8000/api/quality/metrics
```

## O que cada camada faz (ultra-resumo)

- **stg** → recebe CSV “como veio”
- **dw** → dados limpos/normalizados (tipos, faixas válidas, ids padronizados)
- **mart** → views agregadas para leitura rápida (top 10, médias por idade, contagem por país)

## Dicas rápidas

- Suba com o compose de **/docker**
- Se mudar schema ou CSV, rode o ETL de novo
- Exportar CSVs tratados:

```bash
docker exec -it py python /app/app.py export
```

# MovieFlix Analytics

Aplicação simples para cadastrar filmes e avaliações, com um pipeline de dados que simula **Data Lake → Data Warehouse → Data Mart** e exibe **insights** no frontend.

## Stack

- **Nginx (80)**: serve o front e faz proxy para as APIs
- **App (Node, 3000)**: CRUD de filmes e avaliações
- **Py (FastAPI, 8000)**: ETL (carrega/trata CSVs) e APIs de insights
- **PostgreSQL**: DW e views do Data Mart

## Estrutura

movieflix-analytics/
├─ web/ # index.html (front simples)
├─ app/ # Node (CRUD)
├─ docker/ # compose e Dockerfile do ETL
├─ nginx/nginx.conf # proxy
├─ data-lake/
│ ├─ raw_v1/ # CSVs brutos (entrada do ETL)
│ └─ normalized_v1/ # CSVs tratados (saída do ETL)
├─ app.py # FastAPI: ETL + insights + export
└─ requirements.txt

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

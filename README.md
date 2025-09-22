# MovieFlix Analytics

Plataforma simples para cadastro e avaliação de filmes + pipeline de dados (Data Lake → DW → Data Mart) gerando insights.

## Arquitetura

- **Nginx**: proxy reverso (porta 80).
- **App (Node, porta 3000)**: CRUD de filmes/ratings.
- **Py (FastAPI, porta 8000)**: ETL, views de negócio e APIs de insights.
- **PostgreSQL**: Data Warehouse.

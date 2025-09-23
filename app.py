# app.py — MovieFlix ETL/Insights (FastAPI)
import os
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text

# =========================
# Config  • conexões e paths
# =========================
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://app:app123@pg:5432/movieflix"  # URL padrão do Postgres
)
DATA_LAKE_DIR = Path(os.getenv("DATA_LAKE_DIR", "./data-lake")).resolve()          # raiz do data lake
NORMALIZED_DIR = Path(os.getenv("NORMALIZED_DIR", "./data-lake/normalized_v1")).resolve()  # saída CSV normalizada

engine = create_engine(DATABASE_URL, future=True)  # engine SQLAlchemy

app = FastAPI(title="MovieFlix ETL API")  # app FastAPI

# CORS aberto (dev) — restringir em prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# =========================
# SQL  • DDL/DML dos estágios
# =========================
SQL_CREATE_STAGING = """
create schema if not exists stg;
drop table if exists stg.movies;
drop table if exists stg.users;
drop table if exists stg.ratings;
create table stg.movies(id int, title text, year int, genre text, imdb_id text);
create table stg.users(id int, age_range text, country text);
create table stg.ratings(user_id int, movie_id int, rating numeric(3,1), created_at timestamp);

drop table if exists stg.movies_v3;
drop table if exists stg.ratings_v3;
create table stg.movies_v3(movie_id int, title text, release_year int, primary_genre text, imdb text);
create table stg.ratings_v3(uid int, mid int, score numeric(3,1), ts timestamptz);
"""  # staging p/ v1/v2 e compat p/ v3

SQL_CREATE_DW = """
create schema if not exists dw;

-- Derruba views do mart dependentes (evita conflito ao recriar DW)
drop view if exists mart.top10_by_genre cascade;
drop view if exists mart.avg_by_age_range cascade;
drop view if exists mart.ratings_by_country cascade;

-- Dimensões do DW
create table if not exists dw.movies(
  id int primary key, title text, year int, genre text, imdb_id text
);
create table if not exists dw.users(
  id int primary key, age_range text, country text
);

-- Fato de ratings (surrogate key)
drop table if exists dw.ratings;
create table dw.ratings(
  id bigserial primary key,
  user_id int,
  movie_id int,
  rating numeric(3,1),
  created_at timestamptz
);

-- Limpa dados para recarga
truncate dw.movies;
truncate dw.users;
truncate dw.ratings;
"""

SQL_LOAD_DW_FROM_STAGING_V1V2 = """
-- Carrega Movies com normalização do imdb_id
insert into dw.movies(id,title,year,genre,imdb_id)
select id, title, year, genre,
       case when imdb_id ~ '^tt[0-9]+$' then imdb_id
            else 'tt' || regexp_replace(coalesce(imdb_id,''),'[^0-9]','','g') end
from stg.movies;

-- Carrega Users com fallback de faixa etária
insert into dw.users(id,age_range,country)
select id, coalesce(nullif(age_range,''),'UNKNOWN'), country
from stg.users;

-- Carrega Ratings com clamp de nota e ajuste de timezone
insert into dw.ratings(user_id,movie_id,rating,created_at)
select user_id, movie_id,
       case when rating is null then 0.5
            when rating < 0.5 then 0.5
            when rating > 5.0 then 5.0
            else rating end,
       (created_at at time zone 'UTC')
from stg.ratings;
"""

SQL_COMPAT_V3_TO_V1 = """
-- Mapeia colunas v3 -> staging v1
truncate stg.movies; truncate stg.ratings;
insert into stg.movies(id,title,year,genre,imdb_id)
select movie_id, title, release_year, primary_genre, imdb from stg.movies_v3;

insert into stg.ratings(user_id,movie_id,rating,created_at)
select uid, mid, score, ts from stg.ratings_v3;
"""

SQL_CREATE_MARTS = """
create schema if not exists mart;

-- View: Top 10 por gênero
create or replace view mart.top10_by_genre as
with ranked as (
  select
    m.genre,
    m.id as movie_id,
    m.title,
    round(avg(r.rating)::numeric,2) as avg_rating,
    count(*) as n_ratings,
    row_number() over (partition by m.genre
                       order by avg(r.rating) desc, count(*) desc, m.title asc) as rn
  from dw.movies m
  join dw.ratings r on r.movie_id = m.id
  group by m.genre, m.id, m.title
)
select genre, movie_id, title, avg_rating, n_ratings
from ranked
where rn <= 10;

-- View: média por faixa etária
create or replace view mart.avg_by_age_range as
select u.age_range, round(avg(r.rating)::numeric,2) as avg_rating, count(*) as n
from dw.ratings r
join dw.users u on u.id = r.user_id
group by u.age_range
order by avg_rating desc;

-- View: contagem por país
create or replace view mart.ratings_by_country as
select u.country, count(*) as n
from dw.ratings r
join dw.users u on u.id = r.user_id
group by u.country
order by n desc;
"""

# =========================
# Utils  • helpers de IO/CSV/SQL
# =========================
def _write_df(df: pd.DataFrame, table: str, schema: str):
    df.to_sql(table, engine, schema=schema, if_exists="append", index=False, method="multi")  # bulk insert

def _read_csv_file(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)  # lê CSV em DataFrame
    except Exception as e:
        raise HTTPException(400, f"Falha lendo CSV: {path.name} ({e})")

def _csv_path(phase: str, name: str) -> Path:
    p = DATA_LAKE_DIR / phase / f"{name}.csv"  # monta caminho do CSV por fase
    if not p.exists():
        raise HTTPException(400, f"Arquivo não encontrado: {p}")
    return p

def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)  # garante diretório

def export_dw_to_csv():
    """Exporta DW e Marts para CSVs em NORMALIZED_DIR."""
    _ensure_dir(NORMALIZED_DIR)
    marts_dir = NORMALIZED_DIR / "marts"
    _ensure_dir(marts_dir)

    with engine.begin() as conn:
        # Lê tabelas DW
        df_movies  = pd.read_sql("select * from dw.movies order by id", conn)
        df_users   = pd.read_sql("select * from dw.users  order by id", conn)
        df_ratings = pd.read_sql("select * from dw.ratings order by user_id, movie_id", conn)

        # Escreve CSVs DW
        df_movies.to_csv (NORMALIZED_DIR / "dw_movies.csv",  index=False)
        df_users.to_csv  (NORMALIZED_DIR / "dw_users.csv",   index=False)
        df_ratings.to_csv(NORMALIZED_DIR / "dw_ratings.csv", index=False)

        # Lê e exporta Marts
        df_top10 = pd.read_sql(
            "select * from mart.top10_by_genre order by genre, avg_rating desc, n_ratings desc, title", conn
        )
        df_age   = pd.read_sql(
            "select * from mart.avg_by_age_range order by avg_rating desc", conn
        )
        df_ctry  = pd.read_sql(
            "select * from mart.ratings_by_country order by n desc", conn
        )

        df_top10.to_csv(marts_dir / "top10_by_genre.csv", index=False)
        df_age.to_csv  (marts_dir / "avg_by_age_range.csv", index=False)
        df_ctry.to_csv (marts_dir / "ratings_by_country.csv", index=False)

    return {
        "dir": str(NORMALIZED_DIR),  # diretório de saída
        "rows": {
            "dw_movies": len(df_movies),
            "dw_users": len(df_users),
            "dw_ratings": len(df_ratings),
            "mart_top10": len(df_top10),
            "mart_age": len(df_age),
            "mart_country": len(df_ctry),
        },
    }

# =========================
# Endpoints  • API pública
# =========================
@app.get("/api/health")
def health():
    with engine.begin() as conn:
        conn.execute(text("select 1"))  # teste simples de conexão
    return {"ok": True}

@app.post("/api/datalake/ingest")
def ingest_from_datalake(phase: Literal["raw_v1","improved_v2","reformulated_v3"]):
    # (re)cria staging para a fase
    with engine.begin() as conn:
        conn.execute(text(SQL_CREATE_STAGING))

    # resolve caminhos dos CSVs
    movies_p = _csv_path(phase, "movies")
    users_p  = _csv_path(phase, "users")
    ratings_p= _csv_path(phase, "ratings")

    # lê CSVs
    dfm = _read_csv_file(movies_p)
    dfu = _read_csv_file(users_p)
    dfr = _read_csv_file(ratings_p)

    # carrega em staging conforme versão do layout
    if phase in ("raw_v1","improved_v2"):
        with engine.begin() as conn:
            conn.execute(text("truncate stg.movies; truncate stg.users; truncate stg.ratings;"))
        _write_df(dfm, "movies",  "stg")
        _write_df(dfu, "users",   "stg")
        _write_df(dfr, "ratings", "stg")
    else:  # reformulated_v3
        with engine.begin() as conn:
            conn.execute(text("truncate stg.movies_v3; truncate stg.users; truncate stg.ratings_v3;"))
        _write_df(dfm, "movies_v3",  "stg")
        _write_df(dfu, "users",      "stg")
        _write_df(dfr, "ratings_v3", "stg")

    return {"phase": phase, "status": "staged", "rows": {
        "movies": int(len(dfm)), "users": int(len(dfu)), "ratings": int(len(dfr))
    }}

@app.post("/api/datalake/pipeline")
def pipeline_from_datalake(phase: Literal["raw_v1","improved_v2","reformulated_v3"]):
    ingest_from_datalake(phase)  # 1) ingest
    with engine.begin() as conn:
        conn.execute(text(SQL_CREATE_DW))  # 2) prepara DW
        if phase == "reformulated_v3":
            conn.execute(text(SQL_COMPAT_V3_TO_V1))  # 2.1) compat layout v3 -> v1
        conn.execute(text(SQL_LOAD_DW_FROM_STAGING_V1V2))  # 3) carrega DW
        conn.execute(text(SQL_CREATE_MARTS))               # 4) cria views Mart
    exp = export_dw_to_csv()  # 5) exporta CSVs
    return {"phase": phase, "status": "dw_loaded_marts_ready_and_exported", "export": exp}

@app.get("/api/export")
def export_now():
    exp = export_dw_to_csv()  # exporta sem reprocessar
    return {"status": "exported", "export": exp}

@app.get("/api/insights/top10-by-genre")
def insights_top10():
    # consulta direta na view do Mart
    with engine.begin() as conn:
        rows = conn.execute(text("""
            select * from mart.top10_by_genre
            order by genre, avg_rating desc, n_ratings desc, title
        """)).mappings().all()
    return list(rows)

@app.get("/api/insights/avg-by-age")
def insights_avg_age():
    with engine.begin() as conn:
        rows = conn.execute(text("""
            select age_range, avg_rating, n
            from mart.avg_by_age_range
            order by avg_rating desc
        """)).mappings().all()
    return list(rows)

@app.get("/api/insights/by-country")
def insights_by_country():
    with engine.begin() as conn:
        rows = conn.execute(text("""
            select country, n
            from mart.ratings_by_country
            order by n desc
        """)).mappings().all()
    return list(rows)

@app.get("/api/quality/metrics")
def quality_metrics():
    # métricas simples de qualidade de dados
    with engine.begin() as conn:
        q = """
        select 'ratings_out_of_range' as metric, count(*) as value
          from dw.ratings where rating<0.5 or rating>5.0
        union all
        select 'users_age_unknown', count(*) from dw.users where coalesce(age_range,'') in ('','UNKNOWN')
        union all
        select 'movies_year_null',  count(*) from dw.movies where year is null
        """
        rows = conn.execute(text(q)).mappings().all()
    return list(rows)

# =========================
# CLI  • execução via linha de comando
# =========================
def run_etl(phase: str):
    ingest_from_datalake(phase)  # ingest
    with engine.begin() as conn:
        conn.execute(text(SQL_CREATE_DW))
        if phase == "reformulated_v3":
            conn.execute(text(SQL_COMPAT_V3_TO_V1))
        conn.execute(text(SQL_LOAD_DW_FROM_STAGING_V1V2))
        conn.execute(text(SQL_CREATE_MARTS))
    exp = export_dw_to_csv()
    print(f"[ETL] OK: DW e Marts prontos (fase={phase}). Exportados: {exp}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MovieFlix ETL runner")  # parser CLI
    parser.add_argument("cmd", choices=["run-etl", "export"], help="comando")  # comandos suportados
    parser.add_argument("--phase", default="raw_v1", choices=["raw_v1","improved_v2","reformulated_v3"])  # fase do lake
    args = parser.parse_args()

    if args.cmd == "run-etl":
        run_etl(args.phase)  # executa pipeline completo
    elif args.cmd == "export":
        info = export_dw_to_csv()  # apenas exporta CSVs
        print(f"[EXPORT] Arquivos gerados em {info['dir']} :: {info['rows']}")

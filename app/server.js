// ----------------------- Dependências principais -----------------------
// Framework HTTP
import express from 'express';
// Cliente PostgreSQL (Pool de conexões)
import pkg from 'pg';
const { Pool } = pkg;

// ----------------------- Swagger (documentação) ------------------------
// Middleware de UI do Swagger
import swaggerUi from 'swagger-ui-express';
// Leitor do arquivo OpenAPI em YAML
import YAML from 'yamljs';

// Cria a aplicação Express e habilita JSON no corpo das requisições
const app = express();
app.use(express.json());

// ------------------- Configurações via variáveis de ambiente -------------------
// Porta da API (padrão 3000)
const PORT = process.env.APP_PORT || 3000;
// URL de conexão do Postgres (usuário/senha/host/porta/banco)
const DATABASE_URL = process.env.DATABASE_URL || 'postgres://app:app123@pg:5432/movieflix';
// Cria um pool de conexões com o Postgres
const pool = new Pool({ connectionString: DATABASE_URL });

// ---------------------- Documentação OpenAPI/Swagger ----------------------
// Carrega o documento OpenAPI (define endpoints, schemas, etc.)
const openapiDocument = YAML.load('./openapi.yaml');
// Disponibiliza a UI do Swagger em /docs e o JSON da especificação em /openapi.json
app.use('/docs', swaggerUi.serve, swaggerUi.setup(openapiDocument));
app.get('/openapi.json', (_, res) => res.json(openapiDocument));

// ---------------------- Bootstrap (migrations mínimas) ----------------------
// Cria tabelas básicas do app caso ainda não existam
async function bootstrap() {
  await pool.query(`
    create table if not exists app_movies (
      id serial primary key,
      title text not null,
      year int,
      genre text
    );
  `);
  await pool.query(`
    create table if not exists app_ratings (
      id serial primary key,
      movie_id int references app_movies(id) on delete cascade,
      rating numeric(3,1) check (rating >= 0 and rating <= 10),
      created_at timestamp default now()
    );
  `);
}
// Executa o bootstrap e loga erros se ocorrerem
bootstrap().catch(console.error);

// ----------------------------- Saúde da API -----------------------------
// Endpoint simples para verificar se a API está de pé
app.get('/health', (_, res) => res.status(200).json({status:'ok'}));

// ============================== Movies CRUD ==============================

// Lista todos os filmes (mais recentes primeiro)
app.get('/movies', async (_, res) => {
  const { rows } = await pool.query('select * from app_movies order by id desc');
  res.json(rows);
});

// Cria um novo filme (valida se "title" foi enviado)
app.post('/movies', async (req, res) => {
  const { title, year, genre } = req.body || {};
  if (!title) return res.status(400).json({error:'title is required'});
  const q = 'insert into app_movies(title,year,genre) values($1,$2,$3) returning *';
  const { rows } = await pool.query(q, [title, year, genre]);
  res.status(201).json(rows[0]);
});

// Atualiza parcialmente um filme pelo id (mantém valores antigos com COALESCE)
app.put('/movies/:id', async (req, res) => {
  const { id } = req.params;
  const { title, year, genre } = req.body || {};
  const q = 'update app_movies set title=coalesce($1,title), year=coalesce($2,year), genre=coalesce($3,genre) where id=$4 returning *';
  const { rows } = await pool.query(q, [title, year, genre, id]);
  if (rows.length === 0) return res.status(404).json({error:'movie not found'});
  res.json(rows[0]);
});

// Remove um filme pelo id (204 = sem conteúdo se deu certo)
app.delete('/movies/:id', async (req, res) => {
  const { id } = req.params;
  const r = await pool.query('delete from app_movies where id=$1', [id]);
  if (r.rowCount === 0) return res.status(404).json({error:'movie not found'});
  res.status(204).send();
});

// ============================== Ratings ==============================

// Cria uma avaliação para um filme (checa existência do filme e nota obrigatória)
app.post('/ratings', async (req, res) => {
  const { movie_id, rating } = req.body || {};
  if (!movie_id || rating==null) return res.status(400).json({error:'movie_id and rating are required'});
  const { rows: exists } = await pool.query('select 1 from app_movies where id=$1',[movie_id]);
  if (exists.length===0) return res.status(404).json({error:'movie not found'});
  const { rows } = await pool.query('insert into app_ratings(movie_id, rating) values($1,$2) returning *',[movie_id, rating]);
  res.status(201).json(rows[0]);
});

// Lista avaliações (todas ou filtradas por movieId via query string)
app.get('/ratings', async (req, res) => {
  const { movieId } = req.query;
  const q = movieId ? 'select * from app_ratings where movie_id=$1 order by id desc' : 'select * from app_ratings order by id desc';
  const params = movieId ? [movieId] : [];
  const { rows } = await pool.query(q, params);
  res.json(rows);
});

// ----------------------------- Server listen -----------------------------
// Sobe o servidor HTTP e loga a porta utilizada
app.listen(PORT, () => console.log(`API running on :${PORT}`));

// ============================ Insights (Mart) ============================
// Observação: estes endpoints leem VIEWS no schema "mart" (criados pela pipeline/ETL).
// Certifique-se de rodar o ETL antes para que as views existam.

// Top 10 por gênero (usa mart.top10_by_genre)
app.get('/api/insights/top10', async (req,res)=>{
  const { rows } = await pool.query('select * from mart.top10_by_genre');
  res.json(rows);
});

// Média de rating por faixa etária (usa mart.avg_rating_by_age)
app.get('/api/insights/avg-by-age', async (req,res)=>{
  const { rows } = await pool.query('select * from mart.avg_rating_by_age');
  res.json(rows);
});

// Contagem de ratings por país (usa mart.ratings_by_country)
app.get('/api/insights/by-country', async (req,res)=>{
  const { rows } = await pool.query('select * from mart.ratings_by_country');
  res.json(rows);
});

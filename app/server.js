import express from 'express';
import pkg from 'pg';
const { Pool } = pkg;

// 🔹 NOVO: Swagger UI + leitura do YAML
import swaggerUi from 'swagger-ui-express';
import YAML from 'yamljs';

const app = express();
app.use(express.json());

const PORT = process.env.APP_PORT || 3000;
const DATABASE_URL = process.env.DATABASE_URL || 'postgres://app:app123@pg:5432/movieflix';
const pool = new Pool({ connectionString: DATABASE_URL });

// 🔹 NOVO: carrega o openapi.yaml
const openapiDocument = YAML.load('./openapi.yaml');

// 🔹 NOVO: rotas do swagger (atenção: vamos acessar via Nginx usando /api)
app.use('/docs', swaggerUi.serve, swaggerUi.setup(openapiDocument));
app.get('/openapi.json', (_, res) => res.json(openapiDocument));

// bootstrap tables if not exist
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
bootstrap().catch(console.error);

app.get('/health', (_, res) => res.status(200).json({status:'ok'}));

// Movies CRUD
app.get('/movies', async (_, res) => {
  const { rows } = await pool.query('select * from app_movies order by id desc');
  res.json(rows);
});

app.post('/movies', async (req, res) => {
  const { title, year, genre } = req.body || {};
  if (!title) return res.status(400).json({error:'title is required'});
  const q = 'insert into app_movies(title,year,genre) values($1,$2,$3) returning *';
  const { rows } = await pool.query(q, [title, year, genre]);
  res.status(201).json(rows[0]);
});

app.put('/movies/:id', async (req, res) => {
  const { id } = req.params;
  const { title, year, genre } = req.body || {};
  const q = 'update app_movies set title=coalesce($1,title), year=coalesce($2,year), genre=coalesce($3,genre) where id=$4 returning *';
  const { rows } = await pool.query(q, [title, year, genre, id]);
  if (rows.length === 0) return res.status(404).json({error:'movie not found'});
  res.json(rows[0]);
});

app.delete('/movies/:id', async (req, res) => {
  const { id } = req.params;
  const r = await pool.query('delete from app_movies where id=$1', [id]);
  if (r.rowCount === 0) return res.status(404).json({error:'movie not found'});
  res.status(204).send();
});

// Ratings
app.post('/ratings', async (req, res) => {
  const { movie_id, rating } = req.body || {};
  if (!movie_id || rating==null) return res.status(400).json({error:'movie_id and rating are required'});
  const { rows: exists } = await pool.query('select 1 from app_movies where id=$1',[movie_id]);
  if (exists.length===0) return res.status(404).json({error:'movie not found'});
  const { rows } = await pool.query('insert into app_ratings(movie_id, rating) values($1,$2) returning *',[movie_id, rating]);
  res.status(201).json(rows[0]);
});

app.get('/ratings', async (req, res) => {
  const { movieId } = req.query;
  const q = movieId ? 'select * from app_ratings where movie_id=$1 order by id desc' : 'select * from app_ratings order by id desc';
  const params = movieId ? [movieId] : [];
  const { rows } = await pool.query(q, params);
  res.json(rows);
});

app.listen(PORT, () => console.log(`API running on :${PORT}`));

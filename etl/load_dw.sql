-- Cria schema DW e importa CSV do Data Lake
create schema if not exists dw;

create table if not exists dw.movies(
  id int primary key,
  title text,
  year int,
  genre text,
  imdb_id text
);

create table if not exists dw.users(
  id int primary key,
  age_range text,
  country text
);

create table if not exists dw.ratings(
  user_id int,
  movie_id int,
  rating numeric(3,1),
  created_at timestamp
);

truncate dw.movies; truncate dw.users; truncate dw.ratings;

copy dw.movies(id,title,year,genre,imdb_id) from '/data-lake/movies.csv' with (format csv, header true);
copy dw.users(id,age_range,country) from '/data-lake/users.csv' with (format csv, header true);
copy dw.ratings(user_id,movie_id,rating,created_at) from '/data-lake/ratings.csv' with (format csv, header true);

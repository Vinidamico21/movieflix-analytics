create schema if not exists mart;

create or replace view mart.top10_by_genre as
select genre, title, avg(r.rating) as avg_rating, count(*) as n_ratings
from dw.movies m
join dw.ratings r on r.movie_id = m.id
group by genre, title
order by genre, avg_rating desc
limit 10;

create or replace view mart.avg_rating_by_age as
select u.age_range, avg(r.rating) as avg_rating, count(*) as n_ratings
from dw.users u
join dw.ratings r on r.user_id = u.id
group by u.age_range
order by avg_rating desc;

create or replace view mart.ratings_by_country as
select u.country, count(*) as n_ratings
from dw.users u
join dw.ratings r on r.user_id = u.id
group by u.country
order by n_ratings desc;

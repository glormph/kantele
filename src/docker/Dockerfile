FROM node:18 AS build_frontend

# Compile node stuff
COPY frontend /frontend
RUN cd /frontend/analysis && npm run build
RUN cd /frontend/dashboard && npm run build
RUN cd /frontend/datasets && npm run build
RUN cd /frontend/file-inflow && npm run build
RUN cd /frontend/home && npm run build


# Django app
FROM python:3.10.4 AS django
RUN apt-get update && apt-get install -y libpq-dev python3-psycopg2
COPY backend /kantele
WORKDIR /kantele
RUN pip install -r requirements.txt
CMD uwsgi --socket :8009 --processes 3 --module kantele.wsgi

FROM django AS django_static
ARG SECRET_KEY=abcd1234
RUN python manage.py collectstatic


# Nginx to serve static stuff, uploads etc
# Needs static things in here, for stage only put the static file
# in case developer has not built all NPM things
FROM nginx:1.21 AS nginx_stage
COPY --from=build_frontend /static /static
COPY --from=django_static /kantele/static /static

# For prod also copy in the relevant config files
FROM nginx_stage AS nginx_prod
COPY docker/nginx_prod.conf /etc/nginx/nginx.conf
COPY docker/uwsgi_params /etc/nginx/uwsgi_params
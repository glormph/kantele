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
COPY docker/requirements.txt /
RUN pip install -r requirements.txt
WORKDIR /kantele
CMD uwsgi --socket :8009 --processes 3 --module kantele.wsgi


# Nginx to serve static stuff, uploads etc
# Needs static things in here
FROM nginx:1.21 AS nginx
COPY --from=build_frontend /static /static

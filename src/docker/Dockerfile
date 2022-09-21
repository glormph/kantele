FROM node:18 AS build_frontend

# Compile node stuff
COPY frontend /frontend
RUN cd /frontend/analysis && npm install && npm run build
RUN cd /frontend/dashboard && npm install && npm run build
RUN cd /frontend/datasets && npm install && npm run build
#RUN cd /frontend/file-inflow && npm install && npm run build
RUN cd /frontend/home && npm install && npm run build


# Django app
FROM python:3.10.4 AS django
ARG USER_ID
ARG GROUP_ID
RUN addgroup --system --gid $GROUP_ID kantele
RUN adduser --system --uid $USER_ID --gid $GROUP_ID kantele
RUN apt-get update && apt-get install -y libpq-dev python3-psycopg2 zip
COPY backend/requirements.txt /
RUN pip install -r requirements.txt
RUN mkdir /assets
RUN chdir /assets && wget https://files.pythonhosted.org/packages/ca/91/6d9b8ccacd0412c08820f72cebaa4f0c0441b5cda699c90f618b6f8a1b42/requests-2.28.1-py3-none-any.whl
RUN chdir /assets && wget https://files.pythonhosted.org/packages/6a/34/cd29f4dd8a23ce45f2b8ce9631ff2d4205fb74eddb412a3dc4fd1e4aa800/certifi-2022.9.14-py3-none-any.whl
RUN chdir /assets && wget https://files.pythonhosted.org/packages/60/ef/7681134338fc097acef8d9b2f8abe0458e4d87559c689a8c306d0957ece5/requests_toolbelt-0.9.1-py2.py3-none-any.whl
RUN chdir /assets && wget https://files.pythonhosted.org/packages/fc/34/3030de6f1370931b9dbb4dad48f6ab1015ab1d32447850b9fc94e60097be/idna-3.4-py3-none-any.whl 
RUN chdir /assets && wget https://files.pythonhosted.org/packages/db/51/a507c856293ab05cdc1db77ff4bc1268ddd39f29e7dc4919aa497f0adbec/charset_normalizer-2.1.1-py3-none-any.whl
RUN chdir /assets && wget https://files.pythonhosted.org/packages/6f/de/5be2e3eed8426f871b170663333a0f627fc2924cc386cd41be065e7ea870/urllib3-1.26.12-py2.py3-none-any.whl
COPY docker/setup.bat /assets/
RUN cd /assets && zip producer.zip *.whl setup.bat && chown kantele:kantele producer.zip
USER kantele
COPY --chown=kantele backend /kantele
WORKDIR /kantele
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
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/uwsgi_params /etc/nginx/uwsgi_params

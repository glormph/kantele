#!/bin/bash

# exit as soon as possible
set -eu

# Updates code/containers on entire system
# You will have to stop analyses and other long running tasks by yourself

if [[ ! $(git rev-parse --show-prefix) = '' ]]
then
    echo You are not in the git repo base folder, exiting
    exit 1
fi

basepath="$(pwd)"
rm -fr ./static/
mkdir static
docker compose run web python manage.py collectstatic
cd "${basepath}/src/frontend/analysis" && npm install && npm run build
cd "${basepath}/src/frontend/dashboard" && npm install && npm run build
cd "${basepath}/src/frontend/datasets" && npm install && npm run build
cd "${basepath}/src/frontend/file-inflow" && npm install && npm run build
cd "${basepath}/src/frontend/home" && npm install && npm run build
cd "${basepath}/src/frontend/staffpage" && npm install && npm run build


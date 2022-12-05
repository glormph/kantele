set -eo pipefail


if [[ -z "$1" ]]
then
    TESTCMD="python manage.py test"
    echo will run empty $TESTCMD
else
    TESTCMD="python manage.py test $1"
    echo will run $TESTCMD
fi

# remove old test results if needed (locally)
echo Cleaning up
git clean -xf data/fakestorage
git checkout -- data/fakestorage

# Clean old containers
docker compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml down

# Lint seems to operate on the local dir
echo Running linting
docker compose --env-file src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml run web pylint -E --disable E1101,E0307 --ignore-paths '.*\/migrations\/[0-9]+.*.py' \
   analysis \
   datasets \
   dashboard \
   home \
   jobs \
   kantele \
   rawstatus \
   || (echo Linting failed && exit 2)
echo Linting OK

echo Prebuilding DB and MQ containers
# Get DB container ready so web doesnt try to connect before it has init'ed
docker compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml up --detach db mq
echo Created db container and started it
sleep 5

echo Running tests
export GROUP_ID=$(id -g)
export USER_ID=$(id -u)
# Run tests
docker compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml run --use-aliases web $TESTCMD || (docker-compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml logs storage_mvfiles storage_downloads && exit 1)


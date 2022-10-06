set -euo pipefail

# remove old test results if needed
echo Cleaning up
git clean -xf data/test
git checkout -- data/test

# Clean old containers
docker compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml down

echo Prebuilding DB and MQ containers
# Get DB container ready so web doesnt try to connect before it has init'ed
docker compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml up --detach db mq
echo Created db container and started it
sleep 5

echo Running tests
export GROUP_ID=$(id -g)
export USER_ID=$(id -u)
# Run tests
docker compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml run --use-aliases web python manage.py test kantele || (docker-compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml logs storage_mvfiles storage_downloads && exit 1)

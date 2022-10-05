# remove old test results if needed

docker-compose --version
echo Cleaning up
git clean -xf data/test
git checkout -- data/test

# Clean old containers
docker-compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml down

echo Prebuilding DB and MQ containers
# Get DB container ready so web doesnt try to connect before it has init'ed
docker-compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml up --no-start db mq
docker-compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml up db
sleep 5 && docker-compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml stop db

echo Running tests
# Run tests
docker-compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml run --use-aliases web python manage.py test kantele

# remove old test results if needed

git clean -xf data/test
git checkout -- data/test

# Clean old containers
docker-compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml down

# Get DB container ready so web doesnt try to connect before it has init'ed
docker-compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml create db mq
docker-compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml start db
sleep 5 && docker-compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml stop db mq

# Run tests
docker-compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml run --use-aliases web python manage.py test kantele

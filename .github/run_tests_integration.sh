DOCKERCMD="docker compose --env-file  src/docker/.compose.testing.env -f src/docker/docker-compose-testing.yml"
export GROUP_ID=$(id -g)
export USER_ID=$(id -u)

echo Prebuilding DB and MQ containers
# Get DB container ready so web doesnt try to connect before it has init'ed
$DOCKERCMD up --detach db mq
echo Created db container and started it
sleep 5
echo Running tests
# Run tests

TESTCMD="python manage.py test"
$DOCKERCMD run --use-aliases web $TESTCMD --tag slow --exclude-tag mstulos || ($DOCKERCMD logs web storage_mvfiles storage_downloads tulos_ingester && exit 1)

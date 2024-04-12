# Kantele

## Development, before starting
Prerequisites:

- docker
- npm 18

First you build the containers for running the Django backend with postgres and nginx:
```
# Create an .env file:
cp .env.example .env

# Edit the new .env file!

# Build containers, with static files and database skeleton
bash src/docker/init_develop.sh

# Now you can run and go to http://${your-machine-url}/
# The admin login / password is test / test
docker compose up
```




## Development:

The backend Django code is mounted in the running web container while developing.
If you change the code, restart with:
```
docker compose restart web
```

In production, the frontend JS is built and stored inside the nginx container, but in development
you do the frontend building yourself, so you can quickly rebuild a frontend app when changing it.
To change a single app (datasets, home, analysis, etc), go to the folder and build:
```
cd src/frontend/datasets
npm run build

# You can run continuous frontend rebuilding with live reload like this:
npm run dev

# For refreshing ALL frontend apps at the same time
# Also does Django static file collection
bash src/docker/create_static.sh
```

If you want to rebuild the containers:
```
# Set user and group id for the file ownership to the same ids the user has.
# I am not sure how to do this on windows or if it is necessary
export USER_ID=$(id -u)
export GROUP_ID=$(id -g)
docker compose build
```


## Testing

To run the Django tests (python unittests):
```
# Run all the tests:
bash run_tests.sh

# Or run a specific test
bash run_tests.sh analysis.tests.TestGetAnalysis.test_ok
```

Tests run in docker compose containers and are also running on github actions inside the same containers.


## Repo
There is a `data` directory for persistent data between container rebuilds in
development and testing. The directory contains:
- `analysisfiles` - analysis results go here, currently only work in prod
- `db` - database persistence
- `test` - contain filesystem fixtures for tests
- `teststorage` - empty, gitignored, used as a fresh fixture workdir in testing
- `storage` - used in develop/stage as a storage unit
- `newstorage` - for simulating a second storage unit
- `uploads` - where uploads go in the nginx container

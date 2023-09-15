# Deploying Kantele

## Development, before starting
Prerequisites:

- docker
- npm

First you build the containers for running the Django backend with postgres and nginx:

```
# Set user and group id for the file ownership to the same ids the user has.
# I am not sure how to do this on windows or if it is necessary
export USER_ID=$(id -u)
export GROUP_ID=$(id -g)

# Create an .env file:
cp .env.example .env

# Edit the new .env file!

# Now build the containers
docker-compose build
```

## FIXME collectattic is run in build, but overwritten by the frontend builds!!!!!!
## Right now you have to go in and copy the files, NOT GOOD

In production we deliver the frontend, but in development you do the frontend building yourself.
An advantage of this is that you can quickly rebuild a frontend app and use live-reload while
working:

```
bash src/docker/build_frontends.sh
```

## Development:

Put your environment variables in `src/docker/stage.env`. This needs fixing.

When new backend code needs to be loaded, you can restart the web container using `docker-compose restart web`. If you need the other containers to restart for more testing that is of course possible.

Frontend coding can be done while this is running, in e.g. `src/frontend/analysis`:

```
npm run dev
```

This will automatically regenerate the compiled frontend files.


# Deploying Kantele

## Development setup
- Run `docker-compose build`
- If you need freshly built frontend files, run the following:

```
  docker-compose -f src/docker/docker-compose-build.yml build
  rm -rf src/static
  docker-compose -f src/docker/docker-compose-build.yml run -v $(pwd)/src:/build_out nginx cp -r /static /build_out
```

- Put environment variables in `src/docker/stage.env`
- Run `docker-compose up`


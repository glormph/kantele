---

# Datasets frontend

This is the source for the corefac frontend Svelte app, which creates and views core facility info


## Get started

Install the dependencies...

```bash
cd frontend/corefac
npm install
```

## Deploying on develop box

Start [Rollup](https://rollupjs.org) to build the JS app:

```bash
npm run dev 
```

Start your Django webserver which will serve the application. Edit a component file in `src`, save it, and reload the page to see your changes.


## Deploying on production

Start [Rollup](https://rollupjs.org) to build the JS app:

```bash
npm run build
```

This does more or less the same as the dev deploy except it does not autobuild on edits. Mainly production is deployed
via git so you'd typically then do something like:

```bash
git add ../../corefac/static/corefac/
git commit -m 'Deploy corefac frontend version x.y'
git push
```

And then use your deploy procedure.

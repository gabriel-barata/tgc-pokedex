# Home-server deployment

The app runs from `ghcr.io/gabriel-barata/tcg-pokedex`, which CI publishes on every merge to
`main` as `:latest` and `:<full commit sha>`. [What's Up Docker](https://getwud.app) (WUD)
polls GHCR every 5 minutes. When `:latest` gets a new digest, it pulls the image, recreates
the app container and sends an ntfy notification.

| Path | What it is |
| --- | --- |
| `compose.yml`, `.env.example` | The app stack: `app` and `postgres` with a named volume. |
| `wud/compose.yml`, `wud/.env.example` | WUD, a server-level stack that can watch other homelab containers too. |

Secrets live only in the `.env` files on the server, never in the repository.

## How it behaves

- **Opt-in auto-update.** WUD's `docker.autoupdate` trigger only touches containers labelled
  `wud.trigger.docker.autoupdate.enabled=true`. Other homelab containers are watched but never
  updated. Postgres is not watched, because a major upgrade needs a dump and restore.
- **Health-gated, with automatic rollback.** WUD keeps the old container until the new one
  reports `healthy` through the image's `HEALTHCHECK`. If it reports `unhealthy`, crashes, or
  is not healthy within 5 minutes, WUD restores the old container.
- **Notifications** go to one ntfy topic: `Deployed TCG Pokédex`, `Deploy FAILED for TCG
  Pokédex`, or `Rollback of tcg-pokedex-app-1`.
- **No public URL.** The app sits behind Nginx Proxy Manager (NPM) on the LAN.

## First install

Needs Docker with the compose plugin, and NPM already running.

1. Find NPM's Docker network. It is usually `<npm project>_default`, and
   `docker network ls` lists it.
2. Create the folders and copy the files from this directory:

   ```sh
   sudo mkdir -p /opt/stacks/tcg-pokedex /opt/stacks/wud
   # copy compose.yml and .env.example to /opt/stacks/tcg-pokedex/
   # copy wud/compose.yml and wud/.env.example to /opt/stacks/wud/
   cd /opt/stacks/tcg-pokedex && cp .env.example .env && chmod 600 .env
   cd /opt/stacks/wud && cp .env.example .env && chmod 600 .env
   ```

3. Fill in `/opt/stacks/tcg-pokedex/.env`:
   - `POSTGRES_PASSWORD`: `openssl rand -hex 32`. Use hex: it goes into a URL as is.
   - `PROXY_NETWORK`: the NPM network from step 1.
4. Start the app and check it:

   ```sh
   cd /opt/stacks/tcg-pokedex && docker compose up -d --wait
   ```

5. In NPM, add a proxy host for your LAN hostname. Forward it to `tcg-pokedex`, port `8000`,
   scheme `http`. `tcg-pokedex` is the app's alias on the proxy network.
6. Install the ntfy app on your phone and subscribe to a long random topic, e.g.
   `tcg-pokedex-$(openssl rand -hex 12)`. Anyone who knows a topic name on ntfy.sh can read it.
7. Fill in `/opt/stacks/wud/.env`:
   - `NTFY_TOPIC`: the topic from step 6. Set `NTFY_URL` too if you self-host ntfy.
   - `PROXY_NETWORK`: the same NPM network.
   - `WUD_ADMIN_PASSWORD`: WUD 9 refuses to start without an admin account.
8. Start WUD:

   ```sh
   cd /opt/stacks/wud && docker compose up -d --wait
   ```

   To reach the WUD UI, add an NPM proxy host forwarding to `wud`, port `3000`.
9. Clean up old images weekly, since WUD's own pruning is off (see Known quirks). Add this
   line to root's crontab:

   ```cron
   0 4 * * 0 docker image prune -f
   ```

The GHCR package is public, so WUD needs no registry credentials. If it ever becomes private,
create a classic PAT with only `read:packages`. Add `WUD_REGISTRY_GHCR_PRIVATE_USERNAME` and
`WUD_REGISTRY_GHCR_PRIVATE_TOKEN` to WUD's environment, and run `docker login ghcr.io` on the
server so `docker compose pull` keeps working.

## Which version is running

```sh
docker inspect -f '{{ index .Config.Labels "org.opencontainers.image.revision" }}' tcg-pokedex-app-1
```

## Manual rollback, and pausing auto-updates

Pin a commit sha. WUD only watches the pinned tag's digest, which never changes, so pinning
also pauses auto-updates for the app.

```sh
cd /opt/stacks/tcg-pokedex
# in .env: TCG_POKEDEX_IMAGE_TAG=<full sha of the commit to run>
docker compose up -d --wait
```

The tags are listed at <https://github.com/gabriel-barata/tgc-pokedex/pkgs/container/tcg-pokedex>,
and every merge commit on `main` has one. To pause without rolling back, pin the sha that is
running now.

To resume auto-updates:

```sh
# in .env: TCG_POKEDEX_IMAGE_TAG=latest
docker compose pull app && docker compose up -d --wait
```

To pause auto-updates for every homelab container, stop WUD: `docker compose stop` in
`/opt/stacks/wud`.

## After an automatic rollback

The old container is running again, but the local `:latest` tag now points at the bad image.
Any later `docker compose up -d`, or a host reboot followed by one, would deploy the bad
image. Right away, pin the last good sha as in "Manual rollback". Then fix forward on `main`
and resume auto-updates.

## Migration rule: expand/contract only

A rollback, manual or automatic, swaps the image but cannot undo a schema change. The app runs
its migrations on start, so by the time a rollback happens the new schema is already in place.
Every migration must therefore keep the previous release working:

- **Expand:** add tables, nullable columns, or columns with defaults. Never rename or drop in
  the same release that stops using them.
- **Contract:** drop or rename only in a later release, once no deployed version reads the old
  shape.

## Known quirks (WUD 9.4.1)

- The first `docker compose up -d` after an auto-update recreates the app once from the same
  image. WUD copies the old `com.docker.compose.image` label, so compose sees a difference.
  This is harmless.
- WUD's Docker Compose trigger ignores digest updates on an unpinned `:latest`, so the plain
  Docker trigger is used. It keeps the compose labels, and `compose.yml` never changes on the
  server.
- WUD's `PRUNE` option can report a successful update as failed when removing the previous
  image errors. That is why it is off and the weekly cron prunes instead.
- Notifiers never send the `success`/`failure` events, so the app's `post` and `failure` hooks
  call the manual-only `ntfy.deploy` trigger. Every ntfy trigger also sends rollback reports,
  which is why there is only one.

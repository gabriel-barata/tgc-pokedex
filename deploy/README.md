# Home-server deployment

The app runs on `homelab01` (192.168.1.201) from `ghcr.io/gabriel-barata/tcg-pokedex`, which
CI publishes on every merge to `main` as `:latest` and `:<full commit sha>`.
[What's Up Docker](https://getwud.app) (WUD) polls GHCR every 5 minutes. When `:latest` gets a
new digest, it pulls the image and recreates the app container.

| Repo path | Server path | What it is |
| --- | --- | --- |
| `compose.yml`, `.env.example` | `/srv/docker/tcg-pokedex/` | The app with its `images` volume, and Postgres 17 with its own. |
| `wud/compose.yml`, `wud/.env.example` | `/srv/docker/wud/` | WUD, shared by the whole homelab. |

Secrets live only in the `.env` files on the server (`chmod 600`), never in the repository.

## How it fits the homelab

- Every stack joins the external `servicos_lan` network, where Nginx Proxy Manager (`npm`)
  reaches it by container name. On that network the app's alias is `tcg-pokedex` (port 8000)
  and WUD's is `wud` (port 3000).
- Pi-hole resolves `*.mistoquente.de` to 192.168.1.201 through
  `misc.dnsmasq_lines = ["address=/mistoquente.de/192.168.1.201"]`, and NPM routes each name:

  | URL | NPM forwards to |
  | --- | --- |
  | http://pokedex.mistoquente.de | `tcg-pokedex:8000` |
  | http://wud.mistoquente.de | `wud:3000` (login: `WUD_ADMIN_*` in `/srv/docker/wud/.env`) |
  | http://npm.mistoquente.de | `npm:81`, the NPM admin UI |

- Devices only resolve these names if they use Pi-hole for DNS. If the router also advertises
  itself as an IPv6 DNS server, devices ask it first and the names fail. Either point the
  router's IPv6 DNS at Pi-hole, or turn that advertisement off.

## How updates behave

- **Opt-in.** WUD's `docker.autoupdate` trigger only updates containers labelled
  `wud.trigger.docker.autoupdate.enabled=true`, which today means just the app. Every other
  container is watched and appears in the WUD UI, but is never updated. Postgres is not
  watched at all, because a major upgrade needs a dump and restore.
- **Health-gated, with automatic rollback.** WUD keeps the old container until the new one
  reports `healthy` through the image's `HEALTHCHECK`. If it reports `unhealthy`, crashes, or
  is not healthy within 5 minutes, WUD restores the old container.
- **Where to look:** the WUD UI, or `docker logs wud` (look for `recreated` or `rolled back`).
- **Disk.** Every deploy leaves the previous image behind. A weekly cron in `machine01`'s
  crontab prunes them: `0 4 * * 0 /usr/bin/docker image prune -f`. WUD's own `PRUNE` is off,
  because a failed image removal makes WUD report a good deploy as failed.

## First install (already done; repeat on a new server)

```sh
mkdir /srv/docker/tcg-pokedex /srv/docker/wud
# copy compose.yml to /srv/docker/tcg-pokedex/ and wud/compose.yml to /srv/docker/wud/
printf 'POSTGRES_PASSWORD=%s\nTCG_POKEDEX_IMAGE_TAG=latest\n' "$(openssl rand -hex 32)" > /srv/docker/tcg-pokedex/.env
printf 'TZ=America/Sao_Paulo\nWUD_ADMIN_USER=admin\nWUD_ADMIN_PASSWORD=%s\n' "$(openssl rand -hex 16)" > /srv/docker/wud/.env
chmod 600 /srv/docker/tcg-pokedex/.env /srv/docker/wud/.env
cd /srv/docker/tcg-pokedex && docker compose up -d --wait
cd /srv/docker/wud && docker compose up -d --wait
docker exec pihole pihole-FTL --config misc.dnsmasq_lines '["address=/mistoquente.de/192.168.1.201"]'
(crontab -l 2>/dev/null; echo "0 4 * * 0 /usr/bin/docker image prune -f >/dev/null 2>&1") | crontab -
```

- The password stays hex because it goes into the database URL as is.
- `chmod 600` is needed because `/srv/docker` has a default ACL that makes new files
  group-readable regardless of `umask`.
- Then add the two proxy hosts above in NPM (http://192.168.1.201:81), scheme `http`.

The GHCR package is public, so neither WUD nor Docker needs registry credentials.

## Syncing data

The app keeps two named volumes: `postgres-data` (the database) and `images` (card images,
set logos and symbols, mounted at `/data/images`). Both survive container updates. Back up
the database; the `images` volume can be lost, because the next image sync downloads it again.

```sh
cd /srv/docker/tcg-pokedex
docker compose exec app tcg sync catalog   # the TCGdex pt catalog
docker compose exec app tcg sync images    # tracked sets' card images, every set's artwork
```

Each prints its run as JSON and exits `0` (succeeded), `1` (partial) or `2` (failed).

## Which version is running

```sh
docker inspect -f '{{ index .Config.Labels "org.opencontainers.image.revision" }}' tcg-pokedex-app-1
```

## Manual rollback, and pausing auto-updates

Pin a commit sha. WUD only watches the pinned tag's digest, which never changes, so pinning
also pauses auto-updates for the app.

```sh
cd /srv/docker/tcg-pokedex
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

`docker compose stop` in `/srv/docker/wud` pauses WUD for every container.

## After an automatic rollback

The old container is running again, but the local `:latest` tag now points at the bad image.
Any later `docker compose up -d`, or a reboot followed by one, would deploy the bad image.
Right away, pin the last good sha as in "Manual rollback". Then fix forward on `main` and
resume auto-updates.

## Migration rule: expand/contract only

A rollback, manual or automatic, swaps the image but cannot undo a schema change. The app runs
its migrations on start, so by the time a rollback happens the new schema is already in place.
Every migration must therefore keep the previous release working:

- **Expand:** add tables, nullable columns, or columns with defaults. Never rename or drop in
  the same release that stops using them.
- **Contract:** drop or rename only in a later release, once no deployed version reads the old
  shape.

## Known quirks (WUD 9.4.1)

- WUD 9 refuses to start without an admin account, hence `WUD_ADMIN_PASSWORD`.
- The first `docker compose up -d` after an auto-update recreates the app once from the same
  image. WUD copies the old `com.docker.compose.image` label, so compose sees a difference.
  This is harmless.
- WUD's Docker Compose trigger ignores digest updates on an unpinned `:latest`, so the plain
  Docker trigger is used. It keeps the compose labels and network aliases, and `compose.yml`
  never changes on the server.

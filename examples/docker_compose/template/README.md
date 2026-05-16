# template

Base configuration files for creating a new compose stack. This directory is not a
runnable stack — copy it as a starting point for your own setup.

## How to use

```sh
cp -r examples/docker_compose/template examples/docker_compose/my_stack
cd examples/docker_compose/my_stack
cp .env.example .env
cp auth.env.example auth.env
cp api.env.example api.env
```

Edit `.env` to select your database engine (`SELECTED_DB=Mysql` or `Postgres`),
token mode, and algorithm, then fill in all secrets.

Run `bash init.sh` to generate RSA/EC keys (if using RS256/ES*) and TLS certificates.
DB provisioning runs automatically on first `docker compose up -d` via `init-db.sh`.

To reset the database later: `bash init.sh --reset-db` (prompts for confirmation).
To rotate keys without reinitializing: `bash init.sh --rotate-keys`.

For the DB isolation model, see `.env.example` — choose Scenario 1 (single shared DB),
Scenario 2 (per-service, default), or Scenario 3 (N arbitrary services). See the
[database isolation guide](../README.md#database-isolation) for full documentation.

Refer to the other stacks in `examples/docker_compose/` for complete working examples:

| Stack | Key difference |
| --- | --- |
| [local_mysql_m8](../local_mysql_m8/) | MariaDB + hybrid mode — simplest to run |
| [dev_postgres_m8](../dev_postgres_m8/) | PostgreSQL + stateful mode |
| [stateful_m8](../stateful_m8/) | MariaDB + stateful + Prometheus/Grafana |
| [RS256_m8](../RS256_m8/) | Asymmetric RS256 signing + JWKS endpoint |

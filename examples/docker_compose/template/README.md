# template

Base configuration files for creating a new Docker Compose stack. This directory is **not a runnable stack** — copy it as a starting point for your own setup.

---

## How to use

```sh
# Copy the template to a new stack directory
cp -r examples/docker_compose/template examples/docker_compose/my_stack
cd examples/docker_compose/my_stack

# Copy env files and fill in all secrets
cp auth.env.example auth.env
cp api.env.example api.env
```

Edit `auth.env` to choose:

- **Database engine** — `SELECTED_DB=Mysql` (MariaDB) or `SELECTED_DB=Postgres`
- **Token mode** — `TOKEN_MODE=stateless` / `hybrid` / `stateful`
- **Signing algorithm** — `ACCESS_TOKEN_ALGORITHM=HS256` / `RS256` / `ES256`

Generate keys and TLS certificates:

```sh
bash init.sh
# For RS256/ES256: also generates the key pair and writes ACCESS_KEY_ID into auth.env
# On Windows: use Git Bash or WSL
```

Start the stack — DB provisioning runs automatically on first boot:

```sh
docker compose up -d --build
```

Reset the database later:

```sh
bash init.sh --reset-db    # prompts for confirmation; use --yes for CI
```

Rotate keys without reinitializing:

```sh
bash init.sh --rotate-keys
```

---

## Database isolation

For the DB isolation model, see the scenario blocks in `auth.env.example` — choose Scenario 1 (single shared DB), Scenario 2 (per-service isolation, default), or Scenario 3 (N arbitrary services). See the [database isolation guide](../README.md#database-isolation) for full documentation.

---

## Choosing a base stack

Refer to the complete working stacks for examples of each combination:

| Stack | Algorithm | Token mode | Database | Monitoring | Key difference |
| --- | --- | --- | --- | --- | --- |
| [lite_mysql_m8](../lite_mysql_m8/) | HS256 | hybrid | MariaDB | — | Simplest to run |
| [lite_postgres_m8](../lite_postgres_m8/) | HS256 | stateful | PostgreSQL | — | PostgreSQL variant |
| [lite_rs256_m8](../lite_rs256_m8/) | RS256 | stateful | MariaDB | — | Asymmetric + JWKS |
| [lite_es256_m8](../lite_es256_m8/) | ES256 | stateful | MariaDB | — | ECDSA asymmetric |
| [lite_hybrid_m8](../lite_hybrid_m8/) | RS256 | hybrid | MariaDB | — | RS256 + hybrid mode |
| [lite_stateless_m8](../lite_stateless_m8/) | HS256 | stateless | MariaDB | — | No Redis for JWT |
| [stateful_m8](../stateful_m8/) | HS256 | stateful | MariaDB | Prometheus + Grafana | Full stateful + metrics |
| [env_rs256_m8](../env_rs256_m8/) | RS256 | stateful | MariaDB | Prometheus + Grafana | RS256 + metrics |
| [vault_rs256_postgres_m8](../vault_rs256_postgres_m8/) | RS256 | stateful | PostgreSQL | Prometheus + Grafana | HashiCorp Vault secrets |

---

> [Docker Compose examples](../README.md) · [Repository root](https://github.com/mano8/fa-auth-m8/tree/main)

# Docker Services and Observability Stack

This project provides a local industrial and IoT stack built with Docker Compose. It includes databases, Kafka and Schema Registry, Node-RED, an OPC UA demo server, and a Grafana, Loki, and Alloy observability stack.

## Prerequisites

- Docker Engine or Rancher Desktop with Docker Compose support.
- A Linux or WSL environment for the `/data/...` bind-mounted directories.
- The ports listed below must be available.

Start the stack from the project root:

```bash
docker compose up -d --build
docker compose ps
```

Stop the stack without removing persistent data:

```bash
docker compose down
```

## Services

| Service | Container | Port(s) | Purpose |
| --- | --- | --- | --- |
| PostgreSQL | `postgres` | `5432` | General-purpose PostgreSQL database using `appdb`. |
| TimescaleDB | `timescaledb` | `5433` | PostgreSQL-compatible time-series database. Initialization scripts are loaded from `postgres-init/`. |
| pgAdmin | `pgadmin` | `5050` | Web administration interface for PostgreSQL and TimescaleDB. |
| Node-RED | `nodered` | `1880` | Flow-based integration and automation runtime, built from the root `Dockerfile`. |
| Kafka | `kafka` | `9094` external, `9092` internal | Single-node Kafka broker using KRaft mode. |
| Schema Registry | `schema-registry` | `8081` | Stores and serves Kafka message schemas. |
| AKHQ | `akhq` | `8080` | Web interface for Kafka topics, brokers, and schemas. |
| OPC UA Server | `opc-server` | `4840`, `53880` | Demo OPC UA server implemented in `opcua-server/server.py`. |
| Loki | `loki` | `3100` | Log database and HTTP API. |
| Alloy | `alloy` | internal | Discovers Docker containers and forwards their logs to Loki. |
| Grafana | `grafana` | `3000` | Dashboards for logs and future metrics. |

The InfluxDB service is currently commented out in `docker-compose.yml`; it is not started by the stack.

### Default credentials

The current Compose file contains development credentials:

- PostgreSQL and TimescaleDB: `admin` / `admin123`, database `appdb`.
- pgAdmin: `admin@admin.com` / `admin123`.
- Grafana: `admin` / `admin123`.

Change these values before using the stack outside a trusted development environment.

### Access URLs

- Grafana: `http://localhost:3000`
- pgAdmin: `http://localhost:5050`
- AKHQ: `http://localhost:8080`
- Loki readiness: `http://localhost:3100/ready`
- Schema Registry: `http://localhost:8081`
- OPC UA: `opc.tcp://localhost:53880/UA/MinimalServer`
- Nodered: `http://localhost:1880`

## Persistent storage

| Host directory | Container path | Used by |
| --- | --- | --- |
| `/data/postgresql` | `/var/lib/postgresql/data` | PostgreSQL |
| `/data/timescaledb` | `/var/lib/postgresql/data` | TimescaleDB |
| `/data/nodered` | `/data` | Node-RED flows and runtime data |
| `/data/kafka` | `/var/lib/kafka/data` | Kafka |
| `/data/schema-registry` | `/var/lib/schema-registry` | Schema Registry |
| `/data/loki` | `/loki` | Loki chunks, index, and rules |
| `/data/alloy` | `/var/lib/alloy` | Alloy state and positions |
| `/data/grafana` | `/var/lib/grafana` | Grafana database, plugins, and state |

Grafana provisioning files are mounted read-only from `observability/grafana/provisioning`.

## Directory permissions

Create the directories before starting the stack:

```bash
sudo mkdir -p /data/postgresql /data/timescaledb /data/nodered /data/kafka /data/schema-registry /data/loki /data/alloy /data/grafana
```

The images use different users. The commonly used ownership commands are:

```bash
# PostgreSQL and TimescaleDB commonly use UID/GID 999.
sudo chown -R 999:999 /data/postgresql /data/timescaledb

# Node-RED, Kafka, Schema Registry, and Alloy commonly use UID/GID 1000.
sudo chown -R 1000:1000 /data/nodered /data/kafka /data/schema-registry /data/alloy

# Loki uses UID/GID 10001.
sudo chown -R 10001:10001 /data/loki

# Grafana uses UID/GID 472.
sudo chown -R 472:472 /data/grafana
```

Verify an image before changing ownership if its version changes:

```bash
docker run --rm postgres:16 id postgres
docker run --rm timescale/timescaledb:latest-pg16 id postgres
docker run --rm apache/kafka:4.3.1 id
docker run --rm confluentinc/cp-schema-registry:8.2.2 id
docker run --rm grafana/loki:3.5.0 id
docker run --rm grafana/alloy:v1.10.2 id
docker run --rm grafana/grafana:12.1.1 id
```

Avoid using `chmod 777` as a permanent fix. If a service reports `permission denied`, verify the container user and the ownership of its bind-mounted host directory.

## OPC UA server

The implementation is in `opcua-server/server.py`. The image is built from `opcua-server/Dockerfile` and runs `python server.py`.

### What `server.py` does

1. Creates an asynchronous `asyncua.Server`.
2. Listens on `opc.tcp://0.0.0.0:53880/UA/MinimalServer`.
3. Registers the namespace `http://demo.local/opcua`.
4. Creates the `DemoTP` object under the OPC UA Objects folder.
5. Creates `CAB`, `Direction`, and `Speed` as `Int16` variables initialized to `0`.
6. Calls `set_writable()` so clients can read and write each tag.
7. Reads every tag once per second.
8. Writes an application log only when a tag value changes.
9. Reduces the noisy `asyncua.server.subscription_service` logger to `WARNING` while preserving warnings and errors.

Example application log:

```text
INFO __main__: Tag Speed changed from 0 to 25
```

The server writes to stdout. Docker captures the output, Alloy collects it, and Loki stores it for Grafana.

### Adding a new tag

Add a tuple to the `tags` tuple:

```python
tags = (
	("CAB", ua.VariantType.Int16),
	("Direction", ua.VariantType.Int16),
	("Speed", ua.VariantType.Int16),
	("Temperature", ua.VariantType.Float),
)
```

The existing loop creates the variable, initializes it to `0`, and makes it writable. Available examples include:

```python
ua.VariantType.Int16
ua.VariantType.Int32
ua.VariantType.Float
ua.VariantType.Double
ua.VariantType.Boolean
ua.VariantType.String
```

For non-numeric tags, update the initial value in `ua.Variant(...)`. For example, use `ua.Variant(False, ua.VariantType.Boolean)` for a Boolean tag. Keep the NodeId and QualifiedName consistent with the tag name.

Rebuild and restart after changing the server:

```bash
docker compose up -d --build opc-server
docker logs -f opc-server
```

## Observability

### Alloy

Alloy discovers Docker containers through the read-only Docker socket mounted at `/var/run/docker.sock`. The configuration is in `observability/alloy-config.alloy`.

Alloy adds these labels to each discovered stream:

- `container`: the Docker container name, for example `opc-server`.
- `service`: the Docker Compose service name, for example `opc-server`.

Alloy sends logs to `http://loki:3100/loki/api/v1/push`.

### Loki

Loki is configured in `observability/loki-config.yml`. It stores data under `/loki`, backed by `/data/loki` on the host. Retention is currently seven days:

```yaml
retention_period: 168h
```

Useful LogQL queries:

```logql
{service="opc-server"}
{container="grafana"}
{service=~".+"}
```

### Grafana provisioning

The Loki datasource is defined in `observability/grafana/provisioning/datasources/loki.yml` with the fixed UID `loki`.

Dashboards are provisioned by `observability/grafana/provisioning/dashboards/dashboards.yml` from `/etc/grafana/provisioning/dashboards/services`. This maps to the repository directory `observability/grafana/provisioning/dashboards/services`.

## Grafana dashboards

There is one dashboard per active Compose service. Each dashboard contains:

1. One **Logs** panel backed by Loki and filtered to the service label.
2. One **Metrics** panel.

The metrics panels are currently informational placeholders because no Prometheus or InfluxDB datasource is configured. They do not generate failed datasource queries.

| Dashboard | Log query | Metrics status |
| --- | --- | --- |
| PostgreSQL | `{service="postgres"}` | Placeholder |
| TimescaleDB | `{service="timescaledb"}` | Placeholder |
| pgAdmin | `{service="pgadmin"}` | Placeholder |
| Node-RED | `{service="nodered"}` | Placeholder |
| Kafka | `{service="kafka"}` | Placeholder |
| Schema Registry | `{service="schema-registry"}` | Placeholder |
| AKHQ | `{service="akhq"}` | Placeholder |
| OPC UA Server | `{service="opc-server"}` | Placeholder |
| Loki | `{service="loki"}` | Placeholder |
| Alloy | `{service="alloy"}` | Placeholder |
| Grafana | `{service="grafana"}` | Placeholder |

The older multi-service dashboard is still stored as `observability/grafana/provisioning/dashboards/grafana-logs.json`, but it is outside the provider path used for the per-service dashboards.

### Adding real metrics

To replace the metrics placeholders:

1. Add a metrics backend such as Prometheus or InfluxDB.
2. Provision its datasource in Grafana.
3. Expose or collect metrics from the target service.
4. Replace the text panel in that service dashboard with a Grafana metrics panel and the correct query.

## Troubleshooting

```bash
docker compose logs --tail=100 loki
docker compose logs --tail=100 alloy
docker compose logs --tail=100 grafana
docker logs --tail=100 opc-server
```

Check Loki readiness and labels:

```bash
curl http://localhost:3100/ready
curl http://localhost:3100/loki/api/v1/labels
curl http://localhost:3100/loki/api/v1/label/service/values
curl http://localhost:3100/loki/api/v1/label/container/values
```

If Loki reports `permission denied` for `/loki/rules`, fix `/data/loki` ownership with UID/GID `10001:10001`. If Alloy reports an invalid `target` attribute, use `target_label` in `discovery.relabel` rules.

## Useful commands

```bash
# Start or rebuild the complete stack.
docker compose up -d --build

# Restart observability services.
docker compose up -d loki alloy grafana

# Force Grafana to reload provisioned dashboards.
docker compose restart grafana

# Rebuild the OPC UA server after a code change.
docker compose up -d --build opc-server
```

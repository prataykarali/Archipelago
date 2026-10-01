# Archipelago Load & Performance Testing

This directory provides load testing scripts using [Locust](https://locust.io/) to measure concurrent student capacity, P50/P95/P99 latency, and error rates under peak burst loads (100–200 req/sec).

## Prerequisites

```bash
pip install locust
```

## Running Locust

### Interactive Web UI

```bash
locust -f tests/performance/locustfile.py --host http://localhost:5151
```
Open `http://localhost:8089` in your browser. Configure:
- Number of users: e.g. 50
- Spawn rate: e.g. 5 users/sec
- Host: `http://localhost:5151`

### Headless Execution (CI/Automated Benchmarks)

```bash
locust -f tests/performance/locustfile.py \
  --headless \
  -u 100 \
  -r 10 \
  -t 60s \
  --host http://localhost:5151 \
  --csv=results
```

## Measured Metrics

- **P50, P95, P99 Latency**
- **Throughput (Requests/sec)**
- **Error Rate & 429 Throttle Count**
- **AI Cache Hit Rate & Tokens Saved**

# Kube-burner

Kube-burner is a Kubernetes performance and scale test orchestration toolset. It provides multi-faceted functionality, the most important of which are summarized below.

# Input

- **Job**: `{job_name}`
- **Build ID**: `{build_id}`
- **Failed test**: `{failed_test}`
- **Failed step**: `{failed_step}`

## Kube-burner failure diagnosis

### Exit code meanings

- **0**: Success
- **1**: Unrecoverable error (API authorization failure, config parsing error, server error, etc.)
- **2**: Benchmark timeout (execution time exceeded `--timeout`)
- **3**: Alerting error — a Prometheus alert at error/critical severity fired during the test
- **4**: Measurement error — a measurement threshold was violated (e.g. pod startup latency P99 exceeded limit)

For **exit code 3** (alerting), extract from the log:
- Which alerts fired, their severity, and their values
- Contributing system conditions: etcd latency spikes (commit > 30ms, fsync > 10ms), API server request latency > 1s, leader election churn, node component failures (ovnkube-node, kubelet)
- Whether alerts indicate a transient infrastructure issue or a genuine OCP regression

For **exit code 4** (measurement), extract from the log:
- Which measurements failed and by how much (actual value vs threshold)
- The error rate percentage
- Whether the failure is isolated to one workload iteration or systemic
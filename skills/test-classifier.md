# Input

- **Job**: `{job_name}`
- **Build ID**: `{build_id}`
- **Failed test**: `{failed_test}`
- **Failed step**: `{failed_step}`

# Tools

1. **`fetch_artifact(url)`** — HTTP GET for **non-GitHub** URLs: Prow/gcsweb artifacts, raw logs, JSON, etc.

# Diagnosis Procedure

Follow these steps in order. Do not skip steps. Think carefully between each step about what you've learned before proceeding.

## Step 1 Fetch the failed step's build log

Fetch the ci-operator structured log:

```
{artifacts_base}/gcs/test-platform-results/logs/{job_name}/{build_id}/artifacts/{failed_step}/{failed_test}/build-log.txt
```

## Step 2 Classify the failed test

Read the log and classify the type of test that failed into one of the following categories:
- `kube-burner`
- `orion`
- `k8s-netperf`
- `ingress-perf`
- `other`

## Step 3 Return the classification

Return just the classification, no other text or explanation.
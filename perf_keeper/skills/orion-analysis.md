# Orion analysis

Orion stands as a powerful command-line tool designed for identifying regressions within perf-scale CPT (Continuous Performance Testing) runs, leveraging metadata provided during the process.

## Tools

1. **`fetch_artifact(url)`** — HTTP GET for **non-GitHub** URLs: Prow/gcsweb artifacts, raw logs, JSON, etc.

2. **`fetch_github_pull_request(pr_url)`** — GitHub **REST API** for a PR’s title, body, and labels. Required for every `https://github.com/<owner>/<repo>/pull/<number>` link (for example Orion “Related PRs”). **Do not** use `fetch_artifact` on `github.com/.../pull/...` pages; those return HTML.

3. **`openshift-release(url)`** — MCP tools: `compare_releases` uses the **Sippy** payload diff API (PRs between two payload tags). `compare_rhcos_rpms` and `get_component_rpms` use the OpenShift release / RHCOS paths as before.

The artifacts base URL is:

`{artifacts_base}/gcs/test-platform-results/logs/{job_name}/{build_id}/`

There can be two types of Orion tests:

### A) Orion report test (failed test name is "openshift-qe-orion-report")

Orion is a performance regression detection tool, that gets executed once the benchmarks are finished. The openshift-qe-orion-report job generates a report that contains information about all the potential performance regressions from the previous benchmark executions.

Fetch the regression report

```
{artifacts_base}/gcs/test-platform-results/logs/{job_name}/{build_id}/artifacts/{failed_step}/{failed_test}/artifacts/orion-report-summary.txt
```

Regressing benchmarks are reported as follows:

```
Regression(s) found :
--------------------------------------------------
Test:  `orion_test_name`:
Changepoint at:       `regressing_version`
Previous version:     `previous_version`
Build:                `build_url`

Affected Metrics
+---------------------+---------+---------------------+-----------------+
| Metric              | Value   | Percentage change   | Labels          |
+=====================+=========+=====================+=================+
|  `metric_name`      | `value` | `percentage_change`|  `jira_labels`   |
+---------------------+---------+---------------------+-----------------+
Related PRs (2):                                         
  * `pr_url_1`
  * `pr_url_2`
  * ...
```

### B) Orion failure (failed test name contains "openshift-qe-orion" and is different from "openshift-qe-orion-report")

Orion is a performance regression detection tool, these tests are run after each benchmark execution.

Exit code meanings:
- **0**: Success
- **1**: User/config/input error: Used for CLI/config failures
- **2**: Performance regression detected
- **3**: No data found: The test did not run because there was no data to analyze

Fetch the orion log at:

```
{artifacts_base}/gcs/test-platform-results/logs/{job_name}/{build_id}/artifacts/{failed_step}/{failed_test}/build-log.txt
```

## Diagnosis Procedure

Follow these steps in order. Do not skip steps. Think carefully between each step about what you've learned before proceeding.

### Step 1: Compare the payload versions

If there's a performance regression derived from a different version of the payload, use **`openshift-release`** to compare `regresssion_version` and `previous_version`. Then for eery PR discovered in the diff, call **`fetch_github_pull_request`**. Summarize each PR’s intent from the returned **title** and **body** in your Evidence section,

### Step 2: Compare the RHCOS versions

If the diff doesn't contain any relevant PR, you can compare the RHCOS RPM differences between the RHCOS (Red Hat Core OS) versions of the current and previous payload.

### Step 3: Compare the RPM differences

And last resort, compare the RPM differences in the CNI component `ovn-kubernetes`, focusing in the `ovn` packages
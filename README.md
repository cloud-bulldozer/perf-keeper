# perf-keeper

AI agent for diagnosing OpenShift Performance & Scale regressions in Prow CI jobs.

Given a failed Prow job URL, the agent automatically extracts job metadata, identifies the failing test, gathers evidence from CI artifacts, and produces a structured root-cause analysis report.

## How it works

The agent is built on [LangGraph](https://github.com/langchain-ai/langgraph) and follows this workflow:

1. **Extract job info** - Parse the Prow job URL for job name and build ID
2. **Check job status** - If the job passed, exit early
3. **Identify failing test** - Parse `ci-operator.log` to find the failed step/test
4. **Route analysis** - Choose between Orion (performance regression) or generic (test failure) analysis
5. **AI-guided analysis** - The LLM uses tools to fetch artifacts, inspect GitHub PRs, compare OCP payloads, and correlate findings
6. **Final report** - Generate a structured Markdown RCA report

### Analysis types

- **Orion analysis**: For performance regression tests (`openshift-qe-orion*`). Analyzes regression metrics, compares OCP release payloads via Sippy, fetches RHCOS RPM diffs, and identifies suspect PRs.
- **Generic analysis**: For other test failures. Categorizes failures (infrastructure, installation, test execution, day-2 ops), analyzes benchmarks, and cross-references system health.

### Tools available to the agent

| Tool | Description |
|------|-------------|
| `fetch_artifact` | Fetch text from any HTTP URL (CI logs, JSON reports, etc.) |
| `fetch_github_pull_request` | Get PR metadata (title, body, labels, state) via GitHub REST API |
| `compare_releases` | Compare two OCP payloads via Sippy to identify PR changes |
| `compare_rhcos_rpms` | Compare RHCOS RPM differences between versions |
| `get_component_rpms` | Retrieve component-specific RPM information |

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A Google Gemini API key
- A GitHub personal access token (for PR analysis)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd perf-keeper

# Install dependencies with uv (recommended)
uv sync

# Or with pip
pip install -e .

# For development dependencies (pytest, etc.)
uv sync --extra dev
# or
pip install -e ".[dev]"
```

## Configuration

Create a `.env` file in the project root with the following variables:

```bash
# Required
GITHUB_TOKEN=<your-github-personal-access-token>   # Needs read access to repos
GOOGLE_API_KEY=<your-google-gemini-api-key>

# Optional - LLM configuration
MODEL_NAME=gemini-2.5-flash          # Gemini model to use (default: gemini-2.5-pro)
LLM_TEMPERATURE=0                    # 0 for deterministic outputs
MAX_OUTPUT_TOKENS=1024               # Max tokens for the final report

# Optional - Prow infrastructure URLs (defaults shown)
PROW_ARTIFACTS_URL=https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com
PROW_DOMAIN=https://prow.ci.openshift.org
```

You can copy the template and fill in your values:

```bash
cat > .env << 'EOF'
GITHUB_TOKEN=
GOOGLE_API_KEY=
MODEL_NAME=gemini-2.5-flash
LLM_TEMPERATURE=0
MAX_OUTPUT_TOKENS=1024
PROW_ARTIFACTS_URL=https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com
PROW_DOMAIN=https://prow.ci.openshift.org
EOF
```

## CLI mode

The agent can be run in CLI mode to diagnose a failed Prow job.

```bash
# Diagnose a failed Prow job
perf-keeper --prow-job-url "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/<job-name>/<build-id>/"

# Show LLM token usage after the run
perf-keeper --prow-job-url "https://prow.ci.openshift.org/view/gs/..." --print-token-usage
```

If the job passed, the agent exits early with a success message. Otherwise, it prints the final RCA report to stdout.

> **Note**: Supported flags can be seen with `perf-keeper --help`.


## Server mode

The agent can be run in server mode to diagnose a failed Prow job via a REST API.

```bash
# Start the server
perf-keeper --server --port 8080
```

The server will listen on port 8080 and will diagnose the failed Prow job when a POST request is made to the `/analyze` endpoint.

```bash
curl -X POST "http://localhost:8080/analyze" -H "Content-Type: application/json" -d '{"job_url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/<job-name>/<build-id>/"}'
```

The server will return a JSON response with the analysis result.

```json
{
    "passed": false,
    "analysis": "The job failed because of the following reason..."
}
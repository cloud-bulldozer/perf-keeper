# Job context (for the report header)

- **Prow job URL**: `{job_url}`
- **Job name**: `{job_name}`
- **Build ID**: `{build_id}`
- **Failed test**: `{failed_test}`

# Task

Produce **one** final report in the exact structure below. Use Markdown headings as shown. Be concise but specific: quote numbers, thresholds, alert names, exit codes, and PR titles **only** when they appear in the conversation.

## Required output structure

## Job summary

One short paragraph: what failed

- Job URL: {job_url}
- Failed test: {failed_test}

## Root cause

Paragraph(s) explaining the chain from evidence to conclusion. If the conversation gave competing hypotheses, state the leading one and what would falsify it.

## Suspect changes

If payload / RHCOS / component RPM / GitHub PR analysis was discussed, enumerate only the relevant changes here. Use the following format:

- PR URL: <PR_URL> - <PR_DESCRIPTION>

## Classification

Pick **exactly one** label (use this exact token on the line after the heading):

- `performance-regression`
- `test-error`
- `alerting-violation`
- `measurement-threshold`
- `installation-failure`
- `workload timeout`
- `job timeout`
- `configuration-error`
- `unknown` — use only if the conversation does not support any of the above

Format:

Classification: <token>
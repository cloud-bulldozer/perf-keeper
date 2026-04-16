from __future__ import annotations
import logging
import re
import os
from langchain_core.messages import SystemMessage
from langgraph.graph import END
from perfscale_agent.state import AgentState
import httpx

PROW_ARTIFACTS_URL = os.getenv("PROW_ARTIFACTS_URL", "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com")

logger = logging.getLogger(__name__)

# Extract the job name and build id from the URL
# https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/periodic-ci-openshift-eng-ocp-qe-perfscale-ci-main-metal-4.22-nightly-x86-daily-virt-6nodes/2041788597949960192/
# URL format is https://{prow_domain}/view/gs/test-platform-results/logs/{job_name}/{build_id}
def extract_job_info(state: AgentState) -> dict:
    job_url = state["job_url"]
    try:
        match = re.search(r'/logs/([^/]+)/(\d+)/?', job_url)
        if match:
            job_name, build_id = match.group(1), match.group(2)
            logger.info(
                "extract_job_info: resolved job_name=%r build_id=%r",
                job_name,
                build_id,
            )
            return {
                "job_name": job_name,
                "build_id": build_id,
            }
        else:
            logger.warning(
                "extract_job_info: no /logs/{job}/{build}/ pattern in URL: %s",
                job_url,
            )
            return {
                "messages": [
                    SystemMessage(content=f"Couldn't extract job name and build id from URL: {job_url}"),
                ]
            }
    except Exception as e:
        logger.exception("extract_job_info: unexpected error while parsing URL")
        return {
            "messages": [
                SystemMessage(content=f"Error parsing URL: {e}"),
            ]
        }

def set_job_state(state: AgentState) -> bool:
    """Check if a job is failed by checking the finished.json file"""
    job_name = state["job_name"]
    build_id = state["build_id"]
    try:
        url = f"{PROW_ARTIFACTS_URL}/gcs/test-platform-results/logs/{job_name}/{build_id}/finished.json"
        resp = httpx.get(url)
        resp.raise_for_status()
        json_data = resp.json()
        logger.info(f"set_job_state: job {job_name} {build_id} passed: {json_data.get('passed')}")
        return {
            "passed": json_data.get("passed"),
        }
    except Exception as e:
        return {
            "messages": [
                SystemMessage(content=f"Error checking job status: {e}"),
            ]
        }

def passed_condition(state: AgentState) -> str:
    if state.get("passed"):
        return END
    return "get_failed_test"

def get_failed_test(state: AgentState) -> dict:
    job_name = state["job_name"]
    build_id = state["build_id"]
    logger.info(f"get_failed_test: job_name={job_name} build_id={build_id}")
    url = f"{PROW_ARTIFACTS_URL}/gcs/test-platform-results/logs/{job_name}/{build_id}/artifacts/ci-operator.log"
    resp = httpx.get(url)
    # Look for the line containing
    # {"level":"error","msg":"\n  * could not run steps: step {step} failed: \"{step}\" test steps failed: \"{step}\" pod \"{step}-{test}\" failed: could not watch pod
    resp.raise_for_status()
    for line in resp.text.splitlines():
        if "test steps failed:" in line:
            step_name = re.search(r"could not run steps: step ([\w-]+)", line).group(1)
            pod_pattern = rf'pod \\?"{re.escape(step_name)}-([\w-]+)\\?"'
            test_name = re.search(pod_pattern, line).group(1)
            logger.info(f"get_failed_test: failed step={step_name} failed test={test_name}")
            return {
                "failed_step": step_name,
                "failed_test": test_name,
            }   
    return {
        "messages": [
            SystemMessage(content=f"No failed test found in ci-operator.log"),
        ]
    }
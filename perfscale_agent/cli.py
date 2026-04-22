"""CLI entry point for the perfscale diagnosis agent."""
from __future__ import annotations

import argparse
import logging
import os
import asyncio

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage
from urllib.parse import urlparse

from perfscale_agent.agent import create_agent


def _text_from_message_content(content: object) -> str | None:
    if content is None:
        return None
    if isinstance(content, str):
        s = content.strip()
        return s or None
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and block.get("text") is not None:
                    parts.append(str(block["text"]))
        s = "\n".join(parts).strip()
        return s or None
    return None


def _last_diagnosis_text(messages: list[BaseMessage]) -> str | None:
    """Prefer the latest AIMessage with non-empty text (skips tool-only turns)."""
    if not messages:
        return None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            text = _text_from_message_content(msg.content)
            if text:
                return text
    return _text_from_message_content(messages[-1].content)


def _print_token_totals(result: dict) -> None:
    inp = int(result.get("input_tokens") or 0)
    out = int(result.get("output_tokens") or 0)
    total = inp + out
    print(f"LLM tokens — input: {inp}  output: {out}  total: {total}")


async def run_non_interactive(job_url: str, *, print_token_usage: bool = False):
    logger = logging.getLogger(__name__)
    load_dotenv()
    agent = await create_agent()
    result = await agent.ainvoke({"job_url": job_url})
    if result.get("passed"):
        logger.info("✅ Job passed. No diagnosis required.")
        return
    final = (result.get("final_report") or "").strip()
    if final:
        print(f"\n{final}\n")
        if print_token_usage:
            _print_token_totals(result)
        return
    messages = result.get("messages") or []
    text = _last_diagnosis_text(messages)
    if text:
        print(f"\n{text}\n")
    else:
        logger.warning("No assistant text to print (e.g. last turn was tool calls only).")
    if print_token_usage:
        _print_token_totals(result)

def main():
    parser = argparse.ArgumentParser(description="OpenShift Perf & Scale Diagnosis Agent",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--prow-job-url", type=str, help="Prow job URL to diagnose (required)")
    parser.add_argument(
        "--log-level",
        type=str,
        default=os.environ.get("LOGLEVEL", "INFO"),
        choices=("debug", "info", "warning", "error"),
        help="Log level for agent progress (default: info, or LOGLEVEL env)",
    )
    parser.add_argument(
        "--print-token-usage",
        action="store_true",
        help="After the run, print cumulative LLM input/output/total tokens",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.prow_job_url:
        try:
            urlparse(args.prow_job_url)
        except ValueError:
            parser.error("Invalid Prow job URL")
    else:
        parser.error("Prow job URL is required")
    asyncio.run(
        run_non_interactive(args.prow_job_url, print_token_usage=args.print_token_usage)
    )

if __name__ == "__main__":
    main()

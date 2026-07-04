"""IBM Code Engine job handler for IBM Daily Email Digest.

This module adapts the digest pipeline to run as an IBM Code Engine scheduled job.
Unlike Cloud Functions (event-driven), Code Engine jobs run as batch processes on a schedule.

Key differences from Cloud Functions:
  - Runs as a containerized job (not a function)
  - Scheduled via Code Engine cron jobs (not triggers)
  - Environment variables from Code Engine job configuration
  - Logs to IBM Cloud Logging
  - Exit code determines success/failure (not return value)

Deploy with:
  - IBM Code Engine runtime: Container (Python 3.11)
  - Memory: 512 MB - 1 GB
  - CPU: 0.5 - 1 vCPU
  - Timeout: 5-10 minutes
  - Schedule: Cron expression (e.g., "0 * * * *" for hourly)
"""
from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from datetime import datetime

# Configure logging for IBM Cloud Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def main() -> int:
    """IBM Code Engine job entry point. Runs the digest pipeline and returns exit code.
    
    Returns:
        0 for success, non-zero for failure (Code Engine uses exit codes)
    """
    try:
        logger.info("=== IBM Daily Digest Code Engine Job started ===")
        logger.info(f"Job execution time: {datetime.now().isoformat()}")
        
        # Log environment info
        job_name = os.getenv("CE_JOB", "unknown")
        job_run = os.getenv("CE_JOBRUN", "unknown")
        logger.info(f"Code Engine Job: {job_name}, Run: {job_run}")
        
        # Import here to ensure all environment variables are loaded
        from . import main as main_mod
        
        # Force IBM Cloud mode (uses SendGrid and IBM Cloud Object Storage)
        os.environ["EMAIL_METHOD"] = "sendgrid"
        os.environ["CLOUD_PROVIDER"] = "ibm"
        
        # Run the digest pipeline
        # - dry_run=False: real execution
        # - mock_llm=False: use real LLM
        # - send=True: send emails
        # - make_decks=False: skip PowerPoint decks (not needed for email digest)
        digest = main_mod.run(
            dry_run=False,
            mock_llm=False,
            send=True,
            make_decks=False
        )
        
        insights_count = len(digest.get("insights", []))
        logger.info(f"Digest completed successfully with {insights_count} insights")
        logger.info("=== IBM Daily Digest Code Engine Job completed successfully ===")
        
        return 0  # Success exit code
        
    except Exception as exc:
        logger.error(f"Code Engine Job execution failed: {exc}")
        logger.error(traceback.format_exc())
        return 1  # Failure exit code


if __name__ == "__main__":
    sys.exit(main())

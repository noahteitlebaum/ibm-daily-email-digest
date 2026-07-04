"""IBM Cloud Functions handler for IBM Daily Email Digest.

This module adapts the existing digest pipeline to run as an IBM Cloud Function,
triggered hourly by IBM Cloud Functions Triggers. It handles cloud-specific concerns:
  - IBM Cloud Object Storage-based state persistence (seen articles)
  - Environment variables from IBM Cloud Functions
  - SendGrid email delivery
  - Logging to IBM Cloud Logs

Deploy with:
  - IBM Cloud Functions runtime: Python 3.11+
  - Memory: 512 MB (adjust based on LLM response sizes)
  - Timeout: 5 minutes (300 seconds)
  - Trigger: Alarm trigger with cron schedule (hourly)
"""
from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import datetime

# Configure logging for IBM Cloud Logs
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def main(params: dict) -> dict:
    """IBM Cloud Functions entry point. Runs the digest pipeline and returns status.
    
    Args:
        params: Dictionary of parameters passed to the function (from trigger or invocation)
        
    Returns:
        Dictionary with statusCode and body (JSON response)
    """
    try:
        logger.info("=== IBM Daily Digest Cloud Function execution started ===")
        logger.info(f"Parameters: {json.dumps(params)}")
        
        # Import here to ensure all environment variables are loaded
        from . import main as main_mod
        
        # Force IBM Cloud mode (uses SendGrid and IBM Cloud Object Storage)
        os.environ["EMAIL_METHOD"] = "sendgrid"
        os.environ["CLOUD_PROVIDER"] = "ibm"
        
        # Run the digest pipeline
        # - dry_run=False: real execution
        # - mock_llm=False: use real LLM
        # - send=True: send emails
        # - make_decks=False: skip PowerPoint decks (lxml/python-pptx issues in cloud)
        digest = main_mod.run(
            dry_run=False,
            mock_llm=False,
            send=True,
            make_decks=False
        )
        
        logger.info("=== IBM Daily Digest Cloud Function execution completed successfully ===")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Digest completed successfully",
                "timestamp": datetime.now().isoformat(),
                "insights_count": len(digest.get("insights", [])),
                "activation_id": params.get("__ow_activation_id", "local")
            })
        }
        
    except Exception as exc:
        logger.error(f"Cloud Function execution failed: {exc}")
        logger.error(traceback.format_exc())
        
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Digest execution failed",
                "error": str(exc),
                "timestamp": datetime.now().isoformat(),
                "activation_id": params.get("__ow_activation_id", "local")
            })
        }


# For local testing
if __name__ == "__main__":
    # Simulate IBM Cloud Functions params for local testing
    result = main({"test": True})
    print(json.dumps(result, indent=2))

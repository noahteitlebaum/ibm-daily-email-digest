"""AWS Lambda handler for IBM Daily Email Digest.

This module adapts the existing digest pipeline to run as an AWS Lambda function,
triggered hourly by EventBridge. It handles cloud-specific concerns:
  - S3-based state persistence (seen articles)
  - Environment variables from Lambda/Secrets Manager
  - SMTP-only email delivery (no Outlook COM)
  - Logging to CloudWatch

Deploy with:
  - Lambda runtime: Python 3.11+
  - Memory: 512 MB (adjust based on LLM response sizes)
  - Timeout: 5 minutes (300 seconds)
  - EventBridge rule: rate(1 hour)
"""
from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import datetime

# Configure logging for CloudWatch
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: dict, context) -> dict:
    """AWS Lambda entry point. Runs the digest pipeline and returns status."""
    try:
        logger.info("=== IBM Daily Digest Lambda execution started ===")
        logger.info(f"Event: {json.dumps(event)}")
        
        # Import here to ensure all environment variables are loaded
        from . import main as main_mod
        
        # Force SES mode for cloud (no Outlook COM or SMTP needed)
        os.environ["EMAIL_METHOD"] = "ses"
        
        # Run the digest pipeline
        # - dry_run=False: real execution
        # - mock_llm=False: use real LLM
        # - send=True: send emails
        # - make_decks=False: skip PowerPoint decks (lxml/python-pptx issues in Lambda)
        digest = main_mod.run(
            dry_run=False,
            mock_llm=False,
            send=True,
            make_decks=False
        )
        
        logger.info("=== IBM Daily Digest Lambda execution completed successfully ===")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Digest completed successfully",
                "timestamp": datetime.now().isoformat(),
                "insights_count": len(digest.get("insights", [])),
                "execution_id": context.aws_request_id if context else "local"
            })
        }
        
    except Exception as exc:
        logger.error(f"Lambda execution failed: {exc}")
        logger.error(traceback.format_exc())
        
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Digest execution failed",
                "error": str(exc),
                "timestamp": datetime.now().isoformat(),
                "execution_id": context.aws_request_id if context else "local"
            })
        }


# For local testing
if __name__ == "__main__":
    # Simulate Lambda event/context for local testing
    class MockContext:
        request_id = "local-test-123"
        
    result = lambda_handler({}, MockContext())
    print(json.dumps(result, indent=2))

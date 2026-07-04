"""Deploy IBM Daily Email Digest to IBM Code Engine.

This script automates the deployment of the digest to IBM Code Engine as a scheduled job.
It handles:
  - Building and pushing Docker image to IBM Container Registry
  - Creating/updating Code Engine project
  - Creating/updating the scheduled job with environment variables
  - Setting up cron schedule for hourly execution

Prerequisites:
  - IBM Cloud CLI installed: https://cloud.ibm.com/docs/cli
  - Code Engine plugin: ibmcloud plugin install code-engine
  - Container Registry plugin: ibmcloud plugin install container-registry
  - Docker installed and running
  - Logged in to IBM Cloud: ibmcloud login

Usage:
  python deploy_code_engine.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        print(f"ERROR: Command failed with exit code {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        sys.exit(1)
    return result


def check_prerequisites():
    """Check that required tools are installed."""
    print("Checking prerequisites...")
    
    # Check IBM Cloud CLI
    result = run_command(["ibmcloud", "version"], check=False)
    if result.returncode != 0:
        print("ERROR: IBM Cloud CLI not found. Install from:")
        print("https://cloud.ibm.com/docs/cli")
        sys.exit(1)
    
    # Check Code Engine plugin
    result = run_command(["ibmcloud", "plugin", "list"], check=False)
    if "code-engine" not in result.stdout:
        print("ERROR: Code Engine plugin not installed.")
        print("Install with: ibmcloud plugin install code-engine")
        sys.exit(1)
    
    # Check Container Registry plugin
    if "container-registry" not in result.stdout:
        print("ERROR: Container Registry plugin not installed.")
        print("Install with: ibmcloud plugin install container-registry")
        sys.exit(1)
    
    # Check Docker
    result = run_command(["docker", "version"], check=False)
    if result.returncode != 0:
        print("ERROR: Docker not found or not running.")
        print("Install Docker Desktop and ensure it's running.")
        sys.exit(1)
    
    # Check IBM Cloud login
    result = run_command(["ibmcloud", "target"], check=False)
    if result.returncode != 0:
        print("ERROR: Not logged in to IBM Cloud.")
        print("Login with: ibmcloud login")
        sys.exit(1)
    
    print("✓ All prerequisites met")


def get_config():
    """Get deployment configuration from user."""
    print("\n=== Deployment Configuration ===")
    
    # Project name
    project_name = input("Code Engine project name [ibm-digest]: ").strip() or "ibm-digest"
    
    # Region
    print("\nAvailable regions: us-south, us-east, eu-de, eu-gb, jp-tok, au-syd")
    region = input("Region [us-south]: ").strip() or "us-south"
    
    # Resource group
    result = run_command(["ibmcloud", "resource", "groups"], check=False)
    print("\nAvailable resource groups:")
    print(result.stdout)
    resource_group = input("Resource group [Default]: ").strip() or "Default"
    
    # Container Registry namespace
    registry_namespace = input("Container Registry namespace [ibm-digest]: ").strip() or "ibm-digest"
    
    # Image name
    image_name = input("Image name [daily-digest]: ").strip() or "daily-digest"
    
    # Job name
    job_name = input("Job name [daily-digest-job]: ").strip() or "daily-digest-job"
    
    # Schedule
    print("\nCron schedule examples:")
    print("  0 * * * * = Every hour")
    print("  0 */2 * * * = Every 2 hours")
    print("  0 9 * * * = Daily at 9 AM UTC")
    print("  0 13 * * 1-5 = Weekdays at 1 PM UTC (9 AM EST)")
    schedule = input("Cron schedule [0 * * * *]: ").strip() or "0 * * * *"
    
    return {
        "project_name": project_name,
        "region": region,
        "resource_group": resource_group,
        "registry_namespace": registry_namespace,
        "image_name": image_name,
        "job_name": job_name,
        "schedule": schedule,
    }


def setup_container_registry(namespace: str, region: str):
    """Set up IBM Container Registry namespace."""
    print(f"\n=== Setting up Container Registry namespace: {namespace} ===")
    
    # Target the region
    run_command(["ibmcloud", "cr", "region-set", region])
    
    # Create namespace (ignore if exists)
    result = run_command(["ibmcloud", "cr", "namespace-add", namespace], check=False)
    if result.returncode == 0:
        print(f"✓ Created namespace: {namespace}")
    else:
        print(f"✓ Namespace already exists: {namespace}")
    
    # Login to registry
    run_command(["ibmcloud", "cr", "login"])


def build_and_push_image(namespace: str, image_name: str, region: str) -> str:
    """Build Docker image and push to IBM Container Registry."""
    print(f"\n=== Building and pushing Docker image ===")
    
    # Determine registry URL based on region
    registry_urls = {
        "us-south": "us.icr.io",
        "us-east": "us.icr.io",
        "eu-de": "de.icr.io",
        "eu-gb": "uk.icr.io",
        "jp-tok": "jp.icr.io",
        "au-syd": "au.icr.io",
    }
    registry_url = registry_urls.get(region, "us.icr.io")
    
    # Full image name with tag
    tag = datetime.now().strftime("%Y%m%d-%H%M%S")
    full_image = f"{registry_url}/{namespace}/{image_name}:{tag}"
    latest_image = f"{registry_url}/{namespace}/{image_name}:latest"
    
    print(f"Building image: {full_image}")
    
    # Build image
    run_command(["docker", "build", "-t", full_image, "-t", latest_image, "."])
    
    # Push both tags
    print(f"Pushing image to registry...")
    run_command(["docker", "push", full_image])
    run_command(["docker", "push", latest_image])
    
    print(f"✓ Image pushed: {full_image}")
    return latest_image


def setup_code_engine_project(project_name: str, region: str, resource_group: str):
    """Create or select Code Engine project."""
    print(f"\n=== Setting up Code Engine project: {project_name} ===")
    
    # Target resource group
    run_command(["ibmcloud", "target", "-g", resource_group])
    
    # Check if project exists
    result = run_command(["ibmcloud", "ce", "project", "list"], check=False)
    
    if project_name in result.stdout:
        print(f"✓ Project exists, selecting: {project_name}")
        run_command(["ibmcloud", "ce", "project", "select", "--name", project_name])
    else:
        print(f"Creating new project: {project_name}")
        run_command(["ibmcloud", "ce", "project", "create", "--name", project_name])
    
    print(f"✓ Code Engine project ready: {project_name}")


def get_environment_variables() -> dict[str, str]:
    """Collect environment variables from user."""
    print("\n=== Environment Variables Configuration ===")
    print("Enter the following environment variables (press Enter to skip optional ones):")
    
    env_vars = {}
    
    # Required variables
    required = [
        ("SENDGRID_API_KEY", "SendGrid API key (required)"),
        ("EMAIL_FROM", "Sender email address (required)"),
        ("EMAIL_TO", "Recipient email(s), comma-separated (required)"),
        ("IBM_COS_BUCKET", "IBM Cloud Object Storage bucket name (required)"),
        ("IBM_COS_ENDPOINT", "COS endpoint URL (required)"),
        ("IBM_COS_API_KEY", "COS API key (required)"),
        ("IBM_COS_INSTANCE_CRN", "COS instance CRN (required)"),
        ("CLAUDE_API_KEY", "ICA Claude API key (required)"),
        ("CLAUDE_AUTH_SCHEME", "ICA Claude auth scheme (required)"),
        ("CLAUDE_CHAT_URL", "ICA Claude chat URL (required)"),
        ("CLAUDE_MODEL", "ICA Claude model (required)"),
    ]
    
    for var_name, description in required:
        value = input(f"{var_name} ({description}): ").strip()
        if not value:
            print(f"ERROR: {var_name} is required")
            sys.exit(1)
        env_vars[var_name] = value
    
    # Optional variables - none currently needed for Claude API
    optional = []
    
    for var_name, description in optional:
        value = input(f"{var_name} ({description}): ").strip()
        if value:
            env_vars[var_name] = value
    
    return env_vars


def create_or_update_job(job_name: str, image: str, env_vars: dict[str, str], schedule: str):
    """Create or update Code Engine job."""
    print(f"\n=== Creating/updating Code Engine job: {job_name} ===")
    
    # Check if job exists
    result = run_command(["ibmcloud", "ce", "job", "list"], check=False)
    job_exists = job_name in result.stdout
    
    # Build command
    cmd = [
        "ibmcloud", "ce", "job",
        "update" if job_exists else "create",
        "--name", job_name,
        "--image", image,
        "--cpu", "0.5",
        "--memory", "1G",
        "--maxexecutiontime", "600",  # 10 minutes
        "--retrylimit", "2",
    ]
    
    # Add environment variables
    for key, value in env_vars.items():
        cmd.extend(["--env", f"{key}={value}"])
    
    # Create/update job
    run_command(cmd)
    
    print(f"✓ Job {'updated' if job_exists else 'created'}: {job_name}")
    
    # Create or update job run subscription (schedule)
    print(f"\nSetting up cron schedule: {schedule}")
    
    subscription_name = f"{job_name}-schedule"
    
    # Check if subscription exists
    result = run_command(["ibmcloud", "ce", "subscription", "cron", "list"], check=False)
    sub_exists = subscription_name in result.stdout
    
    if sub_exists:
        # Update existing subscription
        run_command([
            "ibmcloud", "ce", "subscription", "cron", "update",
            "--name", subscription_name,
            "--destination-type", "job",
            "--destination", job_name,
            "--schedule", schedule,
        ])
        print(f"✓ Schedule updated: {subscription_name}")
    else:
        # Create new subscription
        run_command([
            "ibmcloud", "ce", "subscription", "cron", "create",
            "--name", subscription_name,
            "--destination-type", "job",
            "--destination", job_name,
            "--schedule", schedule,
        ])
        print(f"✓ Schedule created: {subscription_name}")


def test_job(job_name: str):
    """Run a test execution of the job."""
    print(f"\n=== Testing job: {job_name} ===")
    
    response = input("Run a test execution now? (y/n): ").strip().lower()
    if response != 'y':
        print("Skipping test execution")
        return
    
    print("Submitting job run...")
    result = run_command(["ibmcloud", "ce", "jobrun", "submit", "--job", job_name])
    
    # Extract job run name from output
    for line in result.stdout.split('\n'):
        if "Name:" in line:
            jobrun_name = line.split("Name:")[1].strip()
            print(f"\nJob run submitted: {jobrun_name}")
            print(f"Monitor with: ibmcloud ce jobrun get --name {jobrun_name}")
            print(f"View logs with: ibmcloud ce jobrun logs --name {jobrun_name}")
            break


def main():
    """Main deployment flow."""
    print("=" * 60)
    print("IBM Code Engine Deployment for IBM Daily Email Digest")
    print("=" * 60)
    
    # Check prerequisites
    check_prerequisites()
    
    # Get configuration
    config = get_config()
    
    # Setup Container Registry
    setup_container_registry(config["registry_namespace"], config["region"])
    
    # Build and push image
    image = build_and_push_image(
        config["registry_namespace"],
        config["image_name"],
        config["region"]
    )
    
    # Setup Code Engine project
    setup_code_engine_project(
        config["project_name"],
        config["region"],
        config["resource_group"]
    )
    
    # Get environment variables
    env_vars = get_environment_variables()
    
    # Create/update job
    create_or_update_job(
        config["job_name"],
        image,
        env_vars,
        config["schedule"]
    )
    
    # Test job
    test_job(config["job_name"])
    
    print("\n" + "=" * 60)
    print("✓ Deployment completed successfully!")
    print("=" * 60)
    print(f"\nYour digest will run on schedule: {config['schedule']}")
    print(f"\nUseful commands:")
    print(f"  View job: ibmcloud ce job get --name {config['job_name']}")
    print(f"  List runs: ibmcloud ce jobrun list --job {config['job_name']}")
    print(f"  View logs: ibmcloud ce jobrun logs --name <jobrun-name>")
    print(f"  Manual run: ibmcloud ce jobrun submit --job {config['job_name']}")
    print(f"  Update schedule: ibmcloud ce subscription cron update --name {config['job_name']}-schedule --schedule '<cron>'")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDeployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

"""Build deployment package for IBM Cloud Functions.

Creates a ZIP file containing all dependencies and source code optimized for
IBM Cloud Functions (Python 3.11 runtime).

Usage:
    python deploy_ibm_cloud.py

Output:
    ibm_cloud_deployment.zip (~50MB)

The ZIP structure is:
    __main__.py                    # Entry point that imports src.ibm_cloud_handler
    src/                           # Application code
    ├── ibm_cloud_handler.py      # Cloud Functions handler
    ├── state_cos.py              # IBM Cloud Object Storage state
    ├── emailer_sendgrid.py       # SendGrid email sender
    └── ...                       # Other modules
    <dependencies>/               # All pip packages

Deploy to IBM Cloud Functions:
    ibmcloud fn action create ibm-daily-digest \
        --kind python:3.11 \
        --memory 512 \
        --timeout 300000 \
        ibm_cloud_deployment.zip \
        --main main
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"
OUTPUT_ZIP = ROOT / "ibm_cloud_deployment.zip"


def main() -> None:
    """Build the deployment package."""
    print("=" * 70)
    print("IBM Cloud Functions Deployment Package Builder")
    print("=" * 70)
    
    # Create temporary directory for building
    with tempfile.TemporaryDirectory() as tmpdir:
        build_dir = Path(tmpdir)
        print(f"\n📦 Building in: {build_dir}")
        
        # Step 1: Install dependencies
        print("\n[1/4] Installing dependencies...")
        install_dependencies(build_dir)
        
        # Step 2: Copy source code
        print("\n[2/4] Copying source code...")
        copy_source(build_dir)
        
        # Step 3: Copy configuration files
        print("\n[3/4] Copying configuration files...")
        copy_config(build_dir)
        
        # Step 4: Create entry point
        print("\n[4/4] Creating entry point...")
        create_entry_point(build_dir)
        
        # Create ZIP file
        print(f"\n📦 Creating ZIP: {OUTPUT_ZIP.name}")
        if OUTPUT_ZIP.exists():
            OUTPUT_ZIP.unlink()
        
        shutil.make_archive(
            str(OUTPUT_ZIP.with_suffix("")),
            "zip",
            build_dir
        )
        
        size_mb = OUTPUT_ZIP.stat().st_size / (1024 * 1024)
        print(f"✅ Created: {OUTPUT_ZIP} ({size_mb:.1f} MB)")
        
        print("\n" + "=" * 70)
        print("Deployment package ready!")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Install IBM Cloud CLI: https://cloud.ibm.com/docs/cli")
        print("2. Install Cloud Functions plugin: ibmcloud plugin install cloud-functions")
        print("3. Login: ibmcloud login")
        print("4. Target resource group: ibmcloud target -g <resource-group>")
        print("5. Deploy:")
        print(f"   ibmcloud fn action create ibm-daily-digest \\")
        print(f"       --kind python:3.11 \\")
        print(f"       --memory 512 \\")
        print(f"       --timeout 300000 \\")
        print(f"       {OUTPUT_ZIP.name} \\")
        print(f"       --main main")
        print("\nSee IBM_CLOUD_SETUP.md for detailed instructions.")


def install_dependencies(build_dir: Path) -> None:
    """Install Python dependencies into build directory."""
    requirements = ROOT / "requirements-ibm.txt"
    
    if not requirements.exists():
        print(f"⚠️  {requirements.name} not found, creating from requirements.txt...")
        create_ibm_requirements()
    
    print(f"   Installing from {requirements.name}...")
    
    # Install packages directly into build directory
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(build_dir),
            "--requirement",
            str(requirements),
            "--upgrade",
            "--no-cache-dir",
        ],
        check=True,
        capture_output=True,
    )
    
    print("   ✓ Dependencies installed")


def create_ibm_requirements() -> None:
    """Create requirements-ibm.txt from requirements.txt with IBM Cloud specific packages."""
    base_requirements = ROOT / "requirements.txt"
    ibm_requirements = ROOT / "requirements-ibm.txt"
    
    # Read base requirements
    if base_requirements.exists():
        content = base_requirements.read_text()
    else:
        content = ""
    
    # Add IBM Cloud specific packages
    ibm_packages = [
        "# IBM Cloud specific packages",
        "ibm-cos-sdk>=2.13.0",
        "sendgrid>=6.11.0",
        "",
        "# Base requirements",
    ]
    
    final_content = "\n".join(ibm_packages) + "\n" + content
    
    # Remove AWS-specific packages
    lines = final_content.split("\n")
    filtered_lines = [
        line for line in lines 
        if not any(pkg in line.lower() for pkg in ["boto3", "botocore"])
    ]
    
    ibm_requirements.write_text("\n".join(filtered_lines))
    print(f"   ✓ Created {ibm_requirements.name}")


def copy_source(build_dir: Path) -> None:
    """Copy source code to build directory."""
    dest = build_dir / "src"
    
    # Copy entire src directory
    shutil.copytree(SRC, dest, dirs_exist_ok=True)
    
    # Remove __pycache__ and .pyc files
    for pycache in dest.rglob("__pycache__"):
        shutil.rmtree(pycache)
    for pyc in dest.rglob("*.pyc"):
        pyc.unlink()
    
    print(f"   ✓ Copied source code to {dest.relative_to(build_dir)}")


def copy_config(build_dir: Path) -> None:
    """Copy configuration files to build directory."""
    config_dir = ROOT / "config"
    grounding_dir = ROOT / "grounding"
    
    if config_dir.exists():
        dest = build_dir / "config"
        shutil.copytree(config_dir, dest, dirs_exist_ok=True)
        print(f"   ✓ Copied config/ directory")
    
    if grounding_dir.exists():
        dest = build_dir / "grounding"
        shutil.copytree(grounding_dir, dest, dirs_exist_ok=True)
        print(f"   ✓ Copied grounding/ directory")


def create_entry_point(build_dir: Path) -> None:
    """Create __main__.py entry point for IBM Cloud Functions."""
    entry_point = build_dir / "__main__.py"
    
    content = '''"""IBM Cloud Functions entry point.

This module serves as the entry point for the IBM Cloud Function.
IBM Cloud Functions expects a 'main' function at the root level.
"""
from src.ibm_cloud_handler import main

# IBM Cloud Functions will call this main function
# The function signature must be: main(params: dict) -> dict
'''
    
    entry_point.write_text(content)
    print(f"   ✓ Created {entry_point.name}")


if __name__ == "__main__":
    main()

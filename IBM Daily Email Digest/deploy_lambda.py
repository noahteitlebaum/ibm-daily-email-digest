"""AWS Lambda deployment packager for IBM Daily Email Digest.

This script creates a deployment package (ZIP file) ready for AWS Lambda upload.
It includes all dependencies and source code, excluding Windows-specific packages.

Usage:
    python deploy_lambda.py

Output:
    lambda_deployment.zip - Ready to upload to AWS Lambda

Requirements:
    - Python 3.11+ installed
    - pip available
    - Sufficient disk space for dependencies (~50MB)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# Project root
ROOT = Path(__file__).parent
PACKAGE_DIR = ROOT / "lambda_package"
ZIP_FILE = ROOT / "lambda_deployment.zip"

# Directories to include in deployment
INCLUDE_DIRS = ["src", "config", "grounding"]

# Files to include in deployment root
INCLUDE_FILES = [
    "requirements-lambda.txt",
    ".env.example"  # As reference, actual .env goes in Lambda env vars
]

# Patterns to exclude
EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".pytest_cache",
    "*.egg-info",
    ".git",
    ".venv",
    "venv",
    "output",  # Don't include local output files
    "tests",   # Don't include tests in deployment
]


def clean_package_dir():
    """Remove existing package directory."""
    if PACKAGE_DIR.exists():
        print(f"Cleaning existing package directory: {PACKAGE_DIR}")
        shutil.rmtree(PACKAGE_DIR)
    PACKAGE_DIR.mkdir(parents=True)


def install_dependencies():
    """Install Python dependencies to package directory."""
    print("\nInstalling dependencies from requirements-lambda.txt...")
    
    requirements_file = ROOT / "requirements-lambda.txt"
    if not requirements_file.exists():
        raise FileNotFoundError(
            f"requirements-lambda.txt not found at {requirements_file}"
        )
    
    # Install to package directory
    cmd = [
        sys.executable, "-m", "pip", "install",
        "-r", str(requirements_file),
        "-t", str(PACKAGE_DIR),
        "--upgrade"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error installing dependencies:\n{result.stderr}")
        raise RuntimeError("Failed to install dependencies")
    
    print("Dependencies installed successfully")


def copy_source_code():
    """Copy source code and configuration to package directory."""
    print("\nCopying source code and configuration...")
    
    for dir_name in INCLUDE_DIRS:
        src_dir = ROOT / dir_name
        if not src_dir.exists():
            print(f"Warning: {dir_name} directory not found, skipping")
            continue
        
        dst_dir = PACKAGE_DIR / dir_name
        print(f"  Copying {dir_name}/")
        shutil.copytree(
            src_dir, dst_dir,
            ignore=shutil.ignore_patterns(*EXCLUDE_PATTERNS)
        )
    
    for file_name in INCLUDE_FILES:
        src_file = ROOT / file_name
        if not src_file.exists():
            print(f"Warning: {file_name} not found, skipping")
            continue
        
        dst_file = PACKAGE_DIR / file_name
        print(f"  Copying {file_name}")
        shutil.copy2(src_file, dst_file)


def patch_imports():
    """Patch main.py to use cloud-compatible modules."""
    print("\nPatching imports for cloud deployment...")
    
    main_file = PACKAGE_DIR / "src" / "main.py"
    if not main_file.exists():
        raise FileNotFoundError(f"main.py not found at {main_file}")
    
    content = main_file.read_text(encoding="utf-8")
    
    # Replace state import with state_s3
    content = content.replace(
        "from . import config, digest as digest_mod, feeds, filter as filt, state",
        "from . import config, digest as digest_mod, feeds, filter as filt, state_s3 as state"
    )
    
    # Replace emailer import with emailer_ses (not emailer_cloud)
    content = content.replace(
        "from .emailer import send_digest",
        "from .emailer_ses import send_digest"
    )
    
    main_file.write_text(content, encoding="utf-8")
    print("  Patched src/main.py for cloud compatibility")


def create_zip():
    """Create deployment ZIP file."""
    print(f"\nCreating deployment package: {ZIP_FILE}")
    
    if ZIP_FILE.exists():
        ZIP_FILE.unlink()
    
    with zipfile.ZipFile(ZIP_FILE, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PACKAGE_DIR):
            # Filter out excluded patterns
            dirs[:] = [d for d in dirs if not any(
                d == pattern.rstrip("*") for pattern in EXCLUDE_PATTERNS
            )]
            
            for file in files:
                if any(file.endswith(ext) for ext in [".pyc", ".pyo", ".pyd"]):
                    continue
                
                file_path = Path(root) / file
                arcname = file_path.relative_to(PACKAGE_DIR)
                zf.write(file_path, arcname)
    
    size_mb = ZIP_FILE.stat().st_size / (1024 * 1024)
    print(f"  Package created: {size_mb:.2f} MB")


def cleanup():
    """Remove temporary package directory."""
    print("\nCleaning up temporary files...")
    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    print("  Cleanup complete")


def main():
    """Main deployment packaging workflow."""
    print("=" * 60)
    print("AWS Lambda Deployment Packager")
    print("IBM Daily Email Digest")
    print("=" * 60)
    
    try:
        clean_package_dir()
        install_dependencies()
        copy_source_code()
        patch_imports()
        create_zip()
        cleanup()
        
        print("\n" + "=" * 60)
        print("✓ Deployment package created successfully!")
        print("=" * 60)
        print(f"\nPackage: {ZIP_FILE}")
        print(f"Size: {ZIP_FILE.stat().st_size / (1024 * 1024):.2f} MB")
        print("\nNext steps:")
        print("1. Upload lambda_deployment.zip to AWS Lambda")
        print("2. Set handler to: src.lambda_handler.lambda_handler")
        print("3. Configure environment variables (see AWS_SETUP.md)")
        print("4. Set up EventBridge hourly trigger")
        print("5. Test with a manual invocation")
        
        return 0
        
    except Exception as exc:
        print(f"\n✗ Deployment packaging failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

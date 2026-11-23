"""
Unit tests verifying Story 8: 3-Environment CI/CD Pipelines & Branch Protection documentation.
"""
import os


WORKFLOWS_DIR = os.path.join(".github", "workflows")
CI_QA_PATH = os.path.join(WORKFLOWS_DIR, "ci-qa.yaml")
DEPLOY_PRE_PATH = os.path.join(WORKFLOWS_DIR, "deploy-pre.yaml")
SEED_PRE_PATH = os.path.join(WORKFLOWS_DIR, "seed-pre.yaml")
DEPLOY_PROD_PATH = os.path.join(WORKFLOWS_DIR, "deploy-prod.yaml")
README_PATH = "README.md"


def _read_file(path: str) -> str:
    """Read and return the UTF-8 contents of a repository file after asserting it exists."""
    assert os.path.exists(path), f"Expected file {path} to exist"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# .github/workflows/ci-qa.yaml (DEV/QA)
# ---------------------------------------------------------------------------

def test_ci_qa_workflow_exists_and_triggers_on_pr_to_pre_and_main():
    """Verify ci-qa.yaml triggers on PRs to pre and main and declares read-only permissions."""
    content = _read_file(CI_QA_PATH)
    assert "pull_request" in content
    assert "pre" in content
    assert "main" in content
    assert "permissions:" in content
    assert "contents: read" in content


def test_ci_qa_workflow_runs_pytest_wiremock_and_frontend_build():
    """Verify ci-qa.yaml runs pytest, WireMock OAuth check, and frontend build."""
    content = _read_file(CI_QA_PATH)
    assert "pytest tests/ -v" in content
    assert "wiremock" in content.lower()
    assert "8089" in content
    assert "/api/oauth/token" in content or "exchange_code_for_token" in content
    assert "npm run build" in content


# ---------------------------------------------------------------------------
# .github/workflows/deploy-pre.yaml (PRE)
# ---------------------------------------------------------------------------

def test_deploy_pre_workflow_triggers_and_tests_before_deploy():
    """Verify deploy-pre.yaml triggers on push to pre, sets read-only permissions, and runs pytest."""
    content = _read_file(DEPLOY_PRE_PATH)
    assert "push:" in content
    assert "pre" in content
    assert "permissions:" in content
    assert "contents: read" in content
    assert "pytest tests/ -v" in content


def test_deploy_pre_workflow_clean_zip_and_lambda_target():
    """Verify deploy-pre.yaml packages a zero-dependency zip and waits for ClubCounterAPI-PRE update."""
    content = _read_file(DEPLOY_PRE_PATH)
    assert "cd api" in content
    assert "zip -r ../function.zip ." in content
    assert "*.env*" in content
    assert "*__pycache__*" in content
    assert "ClubCounterAPI-PRE" in content
    assert "function-updated-v2" in content
    assert "eu-north-1" in content
    # Must not pip install into api/ package directory
    assert "pip install -t" not in content
    assert "--target" not in content


# ---------------------------------------------------------------------------
# .github/workflows/seed-pre.yaml (PRE Demo Data Seeder)
# ---------------------------------------------------------------------------

def test_seed_pre_workflow_triggers_on_pre_merge_and_seeds_pre():
    """Verify seed-pre.yaml runs on every push/merge to pre and seeds PRE demo data."""
    content = _read_file(SEED_PRE_PATH)
    assert "push:" in content
    assert "- pre" in content
    assert "paths:" not in content
    assert "workflow_dispatch:" in content
    assert "permissions:" in content
    assert "contents: read" in content
    assert "environment: pre" in content
    assert "eu-north-1" in content
    assert "python scripts/seed_demo_data.py --env pre" in content


# ---------------------------------------------------------------------------
# .github/workflows/deploy-prod.yaml (PROD)
# ---------------------------------------------------------------------------

def test_deploy_prod_workflow_triggers_and_tests_before_deploy():
    """Verify deploy-prod.yaml triggers on push to main, sets read-only permissions, and runs pytest."""
    content = _read_file(DEPLOY_PROD_PATH)
    assert "push:" in content
    assert "main" in content
    assert "permissions:" in content
    assert "contents: read" in content
    assert "pytest tests/ -v" in content


def test_deploy_prod_workflow_clean_zip_and_lambda_target():
    """Verify deploy-prod.yaml packages a zero-dependency zip and waits for ClubCounterAPI-PROD update."""
    content = _read_file(DEPLOY_PROD_PATH)
    assert "cd api" in content
    assert "zip -r ../function.zip ." in content
    assert "*.env*" in content
    assert "*__pycache__*" in content
    assert "ClubCounterAPI-PROD" in content
    assert "function-updated-v2" in content
    assert "eu-north-1" in content
    assert "pip install -t" not in content
    assert "--target" not in content


# ---------------------------------------------------------------------------
# README.md Documentation
# ---------------------------------------------------------------------------

def test_readme_documents_branch_protection_vercel_aws_and_demo_playbook():
    """Verify README.md documents branch protection, Vercel env vars, AWS provisioning, and demo scripts."""
    content = _read_file(README_PATH)
    # Branch protection & CI status check
    assert "main" in content
    assert "ci-qa" in content
    assert "branch protection" in content.lower() or "protected" in content.lower()

    # Vercel PRE vs PROD setup (signing secret must be server-side API_SIGNING_SECRET, not VITE_API_SIGNING_SECRET)
    assert "Vercel" in content
    assert "PRE" in content
    assert "PROD" in content
    assert "API_SIGNING_SECRET" in content
    assert "VITE_API_SIGNING_SECRET" not in content

    # AWS DynamoDB & Lambda provisioning in eu-north-1
    for resource in (
        "ATHLETES_PRE",
        "ACTIVITIES_PRE",
        "ATHLETES_PROD",
        "ACTIVITIES_PROD",
        "ClubCounterAPI-PRE",
        "ClubCounterAPI-PROD",
        "eu-north-1",
    ):
        assert resource in content, f"README.md missing documentation for {resource}"

    # Demo playbook scripts
    assert "seed_demo_data.py" in content
    assert "simulate_webhook.py" in content


def test_ci_qa_workflow_runs_gitleaks_secret_scan():
    """Verify ci-qa.yaml fetches full history and runs pinned Gitleaks CLI scans."""
    content = _read_file(CI_QA_PATH)
    assert "fetch-depth: 0" in content
    assert "gitleaks" in content.lower()
    assert "sha256sum -c" in content
    assert "gitleaks dir . --redact --exit-code 1" in content
    assert "gitleaks git --log-opts=" in content


def test_repo_secret_hygiene():
    """Verify tracked Bruno/env files contain no committed credentials or live secret values."""
    assert not os.path.exists(os.path.join("bruno", "Intervals post act.bru"))
    assert not os.path.exists(os.path.join("frontend", ".env.development"))
    assert not os.path.exists(os.path.join("frontend", ".env.production"))

    pre_bru = _read_file(os.path.join("bruno", "environments", "PRE.bru"))
    assert "vars:secret" in pre_bru
    assert "webhookSecret" in pre_bru
    assert "apiKey" in pre_bru
    assert "https://<pre-lambda-url>.lambda-url.eu-north-1.on.aws" in pre_bru

    env_example = _read_file(os.path.join("frontend", ".env.example"))
    for key in ("API_KEY", "API_SIGNING_SECRET"):
        lines = [ln.strip() for ln in env_example.splitlines() if ln.strip().startswith(f"{key}=")]
        assert lines == [f"{key}="], f"Expected {key}= to have an empty placeholder in .env.example"

    gitignore = _read_file(".gitignore")
    assert ".env.*" in gitignore
    assert "!.env.example" in gitignore

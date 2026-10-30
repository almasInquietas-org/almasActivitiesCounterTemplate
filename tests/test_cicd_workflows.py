"""
Unit tests verifying Story 8: 3-Environment CI/CD Pipelines & Branch Protection documentation.
"""
import os


WORKFLOWS_DIR = os.path.join(".github", "workflows")
CI_QA_PATH = os.path.join(WORKFLOWS_DIR, "ci-qa.yaml")
DEPLOY_PRE_PATH = os.path.join(WORKFLOWS_DIR, "deploy-pre.yaml")
DEPLOY_PROD_PATH = os.path.join(WORKFLOWS_DIR, "deploy-prod.yaml")
README_PATH = "README.md"


def _read_file(path: str) -> str:
    assert os.path.exists(path), f"Expected file {path} to exist"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# AC 1: .github/workflows/ci-qa.yaml (DEV/QA)
# ---------------------------------------------------------------------------

def test_ci_qa_workflow_exists_and_triggers_on_pr_to_pre_and_master():
    content = _read_file(CI_QA_PATH)
    assert "pull_request" in content
    assert "pre" in content
    assert "master" in content


def test_ci_qa_workflow_runs_pytest_wiremock_and_frontend_build():
    content = _read_file(CI_QA_PATH)
    assert "pytest tests/ -v" in content
    assert "wiremock" in content.lower()
    assert "8089" in content
    assert "/api/oauth/token" in content or "exchange_code_for_token" in content
    assert "npm run build" in content


# ---------------------------------------------------------------------------
# AC 2: .github/workflows/deploy-pre.yaml (PRE)
# ---------------------------------------------------------------------------

def test_deploy_pre_workflow_triggers_and_tests_before_deploy():
    content = _read_file(DEPLOY_PRE_PATH)
    assert "push:" in content
    assert "pre" in content
    assert "pytest tests/ -v" in content


def test_deploy_pre_workflow_clean_zip_and_lambda_target():
    content = _read_file(DEPLOY_PRE_PATH)
    assert "cd api" in content
    assert "zip -r ../function.zip ." in content
    assert "*.env*" in content
    assert "*__pycache__*" in content
    assert "ClubCounterAPI-PRE" in content
    assert "eu-west-1" in content
    # Must not pip install into api/ package directory
    assert "pip install -t" not in content
    assert "--target" not in content


# ---------------------------------------------------------------------------
# AC 3: .github/workflows/deploy-prod.yaml (PROD)
# ---------------------------------------------------------------------------

def test_deploy_prod_workflow_triggers_and_tests_before_deploy():
    content = _read_file(DEPLOY_PROD_PATH)
    assert "push:" in content
    assert "master" in content
    assert "pytest tests/ -v" in content


def test_deploy_prod_workflow_clean_zip_and_lambda_target():
    content = _read_file(DEPLOY_PROD_PATH)
    assert "cd api" in content
    assert "zip -r ../function.zip ." in content
    assert "*.env*" in content
    assert "*__pycache__*" in content
    assert "ClubCounterAPI-PROD" in content
    assert "eu-west-1" in content
    assert "pip install -t" not in content
    assert "--target" not in content


# ---------------------------------------------------------------------------
# AC 4: README.md Documentation
# ---------------------------------------------------------------------------

def test_readme_documents_branch_protection_vercel_aws_and_demo_playbook():
    content = _read_file(README_PATH)
    # Branch protection & CI status check
    assert "master" in content
    assert "ci-qa" in content
    assert "branch protection" in content.lower() or "protected" in content.lower()

    # Vercel PRE vs PROD setup
    assert "Vercel" in content
    assert "PRE" in content
    assert "PROD" in content

    # AWS DynamoDB & Lambda provisioning in eu-west-1
    for resource in (
        "ATHLETES_PRE",
        "ACTIVITIES_PRE",
        "ATHLETES_PROD",
        "ACTIVITIES_PROD",
        "ClubCounterAPI-PRE",
        "ClubCounterAPI-PROD",
        "eu-west-1",
    ):
        assert resource in content, f"README.md missing documentation for {resource}"

    # Demo playbook scripts
    assert "seed_demo_data.py" in content
    assert "simulate_webhook.py" in content


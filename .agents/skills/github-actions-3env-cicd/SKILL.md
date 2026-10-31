---
name: github-actions-3env-cicd
description: >-
  Configures the 3-environment GitHub Actions CI/CD pipelines (ci-qa.yaml for PRs,
  deploy-pre.yaml for PRE, deploy-prod.yaml for protected main) and zero-dependency
  AWS Lambda zip packaging. Use when working on Story 8 or .github/workflows/.
---

# 3-Environment GitHub Actions CI/CD Skill

## 1. Pipeline Overview

| Workflow File | Trigger | Target Environment | Actions Performed |
|---|---|---|---|
| `.github/workflows/ci-qa.yaml` | `pull_request` to `pre` or `main` | `DEV / QA` | Runs `pytest tests/ -v` + WireMock service container integration check + frontend `npm run build` |
| `.github/workflows/deploy-pre.yaml` | `push` to `pre` branch (`api/**` changes) | `PRE` (`ClubCounterAPI-PRE`) | Runs `pytest`, zips `api/` (excluding `.env*` & `__pycache__`), deploys to `ClubCounterAPI-PRE` (`eu-north-1`) |
| `.github/workflows/deploy-prod.yaml` | `push` to `main` branch (`api/**` changes) | `PROD` (`ClubCounterAPI-PROD`) | Runs `pytest`, zips `api/` (excluding `.env*` & `__pycache__`), deploys to `ClubCounterAPI-PROD` (`eu-north-1`) |

## 2. Lambda Packaging Rules (`deploy-pre.yaml` & `deploy-prod.yaml`)
1. **Always Run Tests Before Deploy:** Every deployment workflow must include a `test` job (or step) running `pytest tests/ -v` before packaging and uploading to AWS Lambda.
2. **Clean Zip Packaging:**
   - Package from inside `api/` so `backend_source.py` is at the root of `function.zip`:
     ```bash
     cd api
     zip -r ../function.zip . -x "*.env*" -x "*__pycache__*" -x "*.pyc"
     ```
   - Never include `.env` files in `function.zip`. All Lambda environment variables are managed in the AWS Lambda configuration.
3. **Zero Pip Install in Lambda Package:**
   - Because `api/` uses only Python 3.12 standard library + Lambda's built-in `boto3`, do **not** `pip install` third-party libraries into `api/` during packaging. Keep the zip tiny (<50 KB) for instant cold starts.

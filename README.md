# Almas Activities Counter (Intervals.icu Edition)

Real-time multi-club activity counter and leaderboard powered by **Intervals.icu OAuth 2.0 & Webhooks**, **AWS Lambda (Python 3.12)**, **Amazon DynamoDB**, and a **React + Vite** dashboard deployed on **Vercel**.

---

## 1. 3-Environment Architecture (`DEV/QA`, `PRE`, `PROD`)

All cloud resources reside in **`eu-west-1` (Ireland)** using environment suffixes (`_PRE`, `_PROD`).

| Dimension | `DEV / QA` | `PRE` (Pre-Production / Client Demo) | `PROD` (Production) |
|---|---|---|---|
| **Git Branch** | `feature/*` & Pull Requests | `pre` | `main` (Protected) |
| **GitHub Workflow** | `.github/workflows/ci-qa.yaml` | `.github/workflows/deploy-pre.yaml` | `.github/workflows/deploy-prod.yaml` |
| **Backend Compute** | Local Flask (`:5000`) & CI Runner | AWS Lambda `ClubCounterAPI-PRE` | AWS Lambda `ClubCounterAPI-PROD` |
| **DynamoDB Tables** | `ATHLETES_DEV`, `ACTIVITIES_DEV` (`moto`) | `ATHLETES_PRE`, `ACTIVITIES_PRE` | `ATHLETES_PROD`, `ACTIVITIES_PROD` |
| **Intervals OAuth URL** | Local WireMock (`http://localhost:8089`) | WireMock Cloud (`https://<id>.wiremockapi.cloud`) | Real Intervals.icu (`https://intervals.icu`) |
| **Frontend Hosting** | Vite Dev (`http://localhost:5173`) | Vercel Preview (`pre` branch) | Vercel Production (`main` branch) |

---

## 2. AWS Provisioning (`eu-west-1`)

### 2.1 DynamoDB Tables
Provision 4 tables in `eu-west-1` (On-Demand / `PAY_PER_REQUEST` billing):

```bash
# PRE Environment Tables
aws dynamodb create-table \
  --table-name ATHLETES_PRE \
  --attribute-definitions AttributeName=athlete_id,AttributeType=S \
  --key-schema AttributeName=athlete_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-west-1

aws dynamodb create-table \
  --table-name ACTIVITIES_PRE \
  --attribute-definitions AttributeName=activity_id,AttributeType=S \
  --key-schema AttributeName=activity_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-west-1

# PROD Environment Tables
aws dynamodb create-table \
  --table-name ATHLETES_PROD \
  --attribute-definitions AttributeName=athlete_id,AttributeType=S \
  --key-schema AttributeName=athlete_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-west-1

aws dynamodb create-table \
  --table-name ACTIVITIES_PROD \
  --attribute-definitions AttributeName=activity_id,AttributeType=S \
  --key-schema AttributeName=activity_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-west-1
```

### 2.2 AWS Lambda Functions (`ClubCounterAPI-PRE` & `ClubCounterAPI-PROD`)
- **Runtime:** Python 3.12 (`backend_source.process_activities` handler)
- **Packaging:** Zero third-party dependencies (uses Python stdlib + built-in `boto3`), zipped from `api/` excluding `.env*` and `__pycache__`.
- **Environment Variables:**

| Variable | `ClubCounterAPI-PRE` (`PRE`) | `ClubCounterAPI-PROD` (`PROD`) |
|---|---|---|
| `AWS_REGION` | `eu-west-1` | `eu-west-1` |
| `ATHLETES_TABLE_NAME` | `ATHLETES_PRE` | `ATHLETES_PROD` |
| `ACTIVITIES_TABLE_NAME` | `ACTIVITIES_PRE` | `ACTIVITIES_PROD` |
| `INTERVALS_OAUTH_BASE_URL` | `https://<mock>.wiremockapi.cloud` | `https://intervals.icu` |
| `INTERVALS_CLIENT_ID` | `pre-demo-client-id` | `<real-client-id>` |
| `INTERVALS_CLIENT_SECRET` | `pre-demo-secret` | `<real-client-secret>` |
| `INTERVALS_WEBHOOK_SECRET` | `pre-webhook-secret` | `<real-webhook-secret>` |
| `GOAL_KM` | `5000` | `<club-goal>` |
| `LAST_ACT` | `10` | `10` |
| `TITLE` | `Almas Rides the Wave (Demo)` | `<club-challenge-title>` |
| `CHECKPOINTS` | `1000,2500,4000` | `<comma-separated-checkpoints>` |
| `CORS_ALLOWED_ORIGINS` | `https://pre-almasactivitiescounter.vercel.app` | `https://almasactivitiescounter.vercel.app` |

---

## 3. Branch Protection & GitHub Actions Setup

### 3.1 GitHub Branch Protection Rules
Configure branch protection in **Settings → Branches** on GitHub:
1. **Protected Branch: `main`**
   - Enable **Require a pull request before merging**.
   - Enable **Require status checks to pass before merging** and select the required status check **`ci-qa`** (from `.github/workflows/ci-qa.yaml`).
   - Enable **Do not allow bypassing the above settings** to prevent direct pushes to `main`.
2. **Pre-Production Branch: `pre`**
   - Pull requests targeting `pre` also trigger `ci-qa`. Merging into `pre` triggers `.github/workflows/deploy-pre.yaml` to update `ClubCounterAPI-PRE` when `api/**` or `.github/workflows/deploy-pre.yaml` changes (or via manual `workflow_dispatch`); frontend-, documentation-, or test-only changes do not deploy `ClubCounterAPI-PRE`.

### 3.2 GitHub Actions Secrets
Add the following repository/environment secrets in **Settings → Secrets and variables → Actions**:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

---

## 4. Vercel Environment Setup (`PRE` vs `PROD`)

Connect the repository to **Vercel** with Root Directory set to `frontend`:

| Setting / Env Var | Vercel Preview (`pre` branch -> `PRE`) | Vercel Production (`main` branch -> `PROD`) |
|---|---|---|
| **Git Branch** | `pre` | `main` |
| `VITE_API_URL` | `https://<pre-lambda-url>.lambda-url.eu-west-1.on.aws` | `https://<prod-lambda-url>.lambda-url.eu-west-1.on.aws` |
| `VITE_API_KEY` | `<pre-api-key>` (or empty for passthrough) | `<prod-api-key>` |
| `API_SIGNING_SECRET` *(Server-only)* | `<pre-signing-secret>` (used by `/api/token`; never expose via `VITE_*`) | `<prod-signing-secret>` (used by `/api/token`; never expose via `VITE_*`) |

---

## 5. Local Development & Client Demo Playbook

### 5.1 Local Development & Testing (`DEV / QA`)
```bash
# Run full unit & Moto test suite
pytest tests/ -v

# Start local WireMock on http://localhost:8089
docker compose -f mocks/docker-compose.yml up -d
```

### 5.2 Client Demo Playbook (`PRE`)
Before a client meeting, reset and seed `PRE` with 12 realistic club athletes and 50 varied workouts (`Run`, `Ride`, `Swim`, `Hike`):

```bash
python scripts/seed_demo_data.py --env pre --reset
```

During the live call:
1. **Show Club Onboarding (`GET /oauth/callback`):** Click the `PRE` registration link (`.../oauth/authorize?...&state=almas_inquietas`) backed by WireMock to display the styled registration confirmation page.
2. **Simulate a Real-Time Workout Upload (`POST /webhook`):**
   ```bash
   python scripts/simulate_webhook.py --env pre --athlete "Laura M." --km 15.4 --type Run
   ```
   Refresh or observe the `PRE` dashboard as total kilometers, recent activities, and leaderboard rankings update immediately.

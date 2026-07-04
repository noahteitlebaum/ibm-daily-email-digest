# IBM Cloud Deployment — Daily Digest (once per day, no computer required)

Single source of truth for running the IBM Daily Email Digest on IBM Cloud so it
sends **once a day automatically**, with no local machine and no Outlook.

This guide is hardcoded for the setup already in progress:
- Region: **ca-tor**
- Registry: **ca.icr.io**
- Namespace: **noah-ibm-digest**
- Image: **ca.icr.io/noah-ibm-digest/ibm-daily-digest:latest**

Follow the steps in order. Every command is copy-paste. Replace only the
`<LIKE_THIS>` values.

---

## 0. What gets built

```
IBM Code Engine (daily cron subscription)
        |  triggers the job once a day
        v
IBM Code Engine job  ->  runs the container:  python -m src.main --no-decks
        |  fetch Google News RSS -> filter -> ICA summarize -> render HTML email
        v
SendGrid HTTPS API  ------------------>  recipients (EMAIL_TO)
```

- Compute + schedule: Code Engine job + cron subscription (IBM Cloud equivalent
  of AWS Lambda + EventBridge).
- Email: SendGrid API. IBM Cloud has no native email service.
- Decks: disabled in the cloud (`--no-decks`) to keep the image small.

---

## 1. Two hard gates — check these FIRST

### Gate A: Is the ICA endpoint reachable from outside IBM's network?
```powershell
curl.exe -I https://api.nextgen-beta.ica.ibm.com/ica/v1/chat-models/chat/completions
```
- Any HTTP response (even 401 or 405) = reachable. Proceed.
- Timeout or "could not resolve host" = NOT reachable publicly. Stop; the cloud
  path is not viable until IBM exposes it or a proxy is arranged.

### Gate B: What sender address is allowed?
SendGrid only sends from a verified sender.
- Personal or team-owned address/domain: works, do it now.
- `@ibm.com`: requires IBM IT to publish SPF/DKIM DNS records. Not solvable here.
  Use a verified non-IBM sender to prove the pipeline.

---

## 2. Prerequisites (install once)

### 2.1 Docker Desktop
- https://www.docker.com/products/docker-desktop/ — install, launch, wait until it says running.

### 2.2 IBM Cloud CLI (PowerShell as Administrator, once)
```powershell
iex (New-Object Net.WebClient).DownloadString('https://clis.cloud.ibm.com/install/powershell')
```
Reopen PowerShell, then:
```powershell
ibmcloud version
```

### 2.3 CLI plugins
```powershell
ibmcloud plugin install code-engine
ibmcloud plugin install container-registry
```

### 2.4 SendGrid account
- https://signup.sendgrid.com/ (free tier ~100 emails/day).

---

## 3. SendGrid setup (get EMAIL_FROM + SENDGRID_API_KEY)

### 3.1 Verify a sender
- SendGrid -> Settings -> Sender Authentication -> Single Sender Verification -> Create New Sender.
- Use the address to send FROM, save, open that inbox, click the verification link.
- That verified address is your `EMAIL_FROM`.

### 3.2 Create an API key
- SendGrid -> Settings -> API Keys -> Create API Key.
- Name `ibm-digest`, Restricted Access, enable "Mail Send" only.
- Create and COPY THE KEY NOW (shown once). This is your `SENDGRID_API_KEY`.

---

## 4. Log in and target ca-tor
```powershell
ibmcloud login --sso
ibmcloud target -g Default
ibmcloud target -r ca-tor
```

---

## 5. Build and push the container image (ca.icr.io)

From the project root (the folder with the `Dockerfile`):

```powershell
cd "C:\Users\NoahTeitlebaum\Internships\IBM\Coding\IBM Daily Email Digest"

# 5.1 Point Container Registry at ca-tor and create the namespace
ibmcloud cr region-set ca-tor
ibmcloud cr namespace-add noah-ibm-digest          # skip if it already exists

# 5.2 Let Docker push to IBM Container Registry
ibmcloud cr login

# 5.3 Build the image (ca.icr.io tag; the trailing dot matters)
docker build -t ca.icr.io/noah-ibm-digest/ibm-daily-digest:latest .

# 5.4 Push it
docker push ca.icr.io/noah-ibm-digest/ibm-daily-digest:latest
```

If an image was already built with the wrong `us.icr.io` tag, retag it (no rebuild):
```powershell
docker tag us.icr.io/noah-ibm-digest/ibm-daily-digest:latest ca.icr.io/noah-ibm-digest/ibm-daily-digest:latest
docker push ca.icr.io/noah-ibm-digest/ibm-daily-digest:latest
```

Verify:
```powershell
ibmcloud cr images
```
Expect a row for `ca.icr.io/noah-ibm-digest/ibm-daily-digest` tag `latest`.

---

## 6. Create an IBM Cloud API key (so Code Engine can pull the image)
```powershell
ibmcloud iam api-key-create digest-registry-key --file digest-key.json
```
Open `digest-key.json`, copy the `"apikey"` value = `<IBMCLOUD_APIKEY>` below.
Delete this file after step 8.

---

## 7. Create the Code Engine project
```powershell
ibmcloud ce project create --name ibm-daily-digest
ibmcloud ce project select --name ibm-daily-digest
```

---

## 8. Create the two secrets

### 8.1 Registry-pull secret (lets the job pull from ca.icr.io)
```powershell
ibmcloud ce registry create --name icr-pull `
  --server ca.icr.io `
  --username iamapikey `
  --password <IBMCLOUD_APIKEY>
```

### 8.2 App secret (private keys)
```powershell
ibmcloud ce secret create --name digest-secrets `
  --from-literal ICA_API_KEY="<YOUR_ICA_API_KEY>" `
  --from-literal SENDGRID_API_KEY="<YOUR_SENDGRID_API_KEY>"
```
Now delete `digest-key.json`.

---

## 9. Create the job
```powershell
ibmcloud ce job create --name digest-job `
  --image ca.icr.io/noah-ibm-digest/ibm-daily-digest:latest `
  --registry-secret icr-pull `
  --cpu 0.5 --memory 1G `
  --env EMAIL_METHOD=sendgrid `
  --env ICA_CHAT_URL="https://api.nextgen-beta.ica.ibm.com/ica/v1/chat-models/chat/completions" `
  --env ICA_MODEL="claude-haiku-4-5" `
  --env ICA_AUTH_SCHEME="Bearer" `
  --env EMAIL_FROM="<YOUR_VERIFIED_SENDER>" `
  --env EMAIL_TO="<RECIPIENT1>,<RECIPIENT2>" `
  --env-from-secret digest-secrets
```

Env var reference (what the code reads):

| Variable | Set to | Used by |
|----------|--------|---------|
| `EMAIL_METHOD` | `sendgrid` | picks the SendGrid sender |
| `SENDGRID_API_KEY` | SendGrid key (in secret) | SendGrid auth |
| `EMAIL_FROM` | verified sender | From address |
| `EMAIL_TO` | comma-separated recipients | recipients |
| `ICA_API_KEY` | ICA key (in secret) | LLM auth |
| `ICA_CHAT_URL` | the chat-completions URL above | LLM endpoint |
| `ICA_MODEL` | `claude-haiku-4-5` | model |
| `ICA_AUTH_SCHEME` | `Bearer` | auth header style |

---

## 10. Test once, on demand, BEFORE trusting the schedule
```powershell
ibmcloud ce jobrun submit --job digest-job --name digest-test
ibmcloud ce jobrun logs --name digest-test --follow
```
Success = a log line ending in:
`-> SendGrid sent the digest to <recipient> (status 202)`
Then check the recipient inbox.

---

## 11. Schedule once per day

Code Engine cron is UTC. New Brunswick is Atlantic time:
- Summer (ADT, UTC-3): 9:00 AM local = `12:00` UTC.
- Winter (AST, UTC-4): 9:00 AM local = `13:00` UTC.

Weekdays at 9 AM Atlantic (summer example):
```powershell
ibmcloud ce sub cron create --name digest-daily `
  --destination digest-job --destination-type job `
  --schedule "0 12 * * 1-5"
```
- Every day: `"0 12 * * *"`. Fields: `minute hour day-of-month month day-of-week`.

Confirm:
```powershell
ibmcloud ce sub cron list
```

---

## 12. Redeploy after code changes
```powershell
cd "C:\Users\NoahTeitlebaum\Internships\IBM\Coding\IBM Daily Email Digest"
docker build -t ca.icr.io/noah-ibm-digest/ibm-daily-digest:latest .
docker push ca.icr.io/noah-ibm-digest/ibm-daily-digest:latest
ibmcloud ce job update --name digest-job --image ca.icr.io/noah-ibm-digest/ibm-daily-digest:latest
```
Change recipients or schedule:
```powershell
ibmcloud ce job update --name digest-job --env EMAIL_TO="<NEW_LIST>"
ibmcloud ce sub cron update --name digest-daily --schedule "0 13 * * 1-5"
```

---

## 13. Troubleshooting (symptom -> cause -> fix)

- `docker push ... Authorization required`
  -> The build tag domain does not match the `cr login` region. Use
     `ca.icr.io` in the tag (retag command in step 5).
- `SendGrid not configured - missing ...`
  -> Secret or env var missing. Re-check step 8.2 and the `--env` flags in step 9.
- SendGrid status `403`
  -> Sender not verified, or key lacks Mail Send. Redo step 3.
- Status `202` but nothing arrives
  -> Accepted by SendGrid; check spam and `EMAIL_TO`.
- Timeout to `api.nextgen-beta.ica.ibm.com`
  -> Gate A failed. ICA not reachable from Code Engine.
- `ImagePullBackOff`
  -> Registry-pull secret wrong. Redo step 8.1 with a valid `<IBMCLOUD_APIKEY>`
     and `--server ca.icr.io`.

Useful:
```powershell
ibmcloud ce jobrun list
ibmcloud ce jobrun logs --name <jobrun-name>
```

---

## 14. Known limitations
- Sender is not `@ibm.com` unless IBM IT publishes SPF/DKIM in SendGrid.
- "New since last run" does not persist in the cloud (`state.py` writes to the
  ephemeral container disk). Fine for a once-daily send; cross-run de-dup needs
  the seen-store moved to IBM Cloud Object Storage (`ibm-cos-sdk` already in
  `requirements-ibm.txt`; wiring is a future change).
- Decks are disabled in the cloud (`--no-decks`).

---

## 15. Cost
- Code Engine + Container Registry: free tier covers one small daily job.
- SendGrid: free tier ~100 emails/day.
- ICA/Claude tokens: a few cents per run.
- Total: well under a few dollars per month.

---

## 16. Cleanup — delete leftover files (run locally on Windows)
```powershell
cd "C:\Users\NoahTeitlebaum\Internships\IBM\Coding\IBM Daily Email Digest"
del AWS_SETUP.md, AWS_SES_SETUP.md, deploy_lambda.py, requirements-lambda.txt, lambda_deployment.zip
del IBM_CLOUD_SETUP.md, IBM_CODE_ENGINE_SETUP.md, deploy_ibm_cloud.py, ibm_cloud_deployment.zip
del LLM-Grounding-Client_News_to_IBM_Opportunity_Insights.md
del digest-key.json
```
Keep: `src/`, `config/`, `grounding/`, `Dockerfile`, `deploy_code_engine.py`,
`requirements.txt`, `requirements-ibm.txt`, `README.md`, this file, `.env`,
`.env.example`, `.gitignore`.
Optional: `scripts/` (local fallback), `ADVISOR_INSTRUCTIONS.md` (writing voice).
```

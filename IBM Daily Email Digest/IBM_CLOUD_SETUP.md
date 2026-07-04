# ⚠️ IBM Cloud Functions - DEPRECATED SERVICE

## IBM Daily Email Digest - Cloud Deployment Options

**IMPORTANT: IBM Cloud Functions has been fully deprecated and is no longer available in the IBM Cloud Console.**

---

## 🚀 Recommended Alternative: IBM Code Engine

IBM Code Engine is IBM's modern, fully-managed serverless platform that replaces Cloud Functions. It offers:
- ✅ Better performance and scalability
- ✅ More flexible deployment options (containers, source code, jobs)
- ✅ Built-in CI/CD integration
- ✅ Enhanced monitoring and logging
- ✅ Same free tier benefits

**This guide needs to be updated for Code Engine deployment.** In the meantime, you have these options:

---

## Deployment Options

### Option 1: AWS Lambda (Recommended - Already Documented)

Use the existing AWS Lambda deployment guide:
- See `AWS_SETUP.md` for complete instructions
- Uses AWS Lambda + S3 + SES
- Fully tested and documented
- Cost: ~$0.25/month (mostly free tier)

### Option 2: Local Windows Execution (Current Setup)

Continue running locally on your Windows machine:
- Use Windows Task Scheduler (see `scripts/setup_task_scheduler.ps1`)
- Runs hourly automatically
- No cloud costs
- Requires computer to be on

### Option 3: IBM Code Engine (Future - Requires Migration)

To migrate to IBM Code Engine, you'll need to:

1. **Install Code Engine CLI:**
   ```bash
   ibmcloud plugin install code-engine
   ```

2. **Create Code Engine project:**
   ```bash
   ibmcloud ce project create --name ibm-digest
   ```

3. **Adapt the deployment:**
   - Code Engine uses different deployment format than Cloud Functions
   - Requires containerization (Docker) or source-based deployment
   - Different environment variable configuration
   - Different scheduling mechanism (cron jobs vs triggers)

**Note:** A complete Code Engine deployment guide needs to be created. The current `deploy_ibm_cloud.py` and `ibm_cloud_handler.py` are designed for the deprecated Cloud Functions service and will not work with Code Engine without modifications.

---

## Why Was Cloud Functions Deprecated?

IBM has consolidated its serverless offerings:
- **Cloud Functions** (based on Apache OpenWhisk) → Deprecated
- **Code Engine** → Current serverless platform
- Better features, performance, and developer experience in Code Engine

---

## Next Steps

**For immediate deployment:**
1. Use AWS Lambda (see `AWS_SETUP.md`) - Recommended
2. Or continue with local Windows execution

**For IBM Cloud deployment:**
1. Wait for Code Engine migration guide to be created
2. Or contribute by creating a Code Engine deployment script

---

## Files That Need Updates

The following files are currently designed for the deprecated Cloud Functions:
- ❌ `deploy_ibm_cloud.py` - Creates Cloud Functions ZIP package
- ❌ `src/ibm_cloud_handler.py` - Cloud Functions entry point
- ❌ `requirements-ibm.txt` - Cloud Functions dependencies
- ❌ This guide (`IBM_CLOUD_SETUP.md`)

These need to be rewritten for Code Engine deployment.

---

## What Happened to the Original Guide?

The original step-by-step deployment guide for IBM Cloud Functions has been removed because the service is no longer available. The steps included:
- Creating deployment packages
- Setting up Cloud Object Storage
- Configuring SendGrid
- Installing CLI plugins (now unavailable)
- Creating functions and triggers (console no longer exists)

All of these instructions are now obsolete.

---

## For AWS Lambda Deployment

If you want serverless deployment, use AWS Lambda instead:

**See `AWS_SETUP.md` for complete AWS Lambda deployment instructions.**

The AWS setup includes:
- AWS Lambda for serverless compute
- Amazon S3 for state storage
- Amazon SES for email delivery
- CloudWatch Events for scheduling
- Complete step-by-step guide

---

## For IBM Code Engine (Future)

IBM Code Engine is the modern replacement for Cloud Functions. Key differences:

**Code Engine vs Cloud Functions:**
- Uses container-based deployment (Docker) or source code
- Different CLI: `ibmcloud ce` instead of `ibmcloud fn`
- Jobs instead of triggers for scheduled tasks
- More flexible scaling and configuration
- Better integration with IBM Cloud services

**To get started with Code Engine:**

1. Install the plugin:
   ```bash
   ibmcloud plugin install code-engine
   ```

2. Create a project:
   ```bash
   ibmcloud login
   ibmcloud target -g Default
   ibmcloud ce project create --name ibm-digest --target
   ```

3. **Migration required:** The current deployment scripts (`deploy_ibm_cloud.py`, `ibm_cloud_handler.py`) need to be rewritten for Code Engine's architecture.

---

## Legacy Content (Deprecated)

The following sections were part of the original Cloud Functions guide and are kept for reference only. **None of these steps work anymore.**

### Original Step 2: Create IBM Cloud Object Storage Bucket (DEPRECATED)

The digest tracks which articles have been sent to avoid duplicates. This state is stored in IBM Cloud Object Storage (COS).

### Via IBM Cloud Console:

1. Go to **Catalog** → Search for **Object Storage**
2. Click **Create** (or use existing instance)
3. Service name: `ibm-digest-storage`
4. Plan: **Lite** (free tier: 25 GB storage, 2,000 Class A requests/month)
5. Click **Create**

6. Create a bucket:
   - Click **Create bucket** → **Customize your bucket**
   - Bucket name: `ibm-digest-state-<your-name>` (must be globally unique)
   - Resiliency: **Regional** (choose your region, e.g., `us-south`)
   - Storage class: **Standard**
   - Click **Create bucket**

7. Get service credentials:
   - Go to **Service credentials** tab
   - Click **New credential**
   - Name: `ibm-digest-credentials`
   - Role: **Writer**
   - Click **Add**
   - Click **View credentials** and note:
     - `apikey`
     - `resource_instance_id` (this is your CRN)
     - `endpoints` → find your regional endpoint (e.g., `s3.us-south.cloud-object-storage.appdomain.cloud`)

### Via IBM Cloud CLI:

```bash
# Create Object Storage instance (if not exists)
ibmcloud resource service-instance-create ibm-digest-storage \
  cloud-object-storage lite us-south

# Create bucket
ibmcloud cos bucket-create \
  --bucket ibm-digest-state-yourname \
  --ibm-service-instance-id <instance-id> \
  --region us-south

# Create service credentials
ibmcloud resource service-key-create ibm-digest-credentials \
  Writer \
  --instance-name ibm-digest-storage
```

**Note the credentials** - you'll need them for environment variables.

---

## Step 3: Set Up SendGrid for Email Delivery

SendGrid is IBM's recommended email service and provides excellent deliverability.

### Create SendGrid Account:

1. Go to https://signup.sendgrid.com/
2. Sign up for free account (100 emails/day)
3. Complete email verification

### Verify Sender Email:

1. Go to **Settings** → **Sender Authentication**
2. Click **Verify a Single Sender**
3. Fill in your details:
   - From Name: `IBM Horizon Atlantic Digest`
   - From Email Address: Your IBM email (e.g., `your.email@ibm.com`)
   - Reply To: Same as From Email
4. Click **Create**
5. Check your email and click verification link

### Create API Key:

1. Go to **Settings** → **API Keys**
2. Click **Create API Key**
3. Name: `IBM Daily Digest`
4. Permissions: **Restricted Access**
   - Enable **Mail Send** → **Full Access**
5. Click **Create & View**
6. **Copy the API key** (you won't see it again!)

**Important:** If using IBM email, you may need to:
- Use a personal email for SendGrid sender (IBM may block external SMTP)
- Or set up Domain Authentication in SendGrid for your IBM domain (requires DNS access)

---

## Step 4: Install IBM Cloud CLI and Plugins

### Install IBM Cloud CLI:

**Windows:**
```powershell
# Download and run installer from:
# https://cloud.ibm.com/docs/cli?topic=cli-install-ibmcloud-cli
```

**macOS:**
```bash
curl -fsSL https://clis.cloud.ibm.com/install/osx | sh
```

**Linux:**
```bash
curl -fsSL https://clis.cloud.ibm.com/install/linux | sh
```

### Important Note About Cloud Functions:

**⚠️ The `cloud-functions` plugin is no longer available in the IBM Cloud plugin repository.**

IBM has deprecated the Cloud Functions CLI plugin. You have two options:

**Option 1: Use IBM Cloud Console (Recommended for Cloud Functions)**
- Deploy and manage Cloud Functions through the web interface at https://cloud.ibm.com/functions
- All CLI commands in this guide can be performed via the console
- Skip to Step 5 and use the "Via IBM Cloud Console" instructions

**Option 2: Migrate to Code Engine (IBM's Modern Serverless Platform)**
```bash
ibmcloud plugin install code-engine
```
Code Engine is IBM's newer serverless platform with enhanced features. However, this guide focuses on Cloud Functions deployment.

### Login and Target:

```bash
# Login to IBM Cloud (use --sso for IBM employees)
ibmcloud login

# Or for IBM SSO:
ibmcloud login --sso

# Target your resource group
ibmcloud target -g Default
```

**For the remainder of this guide, use the IBM Cloud Console** at https://cloud.ibm.com/functions for all deployment steps, as the CLI plugin is no longer available.

---

## Step 5: Create IBM Cloud Function

### Via IBM Cloud Console (Required - CLI Not Available):

1. Go to **Functions** → **Actions**
2. Click **Create**
3. Action name: `ibm-daily-digest`
4. Runtime: **Python 3.11**
5. Click **Create**
6. Upload `ibm_cloud_deployment.zip`
7. Set entry point: `main`
8. Configure:
   - Memory: **512 MB**
   - Timeout: **300000 ms** (5 minutes)
9. Click **Save**

---

## Step 6: Configure Environment Variables

IBM Cloud Functions needs your credentials and configuration.

### Required Environment Variables:

| Variable | Example Value | Description |
|----------|---------------|-------------|
| `SENDGRID_API_KEY` | `SG.xxxxx...` | SendGrid API key |
| `EMAIL_FROM` | `your.email@ibm.com` | Verified sender address |
| `EMAIL_TO` | `recipient1@ibm.com,recipient2@ibm.com` | Recipients (comma-separated) |
| `IBM_COS_BUCKET` | `ibm-digest-state-yourname` | COS bucket name |
| `IBM_COS_ENDPOINT` | `s3.us-south.cloud-object-storage.appdomain.cloud` | COS endpoint URL |
| `IBM_COS_API_KEY` | `xxxxx...` | COS API key from credentials |
| `IBM_COS_INSTANCE_CRN` | `crn:v1:bluemix:...` | COS instance CRN |
| `WATSONX_API_KEY` | `your-watsonx-key` | IBM watsonx API key |
| `WATSONX_PROJECT_ID` | `your-project-id` | IBM watsonx project ID |

### Via IBM Cloud Console (Required - CLI Not Available):

1. Go to **Functions** → **Actions** → **ibm-daily-digest**
2. Click **Parameters** tab
3. Add each parameter from the table above
4. Click **Save**

---

## Step 7: Set Up Hourly Trigger

Configure the function to run automatically every hour using an Alarm trigger.

### Via IBM Cloud Console (Required - CLI Not Available):

1. Go to **Functions** → **Triggers**
2. Click **Create**
3. Trigger type: **Alarm**
4. Name: `hourly-digest-trigger`
5. Schedule: **Cron expression**
6. Cron: `0 * * * *` (every hour)
7. Click **Create**

8. Connect to action:
   - Go to **Connected Actions**
   - Click **Add**
   - Select `ibm-daily-digest`
   - Click **Add**

### Alternative Schedules:

- Every 2 hours: `0 */2 * * *`
- Every 30 minutes: `*/30 * * * *`
- Daily at 9 AM UTC: `0 9 * * *`
- Weekdays at 8 AM EST: `0 13 * * 1-5` (13:00 UTC = 8 AM EST)

---

## Step 8: Test the Deployment

### Manual Test via Console:

1. Go to **Functions** → **Actions** → **ibm-daily-digest**
2. Click **Invoke** (or **Invoke with parameters** for custom input)
3. Check **Activations** tab for results
4. Click on an activation to view detailed logs

### Test Email Only:

To test email functionality without processing feeds:

1. Go to **Functions** → **Actions** → **ibm-daily-digest**
2. Click **Invoke with parameters**
3. Add parameter:
   ```json
   {
     "test_email": "your.email@ibm.com"
   }
   ```
4. Click **Apply** then **Invoke**

Update `ibm_cloud_handler.py` to handle test emails:

```python
def main(params: dict) -> dict:
    # Check for test email request
    if "test_email" in params:
        from .emailer_sendgrid import send_test
        send_test(params["test_email"])
        return {"statusCode": 200, "body": "Test email sent"}
    
    # Normal execution...
```

### Check Logs via Console:

1. Go to **Functions** → **Actions** → **ibm-daily-digest**
2. Click **Activations** tab
3. View recent invocations (should show ~24/day when running hourly)
4. Click any activation to see:
   - **Result**: Return value from function
   - **Logs**: Console output and errors
   - **Duration**: Execution time
   - **Memory**: Memory usage

---

## Step 9: Monitor and Maintain

### IBM Cloud Monitoring:

1. Go to **Functions** → **Actions** → **ibm-daily-digest**
2. Click **Monitor** tab
3. View:
   - **Invocations**: Should be ~24/day (hourly)
   - **Duration**: Typically 30-60 seconds
   - **Errors**: Should be 0

### Set Up Alerts (Optional):

1. Go to **Observability** → **Monitoring**
2. Create alert for function failures
3. Configure notification channels (email, Slack, etc.)

### Cost Estimation:

**IBM Cloud Functions:**
- Free tier: 400,000 GB-seconds/month
- Usage: ~24 invocations/day × 30 days × 60s × 0.5 GB = 21,600 GB-seconds/month
- **Cost: FREE** (well within free tier)

**IBM Cloud Object Storage:**
- Free tier: 25 GB storage, 2,000 Class A requests/month
- Usage: ~1 MB storage, ~50 requests/month
- **Cost: FREE** (well within free tier)

**SendGrid:**
- Free tier: 100 emails/day
- Usage: ~1-5 emails/day (depending on news volume)
- **Cost: FREE** (well within free tier)

**Total: $0/month** (using free tiers)

### Updating the Code:

1. Make changes locally
2. Run `python deploy_ibm_cloud.py` to create updated ZIP
3. Update via IBM Cloud Console:
   - Go to **Functions** → **Actions** → **ibm-daily-digest**
   - Click **Code** tab
   - Click **Upload** and select the new `ibm_cloud_deployment.zip`
   - Verify entry point is still set to `main`
   - Click **Save**

---

## Troubleshooting

### "SendGrid authentication failed"
- Verify `SENDGRID_API_KEY` is correct
- Ensure API key has "Mail Send" permissions
- Check if sender email is verified in SendGrid

### "Email address is not verified"
- Go to SendGrid → Settings → Sender Authentication
- Verify your sender email address
- Check verification email in your inbox

### "No module named 'ibm_boto3'"
- Ensure `requirements-ibm.txt` includes `ibm-cos-sdk`
- Re-run `python deploy_ibm_cloud.py`

### "Access Denied" (COS)
- Verify COS credentials are correct
- Check `IBM_COS_API_KEY` and `IBM_COS_INSTANCE_CRN`
- Ensure bucket exists and credentials have Writer role

### "Action exceeded its time limits"
- Increase timeout in function configuration
- Check if LLM API is responding slowly
- Consider reducing the number of articles processed

### No emails received
- Check activation logs for errors
- Verify `EMAIL_TO` is correct
- Check spam/junk folder
- Test with `send_test()` function

### Emails sent but no new content
- Check `state/seen_articles.json` in COS bucket
- Verify `prefer_new: true` in `config/settings.yaml`
- Ensure RSS feeds are returning new articles

### Function not triggering hourly
- Go to **Functions** → **Triggers** → **hourly-digest-trigger**
- Verify trigger is **Enabled**
- Check **Connected Actions** shows `ibm-daily-digest`
- Go to **Functions** → **Actions** → **ibm-daily-digest** → **Activations**
- Verify invocations are occurring hourly (should see ~24 activations per day)

---

## Security Best Practices

1. **Never commit secrets to Git**
   - Use IBM Cloud Functions parameters
   - Consider IBM Key Protect for production

2. **Restrict IAM permissions**
   - Use least-privilege principle
   - Only grant COS access to specific bucket

3. **Rotate credentials regularly**
   - Update SendGrid API key every 90 days
   - Rotate watsonx API keys periodically
   - Regenerate COS credentials annually

4. **Monitor for anomalies**
   - Set up IBM Cloud Monitoring alerts
   - Review activation logs weekly
   - Monitor SendGrid delivery statistics

5. **Use IBM Cloud Key Protect (Optional)**
   - Store sensitive credentials in Key Protect
   - Reference them in function parameters
   - Automatic encryption at rest

---

## Rollback to Local Execution

If you need to revert to local Windows execution:

1. Keep your original `.env` file
2. Use `python -m src.main` locally
3. IBM Cloud Function continues running independently
4. Disable trigger if needed via console:
   - Go to **Functions** → **Triggers** → **hourly-digest-trigger**
   - Toggle the trigger to **Disabled**
   - Or delete the trigger entirely

---

## Comparison: IBM Cloud vs AWS

| Feature | IBM Cloud | AWS |
|---------|-----------|-----|
| **Compute** | Cloud Functions | Lambda |
| **Storage** | Cloud Object Storage | S3 |
| **Email** | SendGrid (3rd party) | SES (native) |
| **Free Tier** | 400K GB-sec/month | 1M requests/month |
| **Cost** | $0/month (free tier) | ~$0.25/month |
| **Setup** | Simpler (fewer services) | More complex |
| **Email Limits** | 100/day (SendGrid free) | 200/day (SES sandbox) |
| **IBM Integration** | Native watsonx support | Requires API keys |

**Advantages of IBM Cloud:**
- ✅ Completely free (using free tiers)
- ✅ Native IBM watsonx integration
- ✅ Simpler setup (fewer services)
- ✅ Better for IBM employees (same ecosystem)

**Advantages of AWS:**
- ✅ Native email service (SES)
- ✅ More mature ecosystem
- ✅ Better documentation

---

## Support

For issues:
1. Check activation logs first via console:
   - Go to **Functions** → **Actions** → **ibm-daily-digest** → **Activations**
   - Click on failed activation to view logs
2. Review this guide's Troubleshooting section
3. Test components individually (SendGrid, COS, LLM)
4. Verify all parameters are set correctly in **Parameters** tab
5. IBM Cloud Support: https://cloud.ibm.com/unifiedsupport/supportcenter

**Note:** The IBM Cloud Functions CLI plugin (`cloud-functions`) has been deprecated. All management must be done through the IBM Cloud Console at https://cloud.ibm.com/functions

---

## Summary

✓ IBM Cloud Function runs hourly (24/7)
✓ No computer needed - fully cloud-based
✓ State persisted in IBM Cloud Object Storage (no duplicate emails)
✓ SendGrid email delivery (100 emails/day free)
✓ **$0/month cost** (using free tiers)
✓ Native IBM watsonx integration
✓ IBM Cloud Monitoring and logs

Your digest now runs automatically in IBM Cloud!

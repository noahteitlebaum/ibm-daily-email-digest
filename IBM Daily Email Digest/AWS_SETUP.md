# AWS Lambda Deployment Guide
## IBM Daily Email Digest - Cloud Setup

This guide walks you through deploying the IBM Daily Email Digest to AWS Lambda for 24/7 automated operation (hourly execution).

---

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI installed and configured (optional but recommended)
- IBM SMTP credentials (username and password/app password)
- Python 3.11+ installed locally

---

## Step 1: Create Deployment Package

Run the deployment script to create `lambda_deployment.zip`:

```bash
python deploy_lambda.py
```

This creates a ~50MB ZIP file containing all dependencies and source code, optimized for Lambda.

---

## Step 2: Create S3 Bucket for State Storage

The digest tracks which articles have been sent to avoid duplicates. This state is stored in S3.

### Via AWS Console:
1. Go to **S3** → **Create bucket**
2. Bucket name: `ibm-digest-state-<your-name>` (must be globally unique)
3. Region: Choose your preferred region (e.g., `us-east-1`)
4. Block all public access: **Enabled** (default)
5. Versioning: **Disabled** (optional)
6. Click **Create bucket**

### Via AWS CLI:
```bash
aws s3 mb s3://ibm-digest-state-<your-name> --region us-east-1
```

**Note the bucket name** - you'll need it for environment variables.

---

## Step 3: Create IAM Role for Lambda

Lambda needs permissions to write logs and access S3.

### Via AWS Console:

1. Go to **IAM** → **Roles** → **Create role**
2. Trusted entity type: **AWS service**
3. Use case: **Lambda**
4. Click **Next**

5. Attach policies:
   - `AWSLambdaBasicExecutionRole` (for CloudWatch Logs)
   - Create custom policy for S3 access (see below)

6. Custom S3 Policy:
   - Click **Create policy** → **JSON**
   - Paste the following (replace `YOUR-BUCKET-NAME`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/state/*"
    }
  ]
}
```

7. Name the policy: `IBMDigestS3Access`
8. Return to role creation and attach this policy
9. Role name: `IBMDigestLambdaRole`
10. Click **Create role**

### Via AWS CLI:

```bash
# Create trust policy
cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name IBMDigestLambdaRole \
  --assume-role-policy-document file://trust-policy.json

# Attach basic execution policy
aws iam attach-role-policy \
  --role-name IBMDigestLambdaRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Create and attach S3 policy (replace YOUR-BUCKET-NAME)
cat > s3-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/state/*"
    }
  ]
}
EOF

aws iam create-policy \
  --policy-name IBMDigestS3Access \
  --policy-document file://s3-policy.json

aws iam attach-role-policy \
  --role-name IBMDigestLambdaRole \
  --policy-arn arn:aws:iam::YOUR-ACCOUNT-ID:policy/IBMDigestS3Access
```

---

## Step 4: Create Lambda Function

### Via AWS Console:

1. Go to **Lambda** → **Create function**
2. Choose **Author from scratch**
3. Function name: `IBMDailyDigest`
4. Runtime: **Python 3.11** (or 3.12)
5. Architecture: **x86_64**
6. Execution role: **Use an existing role** → Select `IBMDigestLambdaRole`
7. Click **Create function**

8. Upload deployment package:
   - In the **Code** tab, click **Upload from** → **.zip file**
   - Select `lambda_deployment.zip`
   - Click **Save**

9. Configure handler:
   - Runtime settings → **Edit**
   - Handler: `src.lambda_handler.lambda_handler`
   - Click **Save**

10. Configure timeout and memory:
    - **Configuration** tab → **General configuration** → **Edit**
    - Memory: **512 MB** (adjust based on usage)
    - Timeout: **5 minutes** (300 seconds)
    - Click **Save**

### Via AWS CLI:

```bash
# Create function (replace YOUR-ACCOUNT-ID and YOUR-REGION)
aws lambda create-function \
  --function-name IBMDailyDigest \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR-ACCOUNT-ID:role/IBMDigestLambdaRole \
  --handler src.lambda_handler.lambda_handler \
  --zip-file fileb://lambda_deployment.zip \
  --timeout 300 \
  --memory-size 512 \
  --region YOUR-REGION

# Update function code (for subsequent deployments)
aws lambda update-function-code \
  --function-name IBMDailyDigest \
  --zip-file fileb://lambda_deployment.zip
```

---

## Step 5: Configure Environment Variables

Lambda needs your SMTP credentials and configuration. **Never hardcode secrets in code!**

### Required Environment Variables:

| Variable | Example Value | Description |
|----------|---------------|-------------|
| `SMTP_HOST` | `smtp.office365.com` | IBM/Outlook SMTP server |
| `SMTP_PORT` | `587` | SMTP port (587 for TLS) |
| `SMTP_USERNAME` | `your.email@ibm.com` | Your IBM email |
| `SMTP_PASSWORD` | `your-app-password` | IBM app password |
| `EMAIL_FROM` | `your.email@ibm.com` | Sender address |
| `EMAIL_TO` | `recipient1@ibm.com,recipient2@ibm.com` | Recipients (comma-separated) |
| `AWS_S3_BUCKET` | `ibm-digest-state-yourname` | S3 bucket for state |
| `AWS_REGION` | `us-east-1` | AWS region |
| `WATSONX_API_KEY` | `your-watsonx-key` | IBM watsonx API key |
| `WATSONX_PROJECT_ID` | `your-project-id` | IBM watsonx project ID |

### Via AWS Console:

1. Lambda function → **Configuration** tab → **Environment variables**
2. Click **Edit** → **Add environment variable**
3. Add each variable from the table above
4. Click **Save**

### Via AWS CLI:

```bash
aws lambda update-function-configuration \
  --function-name IBMDailyDigest \
  --environment Variables="{
    SMTP_HOST=smtp.office365.com,
    SMTP_PORT=587,
    SMTP_USERNAME=your.email@ibm.com,
    SMTP_PASSWORD=your-app-password,
    EMAIL_FROM=your.email@ibm.com,
    EMAIL_TO=recipient@ibm.com,
    AWS_S3_BUCKET=ibm-digest-state-yourname,
    AWS_REGION=us-east-1,
    WATSONX_API_KEY=your-key,
    WATSONX_PROJECT_ID=your-project-id
  }"
```

### Getting IBM SMTP Credentials:

**Option 1: App Password (Recommended)**
1. Go to https://myaccount.microsoft.com/security
2. Sign in with your IBM account
3. Select **App passwords**
4. Create new app password for "IBM Digest Lambda"
5. Use this password for `SMTP_PASSWORD`

**Option 2: Check with IT**
- Contact IBM IT to confirm SMTP is enabled for your account
- Some corporate accounts block SMTP for security

---

## Step 6: Set Up Hourly Trigger (EventBridge)

Configure Lambda to run automatically every hour.

### Via AWS Console:

1. Lambda function → **Configuration** tab → **Triggers**
2. Click **Add trigger**
3. Select **EventBridge (CloudWatch Events)**
4. Rule type: **Create a new rule**
5. Rule name: `IBMDigestHourlyTrigger`
6. Rule description: `Runs IBM Daily Digest every hour`
7. Schedule expression: `rate(1 hour)`
8. Click **Add**

### Via AWS CLI:

```bash
# Create EventBridge rule
aws events put-rule \
  --name IBMDigestHourlyTrigger \
  --schedule-expression "rate(1 hour)" \
  --state ENABLED

# Add Lambda permission for EventBridge
aws lambda add-permission \
  --function-name IBMDailyDigest \
  --statement-id EventBridgeInvoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:YOUR-REGION:YOUR-ACCOUNT-ID:rule/IBMDigestHourlyTrigger

# Add Lambda as target
aws events put-targets \
  --rule IBMDigestHourlyTrigger \
  --targets "Id"="1","Arn"="arn:aws:lambda:YOUR-REGION:YOUR-ACCOUNT-ID:function:IBMDailyDigest"
```

### Alternative Schedules:

- Every 2 hours: `rate(2 hours)`
- Every 30 minutes: `rate(30 minutes)`
- Daily at 9 AM UTC: `cron(0 9 * * ? *)`
- Weekdays at 8 AM EST: `cron(0 13 ? * MON-FRI *)` (13:00 UTC = 8 AM EST)

---

## Step 7: Test the Deployment

### Manual Test:

1. Lambda function → **Test** tab
2. Create new test event:
   - Event name: `ManualTrigger`
   - Template: `hello-world` (default)
   - Click **Save**
3. Click **Test**
4. Check execution results and CloudWatch Logs

### Test Email Only:

Modify the test event JSON to send a test email:

```json
{
  "test_email": "your.email@ibm.com"
}
```

Then update `lambda_handler.py` to handle this:

```python
def lambda_handler(event: dict, context) -> dict:
    # Check for test email request
    if "test_email" in event:
        from .emailer_cloud import send_test
        send_test(event["test_email"])
        return {"statusCode": 200, "body": "Test email sent"}
    
    # Normal execution...
```

### Check CloudWatch Logs:

1. Lambda function → **Monitor** tab → **View CloudWatch logs**
2. Click latest log stream
3. Look for:
   - ✓ "Fetching Google News RSS feeds..."
   - ✓ "Email sent successfully to..."
   - ✗ Any errors or exceptions

---

## Step 8: Monitor and Maintain

### CloudWatch Metrics:

- **Invocations**: Should be ~24/day (hourly)
- **Duration**: Typically 30-60 seconds
- **Errors**: Should be 0
- **Throttles**: Should be 0

### CloudWatch Alarms (Optional):

Set up alerts for failures:

1. CloudWatch → **Alarms** → **Create alarm**
2. Metric: Lambda → Errors
3. Threshold: > 0 for 2 consecutive periods
4. Action: Send SNS notification to your email

### Cost Estimation:

- Lambda: ~$0.20/month (24 invocations/day × 30 days × 60s avg × $0.0000166667/GB-second)
- S3: ~$0.01/month (minimal storage)
- **Total: ~$0.25/month**

### Updating the Code:

1. Make changes locally
2. Run `python deploy_lambda.py`
3. Upload new `lambda_deployment.zip` to Lambda
4. Test manually before next scheduled run

---

## Troubleshooting

### "SMTP authentication failed"
- Verify `SMTP_USERNAME` and `SMTP_PASSWORD`
- Ensure you're using an app password, not your regular password
- Check if IBM allows SMTP for your account

### "No module named 'boto3'"
- Ensure `requirements-lambda.txt` includes boto3
- Re-run `python deploy_lambda.py`

### "Access Denied" (S3)
- Verify IAM role has S3 permissions
- Check bucket name in `AWS_S3_BUCKET` environment variable
- Ensure bucket exists in the correct region

### "Task timed out after 300 seconds"
- Increase Lambda timeout (Configuration → General configuration)
- Check if LLM API is responding slowly
- Consider reducing the number of articles processed

### No emails received
- Check CloudWatch Logs for errors
- Verify `EMAIL_TO` is correct
- Check spam/junk folder
- Test with `send_test()` function

### Emails sent but no new content
- Check `state/seen_articles.json` in S3
- Verify `prefer_new: true` in `config/settings.yaml`
- Ensure RSS feeds are returning new articles

---

## Security Best Practices

1. **Never commit secrets to Git**
   - Use Lambda environment variables
   - Consider AWS Secrets Manager for production

2. **Restrict IAM permissions**
   - Use least-privilege principle
   - Only grant S3 access to specific bucket/path

3. **Enable CloudWatch Logs encryption**
   - Configuration → Environment variables → Encryption
   - Use AWS KMS key

4. **Rotate credentials regularly**
   - Update SMTP password every 90 days
   - Rotate watsonx API keys periodically

5. **Monitor for anomalies**
   - Set up CloudWatch alarms
   - Review logs weekly

---

## Rollback to Local Execution

If you need to revert to local Windows execution:

1. Keep your original `.env` file
2. Use `python -m src.main` locally
3. Lambda continues running independently
4. Disable EventBridge trigger if needed

---

## Support

For issues:
1. Check CloudWatch Logs first
2. Review this guide's Troubleshooting section
3. Test components individually (SMTP, S3, LLM)
4. Verify all environment variables are set correctly

---

## Summary

✓ Lambda function runs hourly (24/7)
✓ No computer needed - fully cloud-based
✓ State persisted in S3 (no duplicate emails)
✓ SMTP delivery from your IBM account
✓ ~$0.25/month cost
✓ CloudWatch monitoring and logs

Your digest now runs automatically in the cloud!

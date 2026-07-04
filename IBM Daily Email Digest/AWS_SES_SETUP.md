# Amazon SES Setup for Lambda Email Delivery

The digest uses **Amazon SES (Simple Email Service)** instead of SMTP for reliable, authenticated email delivery from Lambda. This avoids SMTP authentication issues with corporate email accounts.

---

## Step 1: Verify Sender Email Address in SES

SES requires you to verify ownership of the sender email address.

### Via AWS Console:

1. Go to **Amazon SES Console**: https://console.aws.amazon.com/ses/
2. Select your region (must match Lambda region, e.g., `us-east-1`)
3. Click **Verified identities** in left sidebar
4. Click **Create identity**
5. Choose **Email address**
6. Enter your email: `your.email@ibm.com` (or personal email)
7. Click **Create identity**
8. **Check your email inbox** for verification email from AWS
9. Click the verification link in the email
10. Return to SES Console - status should show **Verified**

### Via AWS CLI:

```bash
# Verify email address
aws ses verify-email-identity \
  --email-address your.email@ibm.com \
  --region us-east-1

# Check verification status
aws ses get-identity-verification-attributes \
  --identities your.email@ibm.com \
  --region us-east-1
```

**Important:** You must verify the email address you'll use in `EMAIL_FROM` environment variable.

---

## Step 2: Verify Recipient Emails (If in SES Sandbox)

By default, new AWS accounts are in **SES Sandbox mode**, which restricts sending to verified addresses only.

### Check if you're in Sandbox:

1. SES Console → **Account dashboard**
2. Look for "Sending status" - if it says **Sandbox**, you're restricted

### Option A: Verify Recipients (Quick, for testing)

If sending to a small team:

1. SES Console → **Verified identities** → **Create identity**
2. Verify each recipient email address
3. Each person must click verification link in their email

### Option B: Request Production Access (Recommended)

For unrestricted sending:

1. SES Console → **Account dashboard**
2. Click **Request production access**
3. Fill out the form:
   - **Mail type**: Transactional
   - **Website URL**: Your company website or N/A
   - **Use case description**: 
     ```
     Automated daily digest emails for internal team distribution.
     Sends curated news summaries to 5-10 IBM employees.
     Low volume: ~24 emails/day (hourly digest to small team).
     ```
4. Submit request
5. AWS typically approves within 24 hours

---

## Step 3: Add SES Permissions to Lambda IAM Role

Lambda needs permission to send emails via SES.

### Via AWS Console:

1. Go to **IAM Console** → **Roles**
2. Find your Lambda role: `IBMDigestLambdaRole2.0`
3. Click **Add permissions** → **Create inline policy**
4. Click **JSON** tab and paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    }
  ]
}
```

5. Click **Review policy**
6. Name: `IBMDigestSESAccess`
7. Click **Create policy**

### Via AWS CLI:

```bash
# Create SES policy document
cat > ses-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Attach inline policy to Lambda role
aws iam put-role-policy \
  --role-name IBMDigestLambdaRole2.0 \
  --policy-name IBMDigestSESAccess \
  --policy-document file://ses-policy.json
```

---

## Step 4: Update Lambda Environment Variables

Remove SMTP variables and ensure these are set:

### Required Variables:

| Variable | Value | Description |
|----------|-------|-------------|
| `EMAIL_FROM` | `your.email@ibm.com` | **Must be verified in SES** |
| `EMAIL_TO` | `recipient1@ibm.com,recipient2@ibm.com` | Recipients (verify if in sandbox) |
| `AWS_REGION` | `us-east-1` | Must match SES region |

### Remove These (No longer needed):

- ~~`SMTP_HOST`~~
- ~~`SMTP_PORT`~~
- ~~`SMTP_USERNAME`~~
- ~~`SMTP_PASSWORD`~~

### Via AWS Console:

1. Lambda function → **Configuration** → **Environment variables**
2. Click **Edit**
3. Remove SMTP variables
4. Ensure `EMAIL_FROM`, `EMAIL_TO`, `AWS_REGION` are set correctly
5. Click **Save**

### Via AWS CLI:

```bash
aws lambda update-function-configuration \
  --function-name IBMDailyDigest \
  --environment Variables="{
    EMAIL_FROM=your.email@ibm.com,
    EMAIL_TO=recipient@ibm.com,
    AWS_REGION=us-east-1,
    AWS_S3_BUCKET=ibm-digest-state-noahteitlebaum,
    ICA_API_KEY=your-claude-key,
    ICA_MODEL=claude-3-5-sonnet-20241022,
    ICA_BASE_URL=https://api.anthropic.com/v1,
    ICA_AUTH_SCHEME=x-api-key
  }"
```

---

## Step 5: Deploy Updated Code

The code now uses Amazon SES instead of SMTP.

```bash
# 1. Rebuild deployment package with SES changes
python deploy_lambda.py

# 2. Upload to Lambda
aws lambda update-function-code \
  --function-name IBMDailyDigest \
  --zip-file fileb://lambda_deployment.zip

# 3. Wait for update to complete
aws lambda wait function-updated \
  --function-name IBMDailyDigest
```

---

## Step 6: Test Email Delivery

### Test via Lambda Console:

1. Lambda function → **Test** tab
2. Use existing test event or create new one
3. Click **Test**
4. Check CloudWatch Logs for:
   - ✓ `Email sent successfully via SES to ...`
   - ✓ `MessageId: ...`

### Check Your Email:

- Look in inbox (and spam folder)
- Email should arrive within seconds
- Sender will show as verified address

---

## Troubleshooting

### Error: "Email address is not verified"

**Solution:** Verify the sender email in SES Console (Step 1)

```bash
aws ses verify-email-identity \
  --email-address your.email@ibm.com \
  --region us-east-1
```

### Error: "MessageRejected" (Sandbox mode)

**Solution:** Either:
- Verify recipient emails in SES Console
- OR request production access (Step 2, Option B)

### Error: "User is not authorized to perform: ses:SendEmail"

**Solution:** Add SES permissions to Lambda IAM role (Step 3)

### Error: "Configuration set does not exist"

**Solution:** Remove any `ConfigurationSetName` references - not needed for basic sending

### Emails going to spam

**Solutions:**
1. **SPF/DKIM**: Set up in SES Console → Verified identities → Your email → Authentication
2. **Domain verification**: Verify entire domain instead of individual email
3. **Warm up**: Start with low volume, gradually increase
4. **Content**: Avoid spam trigger words, include unsubscribe link

---

## SES Limits and Costs

### Sending Limits:

- **Sandbox**: 200 emails/day, 1 email/second
- **Production**: 50,000 emails/day (can request increase)

### Costs:

- **First 62,000 emails/month**: FREE (when sent from Lambda)
- **After that**: $0.10 per 1,000 emails
- **Your digest**: ~720 emails/month (24/day × 30 days) = **FREE**

### Monitor Usage:

```bash
# Check sending statistics
aws ses get-send-statistics --region us-east-1

# Check sending quota
aws ses get-send-quota --region us-east-1
```

---

## Comparison: SES vs SMTP

| Feature | Amazon SES | SMTP |
|---------|-----------|------|
| **Authentication** | AWS IAM (automatic) | Username/password required |
| **Corporate blocks** | Not blocked | Often blocked by IT |
| **Deliverability** | Excellent (AWS reputation) | Depends on provider |
| **Setup complexity** | Medium (verify emails) | Low (just credentials) |
| **Lambda integration** | Native (boto3) | Requires network calls |
| **Cost** | Free tier generous | Varies by provider |
| **Reliability** | Very high (AWS SLA) | Depends on provider |

---

## Summary

✓ **Step 1**: Verify sender email in SES
✓ **Step 2**: Verify recipients (if in sandbox) OR request production access
✓ **Step 3**: Add SES permissions to Lambda IAM role
✓ **Step 4**: Update Lambda environment variables (remove SMTP vars)
✓ **Step 5**: Deploy updated code with SES support
✓ **Step 6**: Test and verify email delivery

**Result**: Reliable, authenticated email delivery from Lambda without SMTP issues!

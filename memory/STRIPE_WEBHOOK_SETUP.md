# Production Billing Hardening — STRIPE_WEBHOOK_SECRET

## What it is
A signing secret that Stripe uses to sign webhook event payloads.
Without it, anyone can POST fake billing events to your webhook endpoint.

## How to get it

1. Go to https://dashboard.stripe.com/webhooks
2. Click **+ Add endpoint**
3. Set **Endpoint URL** to: `https://YOUR_PRODUCTION_DOMAIN/api/billing/webhook`
4. Under **Select events**, add these 4 events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
5. Click **Add endpoint**
6. On the endpoint detail page, click **Reveal** under **Signing secret**
7. Copy the value (starts with `whsec_...`)

## Where to place it

Add to `/app/backend/.env`:
```
STRIPE_WEBHOOK_SECRET=whsec_YOUR_SECRET_HERE
```

Then restart the backend:
```
sudo supervisorctl restart backend
```

## What changes in behavior

- **With secret set**: Webhook endpoint verifies every request signature. Rejects unsigned or tampered payloads with 400.
- **Without secret**: Webhook endpoint accepts raw JSON (current dev mode). Functional but not production-trustworthy.

## Verification

After setting, test with Stripe CLI:
```bash
stripe listen --forward-to https://YOUR_DOMAIN/api/billing/webhook
stripe trigger checkout.session.completed
```

Or from Stripe Dashboard → Webhooks → Send test webhook.

## Current code location
- Signature verification: `/app/backend/routes/billing.py` lines 88-100
- Config registration: `/app/backend/core/config.py` line 60

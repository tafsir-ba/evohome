# Environment Variable Registry
## Evohome CMP - Production Configuration

This document is the **canonical source** for all environment variables required to deploy Evohome CMP.

---

## Frontend Environment Variables

| Variable | Required | Purpose | Example | Fallback Policy |
|----------|----------|---------|---------|-----------------|
| `REACT_APP_BACKEND_URL` | **YES** | Backend API base URL | `https://api.evo-home.ch` | **FAIL** - App cannot function |

### Frontend `.env` Template

```env
# REQUIRED - No fallbacks
REACT_APP_BACKEND_URL=https://api.evo-home.ch
```

---

## Backend Environment Variables

### Critical (MUST FAIL if missing)

| Variable | Required | Purpose | Example | Fallback Policy |
|----------|----------|---------|---------|-----------------|
| `MONGO_URL` | **YES** | MongoDB connection string | `mongodb+srv://user:pass@cluster.mongodb.net/dbname` | **FAIL** |
| `DB_NAME` | **YES** | MongoDB database name | `evohome` | **FAIL** |
| `JWT_SECRET` | **YES** | JWT signing key (min 32 chars) | `your-secure-random-string-here` | **FAIL** |
| `CORS_ORIGINS` | **YES** | Allowed frontend origins | `https://app.evo-home.ch,https://evo-home.ch` | **FAIL** |

### Integration Keys (graceful degradation)

| Variable | Required | Purpose | Example | Fallback Policy |
|----------|----------|---------|---------|-----------------|
| `RESEND_API_KEY` | Optional | Email delivery | `re_xxxxxxxxxxxx` | WARN - emails disabled |
| `SENDER_EMAIL` | Optional | From address for emails | `noreply@evo-home.ch` | WARN - emails disabled |
| `STRIPE_API_KEY` | Optional | Payment processing | `sk_live_xxxx` | WARN - billing disabled |
| `STRIPE_WEBHOOK_SECRET` | Optional | Stripe webhook verification | `whsec_xxxx` | WARN - webhooks unverified |
| `OPENAI_API_KEY` | Optional | Document AI extraction | `sk-xxxx` | WARN - AI extraction disabled |
| `GOOGLE_CLIENT_SECRET` | Optional | Google OAuth | `GOCSPX-xxxx` | WARN - Google login disabled |

### Application Settings

| Variable | Required | Purpose | Example | Fallback Policy |
|----------|----------|---------|---------|-----------------|
| `FRONTEND_URL` | Optional | Frontend URL for emails | `https://app.evo-home.ch` | Use REACT_APP_BACKEND_URL |
| `OAUTH_BACKEND_URL` | Optional | OAuth callback handler | `https://api.evo-home.ch` | Default internal |
| `ENVIRONMENT` | Optional | Environment identifier | `production` | Default: `development` |

---

## Backend `.env` Template

```env
# ============================================
# CRITICAL - Server will not start without these
# ============================================

# MongoDB Connection
MONGO_URL=mongodb+srv://username:password@cluster.mongodb.net/evohome?retryWrites=true&w=majority
DB_NAME=evohome

# Security - MUST be unique per environment, min 32 characters
JWT_SECRET=your-production-secret-key-minimum-32-characters-long

# CORS - Comma-separated list of allowed origins (NO wildcard in production)
CORS_ORIGINS=https://app.evo-home.ch,https://evo-home.ch

# ============================================
# INTEGRATIONS - Graceful degradation if missing
# ============================================

# Email (Resend)
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
SENDER_EMAIL=noreply@evo-home.ch

# Payments (Stripe)
STRIPE_API_KEY=sk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# AI Extraction (OpenAI)
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# OAuth (Google) - Optional
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxxxxx

# ============================================
# APPLICATION
# ============================================

# Frontend URL for email links
FRONTEND_URL=https://app.evo-home.ch

# Environment identifier
ENVIRONMENT=production
```

---

## Environment-Specific Configurations

### Local Development

```env
MONGO_URL=mongodb://localhost:27017/evohome_dev
DB_NAME=evohome_dev
JWT_SECRET=dev-secret-not-for-production-use-only
CORS_ORIGINS=http://localhost:3000
ENVIRONMENT=development
```

### Staging

```env
MONGO_URL=mongodb+srv://staging:pass@cluster.mongodb.net/evohome_staging
DB_NAME=evohome_staging
JWT_SECRET=staging-secret-unique-per-environment
CORS_ORIGINS=https://staging.evo-home.ch
ENVIRONMENT=staging
```

### Production

```env
MONGO_URL=mongodb+srv://prod:pass@cluster.mongodb.net/evohome
DB_NAME=evohome
JWT_SECRET=production-secret-64-characters-minimum-recommended
CORS_ORIGINS=https://app.evo-home.ch,https://evo-home.ch
ENVIRONMENT=production
```

---

## Validation Rules

### At Startup, the Backend MUST:

1. **FAIL IMMEDIATELY** if any of these are missing or empty:
   - `MONGO_URL`
   - `DB_NAME`
   - `JWT_SECRET`
   - `CORS_ORIGINS`

2. **WARN but continue** if these are missing:
   - `RESEND_API_KEY` (emails disabled)
   - `STRIPE_API_KEY` (billing disabled)
   - `OPENAI_API_KEY` (AI extraction disabled)

3. **REJECT** these configurations:
   - `JWT_SECRET` shorter than 32 characters
   - `CORS_ORIGINS` containing `*` in production
   - `MONGO_URL` without proper URI scheme

---

## Security Checklist

- [ ] JWT_SECRET is unique per environment
- [ ] JWT_SECRET is at least 32 characters (64 recommended for production)
- [ ] CORS_ORIGINS does NOT contain wildcard `*`
- [ ] CORS_ORIGINS lists only trusted domains
- [ ] All secrets are stored in secure secret manager (not in code)
- [ ] Production .env is NOT committed to git
- [ ] Stripe webhook secret matches production endpoint

---

## DigitalOcean App Platform Configuration

In DigitalOcean App Platform, set these as **App-Level Environment Variables**:

1. Go to App → Settings → App-Level Environment Variables
2. Add each variable with appropriate encryption:
   - Mark as **Encrypted**: `JWT_SECRET`, `MONGO_URL`, `STRIPE_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_CLIENT_SECRET`
   - Plain text OK: `DB_NAME`, `CORS_ORIGINS`, `FRONTEND_URL`, `ENVIRONMENT`

---

## Troubleshooting

### "Server fails to start"
- Check `MONGO_URL` is correct and accessible
- Verify `JWT_SECRET` is set and non-empty
- Confirm `CORS_ORIGINS` is set

### "Emails not sending"
- Verify `RESEND_API_KEY` is set
- Check `SENDER_EMAIL` domain is verified in Resend

### "Stripe payments failing"
- Ensure `STRIPE_API_KEY` matches environment (test vs live)
- Verify webhook endpoint is configured in Stripe dashboard

### "Google login not working"
- Check `GOOGLE_CLIENT_SECRET` is set
- Verify OAuth redirect URIs in Google Console

---

*Last updated: January 2026*

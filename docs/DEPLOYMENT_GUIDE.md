# Deployment Guide

**Version:** 2.0  
**Last Updated:** October 2025  
**Status:** 🚧 In Progress

## Overview

This guide covers production deployment of KaryaKarta, including frontend (Next.js), backend (FastAPI), and database (Supabase) setup.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Supabase Setup](#supabase-setup)
4. [Backend Deployment (Railway)](#backend-deployment-railway)
5. [Frontend Deployment (Vercel)](#frontend-deployment-vercel)
6. [Environment Variables](#environment-variables)
7. [Domain & DNS](#domain--dns)
8. [CI/CD Setup](#cicd-setup)
9. [Monitoring](#monitoring)
10. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### Production Stack

```
┌─────────────────────────────────────────────────────────┐
│                  PRODUCTION DEPLOYMENT                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  DNS (CloudFlare/Vercel)                                 │
│       ↓                                                  │
│  Vercel (Frontend - Next.js)                             │
│  ├── app.karyakarta.ai                                   │
│  ├── Static Assets (CDN)                                 │
│  ├── Edge Functions                                      │
│  └── Auto-scaling                                        │
│       ↓                                                  │
│  Railway (Backend - FastAPI)                             │
│  ├── api.karyakarta.ai                                   │
│  ├── WebSocket Server                                    │
│  ├── Background Tasks                                    │
│  └── Auto-scaling                                        │
│       ↓                                                  │
│  Supabase (Database + Auth)                              │
│  ├── PostgreSQL Database                                 │
│  ├── Authentication                                      │
│  ├── Real-time Subscriptions                             │
│  └── Storage                                             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Cost Estimate

| Service | Free Tier | Production (Est.) |
|---------|-----------|------------------|
| **Vercel** | ✅ 100GB bandwidth | ~$20/mo (Pro plan) |
| **Railway** | ✅ $5 credit | ~$10-20/mo |
| **Supabase** | ✅ 500MB DB, 50K MAU | ~$25/mo (Pro plan) |
| **Domain** | N/A | ~$12/year |
| **Total** | **$0/mo** | **~$55-65/mo** |

---

## Prerequisites

### Required Accounts

1. **Supabase Account** - [supabase.com](https://supabase.com)
2. **Railway Account** - [railway.app](https://railway.app)
3. **Vercel Account** - [vercel.com](https://vercel.com)
4. **GitHub Account** - For repository hosting

### Required Tools

```bash
# Install Railway CLI
npm install -g @railway/cli

# Install Vercel CLI
npm install -g vercel

# Install Supabase CLI (optional)
npm install -g supabase
```

### Repository Setup

```bash
# Ensure your code is in a Git repository
git init
git add .
git commit -m "Initial commit"

# Create GitHub repository and push
gh repo create karyakarta --public
git remote add origin https://github.com/your-username/karyakarta.git
git push -u origin main
```

---

## Supabase Setup

### 1. Create Project

1. Go to [supabase.com](https://supabase.com/dashboard)
2. Click **"New Project"**
3. Fill in details:
   - **Organization:** Create or select
   - **Name:** `karyakarta-production`
   - **Database Password:** Generate strong password (save it!)
   - **Region:** Choose closest to your users
   - **Plan:** Free (or Pro for production)

### 2. Run Database Schema

1. Go to **SQL Editor** in Supabase Dashboard
2. Click **"New Query"**
3. Copy SQL from `docs/SUPABASE_INTEGRATION.md`
4. Run the query
5. Verify tables created successfully

### 3. Configure Authentication

1. Go to **Authentication** → **Providers**
2. Enable **Email** provider
3. Configure **Site URL**: `https://app.yourdomain.com`
4. Configure **Redirect URLs**: Add your production URL
5. Customize **Email Templates** (optional)

### 4. Get API Keys

1. Go to **Project Settings** → **API**
2. Copy **URL** and **anon** key (for frontend)
3. Copy **service_role** key (for backend)
4. Save these securely!

---

## Backend Deployment (Railway)

### Option 1: Deploy via Railway CLI

```bash
# Navigate to backend directory
cd karyakarta-agent

# Login to Railway
railway login

# Initialize project
railway init

# Add environment variables
railway variables set SUPABASE_URL="https://xxx.supabase.co"
railway variables set SUPABASE_ANON_KEY="eyJ..."
railway variables set SUPABASE_SERVICE_KEY="eyJ..."
railway variables set GEMINI_API_KEY="your_key"
railway variables set PORT="8000"

# Deploy
railway up

# Get deployment URL
railway domain
```

### Option 2: Deploy via GitHub

1. **Push to GitHub:**
```bash
git push origin main
```

2. **Connect to Railway:**
   - Go to [railway.app](https://railway.app/dashboard)
   - Click **"New Project"**
   - Select **"Deploy from GitHub repo"**
   - Select `karyakarta` repository
   - Select `karyakarta-agent` directory

3. **Configure Build:**
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py` or `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Root Directory:** `karyakarta-agent`

4. **Add Environment Variables:**
   Go to **Variables** tab and add:
   ```
   SUPABASE_URL=https://xxx.supabase.co
   SUPABASE_ANON_KEY=eyJ...
   SUPABASE_SERVICE_KEY=eyJ...
   GEMINI_API_KEY=your_key
   PORT=8000
   LOGGING_URL=https://app.yourdomain.com/api/socket/log
   ```

5. **Generate Domain:**
   - Go to **Settings** → **Domains**
   - Click **"Generate Domain"**
   - Copy the URL (e.g., `karyakarta-production.up.railway.app`)
   - Or add custom domain (e.g., `api.yourdomain.com`)

### Configure CORS

Update backend to allow production frontend:

```python
# karyakarta-agent/main.py

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Development
        "https://app.yourdomain.com",  # Production
        "https://yourdomain.vercel.app"  # Vercel preview
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Frontend Deployment (Vercel)

### Option 1: Deploy via Vercel CLI

```bash
# Navigate to frontend directory
cd karyakarta-ai

# Login to Vercel
vercel login

# Deploy (preview)
vercel

# Deploy (production)
vercel --prod
```

### Option 2: Deploy via GitHub (Recommended)

1. **Push to GitHub** (if not already done)

2. **Import to Vercel:**
   - Go to [vercel.com/dashboard](https://vercel.com/dashboard)
   - Click **"Add New"** → **"Project"**
   - Import your GitHub repository
   - Select `karyakarta-ai` directory

3. **Configure Build Settings:**
   - **Framework Preset:** Next.js
   - **Root Directory:** `karyakarta-ai`
   - **Build Command:** `npm run build`
   - **Output Directory:** `.next`
   - **Install Command:** `npm install`

4. **Add Environment Variables:**
   ```
   NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
   NEXT_PUBLIC_API_URL=https://api.yourdomain.com
   ```

5. **Deploy:**
   - Click **"Deploy"**
   - Wait for deployment to complete
   - Get deployment URL (e.g., `karyakarta.vercel.app`)

### Configure Custom Domain

1. Go to **Project Settings** → **Domains**
2. Add custom domain (e.g., `app.yourdomain.com`)
3. Follow DNS configuration instructions
4. Wait for SSL certificate provisioning

---

## Environment Variables

### Backend (.env)

```bash
# Supabase
SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# LLM
GEMINI_API_KEY=AIzaSyD...

# Server
PORT=8000
LOGGING_URL=https://app.yourdomain.com/api/socket/log

# Environment
ENVIRONMENT=production
DEBUG=false
```

### Frontend (.env.local)

```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Backend API
NEXT_PUBLIC_API_URL=https://api.yourdomain.com

# Environment
NEXT_PUBLIC_ENVIRONMENT=production
```

---

## Domain & DNS

### DNS Configuration

If using custom domain:

```
# CloudFlare DNS Settings

# Frontend (app.yourdomain.com)
Type: CNAME
Name: app
Target: cname.vercel-dns.com
Proxy: ✅ Proxied

# Backend (api.yourdomain.com)
Type: CNAME
Name: api
Target: your-app.up.railway.app
Proxy: ✅ Proxied

# Root domain (yourdomain.com)
Type: A
Name: @
Target: Vercel IP (from Vercel dashboard)
Proxy: ✅ Proxied
```

### SSL Certificates

- **Vercel:** Automatic SSL via Let's Encrypt
- **Railway:** Automatic SSL via Let's Encrypt
- **CloudFlare:** Additional layer (if using CloudFlare)

---

## CI/CD Setup

### GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        working-directory: ./karyakarta-agent
        run: |
          pip install -r requirements.txt
      - name: Run tests
        working-directory: ./karyakarta-agent
        run: |
          pytest tests/ -v

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        working-directory: ./karyakarta-ai
        run: npm install
      - name: Run linter
        working-directory: ./karyakarta-ai
        run: npm run lint
      - name: Build
        working-directory: ./karyakarta-ai
        run: npm run build

  deploy:
    needs: [test-backend, test-frontend]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Railway
        run: |
          # Railway auto-deploys from GitHub
          echo "Backend deployed via Railway"
      - name: Deploy to Vercel
        run: |
          # Vercel auto-deploys from GitHub
          echo "Frontend deployed via Vercel"
```

### Automatic Deployments

- **Push to `main` branch** → Auto-deploy to production
- **Push to feature branch** → Create preview deployment
- **Pull request** → Create preview for testing

---

## Monitoring

### Vercel Analytics

1. Go to Vercel Dashboard → **Analytics**
2. View:
   - Page views
   - Response times
   - Error rates
   - Geographic distribution

### Railway Metrics

1. Go to Railway Dashboard → **Metrics**
2. Monitor:
   - CPU usage
   - Memory usage
   - Network traffic
   - Response times

### Supabase Monitoring

1. Go to Supabase Dashboard → **Database** → **Reports**
2. Track:
   - Database size
   - Active connections
   - Query performance
   - API requests

### Error Tracking (Optional)

**Sentry Integration:**

```bash
# Install Sentry
npm install @sentry/nextjs  # Frontend
pip install sentry-sdk  # Backend

# Configure
```

---

## Troubleshooting

### Common Issues

#### 1. CORS Errors

**Symptom:** `Access-Control-Allow-Origin` errors in browser console

**Solution:**
```python
# Update backend CORS settings
allow_origins=["https://your-frontend-url.com"]
```

#### 2. Environment Variables Not Working

**Symptom:** Features not working in production

**Solution:**
- Verify variables in Railway/Vercel dashboard
- Ensure `NEXT_PUBLIC_` prefix for frontend variables
- Redeploy after adding variables

#### 3. Database Connection Errors

**Symptom:** Cannot connect to Supabase

**Solution:**
- Verify Supabase URL and keys
- Check Supabase project is not paused
- Verify RLS policies are correct

#### 4. Build Failures

**Symptom:** Deployment fails during build

**Solution:**
- Check build logs
- Verify dependencies in `requirements.txt` / `package.json`
- Ensure Node/Python versions match

#### 5. WebSocket Connection Failed

**Symptom:** Real-time features not working

**Solution:**
- Ensure WebSocket support is enabled (Railway supports it by default)
- Check firewall/proxy settings
- Verify connection URL is correct

### Health Checks

**Backend Health Check:**
```bash
curl https://api.yourdomain.com/
# Should return: {"status": "KaryaKarta Python Agent is running."}
```

**Frontend Health Check:**
```bash
curl https://app.yourdomain.com/
# Should return 200 OK
```

**Database Health Check:**
```bash
# In Supabase SQL Editor
SELECT 1;
# Should return 1
```

---

## Rollback Strategy

### Vercel Rollback

1. Go to **Deployments** tab
2. Find previous successful deployment
3. Click **"..."** → **"Promote to Production"**

### Railway Rollback

1. Go to **Deployments** tab
2. Find previous deployment
3. Click **"Redeploy"**

### Database Rollback

1. Go to Supabase Dashboard → **Database** → **Backups**
2. Select backup point
3. Click **"Restore"**

---

## Security Checklist

- [ ] Environment variables secured (not in code)
- [ ] API keys rotated
- [ ] HTTPS enabled on all endpoints
- [ ] CORS properly configured
- [ ] RLS policies enabled on all tables
- [ ] Service role key never exposed to frontend
- [ ] Rate limiting enabled (if needed)
- [ ] Input validation on all endpoints
- [ ] Error messages don't expose sensitive info
- [ ] Database backups enabled
- [ ] Monitoring and alerts set up

---

## Maintenance

### Regular Tasks

- **Weekly:** Check error logs, monitor performance
- **Monthly:** Review costs, optimize resources
- **Quarterly:** Update dependencies, security patches
- **Yearly:** Review architecture, plan improvements

### Scaling Considerations

When to scale:
- Response time > 1 second
- Error rate > 1%
- CPU usage > 80%
- Memory usage > 80%

How to scale:
- **Vercel:** Upgrade to Pro plan for more bandwidth
- **Railway:** Increase resources or add replicas
- **Supabase:** Upgrade to Pro plan for better performance

---

## Resources

- [Vercel Documentation](https://vercel.com/docs)
- [Railway Documentation](https://docs.railway.app)
- [Supabase Documentation](https://supabase.com/docs)
- [Next.js Deployment](https://nextjs.org/docs/deployment)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)

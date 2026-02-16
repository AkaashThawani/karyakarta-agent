# Render Deployment Guide for KaryaKarta Agent

This guide will help you deploy the KaryaKarta Agent backend to Render.

---

## 🚀 Quick Deployment Steps

### Step 1: Push the Render Branch to GitHub

```bash
# Make sure you're on the render-deploy branch
git branch --show-current  # Should show: render-deploy

# Push to GitHub
git push origin render-deploy
```

### Step 2: Create Web Service on Render

1. Go to [render.com](https://render.com) and sign in
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Select the repository: `karyakarta`

### Step 3: Configure the Service

**Basic Settings:**
- **Name**: `karyakarta-agent` (or your preferred name)
- **Region**: Choose closest to your users
- **Branch**: `render-deploy` ⚠️ IMPORTANT: Select this branch
- **Root Directory**: `karyakarta-agent`
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt && playwright install --with-deps chromium`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

**Instance Type:**
- For testing: **Free** (512 MB RAM, spins down after inactivity)
- For production: **Starter** ($7/month, 512 MB RAM, always on)
- For heavy usage: **Standard** ($25/month, 2 GB RAM)

### Step 4: Add Environment Variables

In the Render dashboard, go to **Environment** tab and add these variables:

#### Required Variables:

| Variable | Value | Where to Get It |
|----------|-------|----------------|
| `GEMINI_API_KEY` | `your_key_here` | [Google AI Studio](https://makersuite.google.com/app/apikey) |
| `SERPER_API_KEY` | `your_key_here` | [Serper.dev](https://serper.dev/) |
| `SUPABASE_URL` | `https://xxx.supabase.co` | Supabase Dashboard → Settings → API |
| `SUPABASE_SERVICE_KEY` | `eyJhbGc...` | Supabase Dashboard → Settings → API (Service Role Key) |

#### Optional Variables:

| Variable | Value | Description |
|----------|-------|-------------|
| `HEADLESS` | `true` | Run browser in headless mode (recommended for production) |
| `ENVIRONMENT` | `production` | Set environment mode |
| `BROWSERLESS_API_KEY` | `your_key_here` | Optional: [Browserless.io](https://www.browserless.io/) API key |
| `BROWSERLESS_ENDPOINT` | `wss://chrome.browserless.io` | Optional: Browserless endpoint |

**Important Notes:**
- ⚠️ Do NOT set `PORT` - Render sets this automatically
- ⚠️ Use `SUPABASE_SERVICE_KEY` (not SUPABASE_ANON_KEY) for backend
- ✅ All environment variables are encrypted by Render

### Step 5: Deploy

1. Click **"Create Web Service"**
2. Render will automatically:
   - Clone your repository
   - Install dependencies
   - Start the uvicorn server
3. Wait for deployment to complete (~5-10 minutes first time)

---

## 📝 Post-Deployment

### Get Your Backend URL

After deployment completes, you'll get a URL like:
```
https://karyakarta-agent.onrender.com
```

### Test Your Deployment

```bash
# Test health endpoint
curl https://your-app.onrender.com/health

# Expected response:
{
  "status": "healthy",
  "service": "karyakarta-agent",
  "version": "1.0.0"
}
```

### Update Frontend

Update your frontend environment variables in Vercel:
```env
NEXT_PUBLIC_API_URL=https://your-app.onrender.com
```

Then redeploy your frontend.

---

## 🔧 Troubleshooting

### Deployment Fails

**Check Build Logs:**
1. Go to Render Dashboard → Your Service → Logs
2. Look for error messages during build

**Common Issues:**
- **Missing dependencies**: Check `requirements.txt` is complete
- **Python version**: Render uses Python 3.7+ by default
- **Build timeout**: Increase timeout in Render settings

### Service Crashes After Deployment

**Check Runtime Logs:**
1. Go to Render Dashboard → Your Service → Logs
2. Look for Python errors

**Common Issues:**
- **Missing environment variables**: Double-check all required vars are set
- **Invalid API keys**: Verify API keys are correct
- **Memory issues**: Upgrade to a larger instance type

### Background Tasks Not Working

If tasks don't execute:
1. Check logs for errors
2. Verify Supabase connection
3. Check GEMINI_API_KEY is valid
4. Ensure sufficient memory (upgrade instance if needed)

### Playwright Browser Issues

If browser automation fails:
1. Ensure `HEADLESS=true` is set
2. Check instance has enough memory (minimum 512 MB)
3. Consider upgrading to Standard plan for more resources

---

## 💰 Cost Estimation

### Free Tier
- **Cost**: $0/month
- **Limitations**: 
  - Spins down after 15 minutes of inactivity
  - Takes 30-60 seconds to spin up
  - 750 hours/month (good for testing)

### Starter Plan
- **Cost**: $7/month
- **Benefits**:
  - Always on
  - Faster response times
  - 512 MB RAM
  - Good for small production apps

### Standard Plan
- **Cost**: $25/month (2 GB RAM) - $85/month (8 GB RAM)
- **Benefits**:
  - More memory for complex tasks
  - Better performance
  - Recommended for production with heavy usage

---

## 🔄 Continuous Deployment

Render automatically deploys when you push to the `render-deploy` branch:

```bash
# Make changes
git add .
git commit -m "Update feature"
git push origin render-deploy

# Render automatically deploys the new version
```

### Manual Deploy

You can also manually deploy from the Render dashboard:
1. Go to your service
2. Click **"Manual Deploy"** → **"Deploy latest commit"**

---

## 📊 Monitoring

### View Logs

Real-time logs are available in the Render dashboard:
1. Go to your service
2. Click **"Logs"** tab
3. See live server logs

### Health Checks

Render automatically checks `/health` endpoint every 30 seconds to ensure your service is running.

### Metrics

View metrics in Render dashboard:
- CPU usage
- Memory usage
- Request count
- Response time

---

## 🔐 Security Best Practices

1. **Environment Variables**: Never commit API keys to git
2. **HTTPS**: Render provides free SSL certificates automatically
3. **Secrets**: Use Render's secret files for sensitive data if needed
4. **Rate Limiting**: Already configured in the code
5. **CORS**: Configure allowed origins in `main.py` if needed

---

## 🚨 Important Notes

### Free Tier Limitations

The free tier spins down after 15 minutes of inactivity:
- First request after spin-down takes 30-60 seconds
- Not suitable for production with real users
- Good for testing and development

### Recommendation for Production

For production use:
- **Minimum**: Starter plan ($7/month) for always-on service
- **Recommended**: Standard plan ($25/month) for better performance
- **Heavy usage**: Standard Plus ($85/month) for 8 GB RAM

---

## 📚 Additional Resources

- [Render Documentation](https://render.com/docs)
- [Render Python Guide](https://render.com/docs/deploy-fastapi)
- [Render Environment Variables](https://render.com/docs/environment-variables)

---

## ✅ Deployment Checklist

Before going live:

- [ ] Push `render-deploy` branch to GitHub
- [ ] Create web service on Render
- [ ] Set all required environment variables
- [ ] Test `/health` endpoint
- [ ] Test a simple query
- [ ] Update frontend API URL
- [ ] Test end-to-end functionality
- [ ] Set up monitoring/alerts
- [ ] Consider upgrading from free tier

---

## 🎉 You're Done!

Your KaryaKarta Agent backend is now deployed on Render and ready to handle requests!

**Next Steps:**
1. Test thoroughly with your frontend
2. Monitor logs for any issues
3. Consider upgrading plan based on usage
4. Set up custom domain if needed

**Need Help?**
- Check logs in Render dashboard
- Review this guide
- Check Render documentation
- Contact support if needed

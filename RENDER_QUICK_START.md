# Render Quick Start - Environment Variables

## Required Environment Variables for Render

Copy these to your Render dashboard under **Environment** tab:

### Core API Keys (Required)
```
GEMINI_API_KEY=your_gemini_api_key_here
SERPER_API_KEY=your_serper_api_key_here
```

### Supabase (Required)
```
SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Production Settings (Recommended)
```
HEADLESS=true
ENVIRONMENT=production
```

### Optional (If Using Browserless)
```
BROWSERLESS_API_KEY=your_browserless_key_here
BROWSERLESS_ENDPOINT=wss://chrome.browserless.io
```

---

## Where to Get API Keys

1. **GEMINI_API_KEY**: https://makersuite.google.com/app/apikey
2. **SERPER_API_KEY**: https://serper.dev/
3. **SUPABASE Credentials**: 
   - Go to Supabase Dashboard
   - Settings → API
   - Copy Project URL and Service Role Key

---

## Render Service Configuration

```
Name: karyakarta-agent
Branch: render-deploy  ⚠️ IMPORTANT
Root Directory: karyakarta-agent
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## Next Steps

1. Push branch: `git push origin render-deploy`
2. Create web service on Render
3. Configure settings above
4. Add environment variables
5. Deploy!

Full guide: See `RENDER_DEPLOYMENT.md`

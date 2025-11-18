from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from api.routes import router
from api.session_routes import router as session_router
from api.middleware import setup_middleware
import asyncio
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title="KaryaKarta Agent API",
    description="AI Agent with Google Search and Web Scraping capabilities",
    version="1.0.0",
    # Important: This tells FastAPI we're behind a proxy
    root_path="",
    # Configure to use forwarded headers from proxy
    openapi_url="/openapi.json"
)

# Add middleware to handle X-Forwarded-Proto header from proxy (Render, Cloud Run, etc.)
@app.middleware("http")
async def force_https_redirect(request: Request, call_next):
    """Force HTTPS in redirect URLs when behind a proxy"""
    # Only apply HTTPS forcing if we're behind a proxy (production)
    # Check for X-Forwarded-Proto header which indicates we're behind a proxy
    forwarded_proto = request.headers.get("x-forwarded-proto")
    
    # Only modify scheme if we're actually behind a proxy
    if forwarded_proto == "https":
        request.scope["scheme"] = "https"
    
    response = await call_next(request)
    return response

# Dynamic CORS middleware to force HTTPS
class DynamicCORSMiddleware(CORSMiddleware):
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            origin_bytes = headers.get(b'origin')
            if origin_bytes:
                origin = origin_bytes.decode()
                # Force HTTPS
                secure_origin = origin.replace("http://", "https://")
                self.allow_origins = [secure_origin]
                logger.info(f"[CORS] Allowing origin: {secure_origin}")
        await super().__call__(scope, receive, send)

# Replace standard CORS with dynamic one
app.add_middleware(
    DynamicCORSMiddleware,
    allow_origins=["*"],  # default, will be overwritten
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include routes
app.include_router(router)
app.include_router(session_router)

# Setup other middleware (logging, rate limiting, etc.)
setup_middleware(app, enable_cors=False)  # Disable default CORS since we handle it dynamically

# Startup event - Initialize and verify services
@app.on_event("startup")
async def startup_event():
    """Verify all services initialize correctly on startup"""
    print("\n" + "="*60)
    print("🚀 KARYAKARTA AGENT STARTUP")
    print("="*60)
    
    # Check environment variables
    import os
    
    # Detect platform
    if os.getenv('RENDER'):
        platform = "Render"
    elif os.getenv('K_SERVICE'):
        platform = "Google Cloud Run"
    else:
        platform = "Local"
    
    print(f"✓ Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"✓ Platform: {platform}")
    print(f"✓ GEMINI_API_KEY: {'Set' if os.getenv('GEMINI_API_KEY') else 'MISSING!'}")
    print(f"✓ SUPABASE_URL: {'Set' if os.getenv('SUPABASE_URL') else 'MISSING!'}")
    print(f"✓ SUPABASE_SERVICE_KEY: {'Set' if os.getenv('SUPABASE_SERVICE_KEY') else 'MISSING!'}")
    
    # Test Supabase connection
    try:
        from src.services.supabase_service import get_supabase_service
        supabase = get_supabase_service()
        if supabase.health_check():
            print("✅ Supabase: Connected")
        else:
            print("❌ Supabase: Health check failed")
    except Exception as e:
        print(f"❌ Supabase: Failed to initialize - {e}")
    
    # Test LLM service
    try:
        from src.services.llm_service import LLMService
        from src.core.config import settings
        llm_service = LLMService(settings)
        model = llm_service.get_model()
        print(f"✅ LLM Service: Initialized ({settings.llm_model})")
    except Exception as e:
        print(f"❌ LLM Service: Failed to initialize - {e}")
    
    # Test Agent Manager
    try:
        from agent_logic import get_agent_manager
        manager = get_agent_manager()
        stats = manager.get_stats()
        print(f"✅ Agent Manager: Initialized ({stats['tools_count']} tools)")
    except Exception as e:
        print(f"❌ Agent Manager: Failed to initialize - {e}")
    
    print("="*60)
    print("✅ Startup complete!")
    print("="*60 + "\n")

# Shutdown handler (Playwright cleanup)
@app.on_event("shutdown")
async def shutdown_event():
    print("[SHUTDOWN] Cleaning up Playwright browsers...")
    try:
        from src.tools.playwright_universal import UniversalPlaywrightTool
        UniversalPlaywrightTool.stop_all_loops()
        await asyncio.sleep(0.5)
        UniversalPlaywrightTool._browser_instances.clear()
        UniversalPlaywrightTool._page_instances.clear()
        UniversalPlaywrightTool._playwright_instances.clear()
        UniversalPlaywrightTool._event_loops.clear()
        UniversalPlaywrightTool._loop_threads.clear()
        UniversalPlaywrightTool._stop_flags.clear()
        await asyncio.sleep(0.5)
        print("[SHUTDOWN] ✅ Cleanup complete!")
    except Exception as e:
        print(f"[SHUTDOWN] Error during cleanup: {e}")

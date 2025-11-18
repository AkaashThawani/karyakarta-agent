from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from api.session_routes import router as session_router
from api.middleware import setup_middleware
import asyncio
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title="KaryaKarta Agent API",
    description="AI Agent with Google Search and Web Scraping capabilities",
    version="1.0.0"
)

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

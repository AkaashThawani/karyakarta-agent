# main.py
"""
FastAPI Application Entry Point

Clean and minimal main.py that imports routes from api/routes.py
All route logic is separated into the api module for better organization.
"""

from fastapi import FastAPI
from api.routes import router
from api.session_routes import router as session_router
from api.middleware import setup_middleware
import asyncio

# Create FastAPI application
app = FastAPI(
    title="KaryaKarta Agent API",
    description="AI Agent with Google Search and Web Scraping capabilities",
    version="1.0.0"
)

# Setup CORS and other middleware
setup_middleware(
    app,
    allowed_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
)

# Include all routes from api/routes.py
app.include_router(router)

# Include session management routes
app.include_router(session_router)

# Shutdown handler to cleanup Playwright browsers
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup all Playwright browser sessions on shutdown."""
    print("[SHUTDOWN] Cleaning up Playwright browsers...")
    
    try:
        from src.tools.playwright_universal import UniversalPlaywrightTool
        
        # CRITICAL: Stop event loops first to allow graceful shutdown
        UniversalPlaywrightTool.stop_all_loops()
        
        # Close all browser instances with timeout
        for session_id in list(UniversalPlaywrightTool._browser_instances.keys()):
            try:
                browser = UniversalPlaywrightTool._browser_instances.get(session_id)
                if browser:
                    print(f"[SHUTDOWN] Closing browser for session: {session_id}")
                    # Add 5 second timeout to prevent hanging
                    await asyncio.wait_for(browser.close(), timeout=5.0)
                    print(f"[SHUTDOWN] ✅ Browser closed: {session_id}")
            except asyncio.TimeoutError:
                print(f"[SHUTDOWN] ⚠️ Timeout closing browser {session_id}, forcing cleanup")
            except Exception as e:
                print(f"[SHUTDOWN] Error closing browser {session_id}: {e}")
        
        # Close all Playwright instances
        for session_id in list(UniversalPlaywrightTool._playwright_instances.keys()):
            try:
                playwright = UniversalPlaywrightTool._playwright_instances.get(session_id)
                if playwright:
                    print(f"[SHUTDOWN] Stopping Playwright for session: {session_id}")
                    await playwright.stop()
            except Exception as e:
                print(f"[SHUTDOWN] Error stopping Playwright {session_id}: {e}")
        
        # Stop all event loops
        for session_id in list(UniversalPlaywrightTool._event_loops.keys()):
            try:
                loop = UniversalPlaywrightTool._event_loops.get(session_id)
                if loop and loop.is_running():
                    print(f"[SHUTDOWN] Stopping event loop for session: {session_id}")
                    loop.call_soon_threadsafe(loop.stop)
            except Exception as e:
                print(f"[SHUTDOWN] Error stopping loop {session_id}: {e}")
        
        # Clear all references
        UniversalPlaywrightTool._browser_instances.clear()
        UniversalPlaywrightTool._page_instances.clear()
        UniversalPlaywrightTool._playwright_instances.clear()
        UniversalPlaywrightTool._event_loops.clear()
        
        print("[SHUTDOWN] ✅ Cleanup complete!")
        
    except Exception as e:
        print(f"[SHUTDOWN] Error during cleanup: {e}")

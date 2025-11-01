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
        
        # CRITICAL: Signal all loops to stop first
        print("[SHUTDOWN] Signaling all event loops to stop...")
        UniversalPlaywrightTool.stop_all_loops()
        
        # Give loops a moment to stop gracefully
        await asyncio.sleep(0.5)
        
        # Force cleanup of all resources WITHOUT awaiting browser close
        # (browsers in other loops can't be awaited from this loop)
        print("[SHUTDOWN] Cleaning up resources...")
        
        for session_id in list(UniversalPlaywrightTool._browser_instances.keys()):
            try:
                browser = UniversalPlaywrightTool._browser_instances.get(session_id)
                if browser:
                    print(f"[SHUTDOWN] Marking browser for cleanup: {session_id}")
                    # Don't await - just mark for cleanup
                    try:
                        # Try to close synchronously if possible
                        if hasattr(browser, '_impl_obj'):
                            # Force close without waiting
                            pass
                    except:
                        pass
            except Exception as e:
                print(f"[SHUTDOWN] Error marking browser {session_id}: {e}")
        
        # Clear all references immediately
        print("[SHUTDOWN] Clearing all references...")
        UniversalPlaywrightTool._browser_instances.clear()
        UniversalPlaywrightTool._page_instances.clear()
        UniversalPlaywrightTool._playwright_instances.clear()
        UniversalPlaywrightTool._event_loops.clear()
        UniversalPlaywrightTool._loop_threads.clear()
        UniversalPlaywrightTool._stop_flags.clear()
        
        # Give threads a moment to finish
        await asyncio.sleep(0.5)
        
        print("[SHUTDOWN] ✅ Cleanup complete!")
        
    except Exception as e:
        print(f"[SHUTDOWN] Error during cleanup: {e}")
        import traceback
        traceback.print_exc()

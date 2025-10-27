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

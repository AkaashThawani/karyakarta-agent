# main.py
"""
FastAPI Application Entry Point

Clean and minimal main.py that imports routes from api/routes.py
All route logic is separated into the api module for better organization.
"""

from fastapi import FastAPI
from api.routes import router

# Create FastAPI application
app = FastAPI(
    title="KaryaKarta Agent API",
    description="AI Agent with Google Search and Web Scraping capabilities",
    version="1.0.0"
)

# Include all routes from api/routes.py
app.include_router(router)

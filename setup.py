"""
Setup configuration for KaryaKarta Agent
Minimal setup.py that doesn't read requirements files to avoid encoding issues.
"""

from setuptools import setup, find_packages

setup(
    name="karyakarta-agent",
    version="0.1.0",
    description="AI Agent for task execution with Google Gemini and LangGraph",
    author="KaryaKarta Team",
    python_requires=">=3.10",
    packages=find_packages(exclude=["tests", "tests.*", "docs"]),
    install_requires=[
        # Core dependencies - kept minimal to avoid encoding issues
        # Install full dependencies with: pip install -r requirements.txt
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)

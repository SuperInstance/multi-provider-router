"""Setup configuration for multi-provider-router package"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_file(filename):
    """Read file contents"""
    with open(os.path.join(os.path.dirname(__file__), filename), encoding='utf-8') as f:
        return f.read()

setup(
    name="multi-provider-router",
    version="1.0.0",
    author="Multi-Provider Router Team",
    author_email="contact@multi-provider-router.dev",
    description="Intelligent AI API router for cost optimization across multiple providers",
    long_description=read_file("README.md"),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/multi-provider-router",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/multi-provider-router/issues",
        "Source": "https://github.com/yourusername/multi-provider-router",
        "Documentation": "https://multi-provider-router.readthedocs.io/",
    },
    packages=find_packages(exclude=["tests", "tests.*", "examples", "examples.*"]),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Framework :: FastAPI",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.115.0",
        "uvicorn[standard]>=0.30.0",
        "pydantic>=2.10.0",
        "pydantic-settings>=2.7.0",
        "httpx>=0.28.0",
        "aiohttp>=3.11.0",
        "redis>=5.2.0",
        "prometheus-client>=0.21.0",
        "structlog>=24.5.0",
        "tenacity>=9.0.0",
        "python-dotenv>=1.0.1",
        "orjson>=3.10.12",
        "python-dateutil>=2.9.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.3.0",
            "pytest-asyncio>=0.24.0",
            "pytest-mock>=3.14.0",
            "black>=24.10.0",
            "ruff>=0.8.4",
            "mypy>=1.13.0",
            "pre-commit>=4.0.1",
        ],
        "postgres": [
            "sqlalchemy>=2.0.36",
            "alembic>=1.14.0",
            "asyncpg>=0.30.0",
        ],
        "celery": [
            "celery>=5.4.0",
            "kombu>=5.4.2",
        ],
    },
    entry_points={
        "console_scripts": [
            "multi-provider-router=multi_provider_router.main:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="ai router api cost-optimization multi-provider llm machine-learning",
)

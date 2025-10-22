"""
Setup script for Polymarket Insider Bot CLI
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text() if readme_path.exists() else ""

setup(
    name="polymarket-insider-bot",
    version="1.0.0",
    description="Polymarket insider trading detection bot with CLI interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/insider-poly-bot",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.10",
    install_requires=[
        "aiohttp>=3.8.0",
        "websockets>=11.0",
        "python-dotenv>=1.0.0",
        "colorama>=0.4.6",
        # Database and persistence
        "sqlalchemy>=2.0.23",
        "aiosqlite>=0.19.0",
        "alembic>=1.13.0",
        # CLI framework
        "click>=8.1.7",
        "rich>=13.7.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-mock>=3.12.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "insider-bot=cli.main:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="polymarket insider-trading blockchain prediction-markets",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/insider-poly-bot/issues",
        "Source": "https://github.com/yourusername/insider-poly-bot",
    },
)

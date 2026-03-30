This file provides guidance to Claude Code (claude.ai/code) when working with code in this   
  repository.                                                                                  
                                                                                               
  Project Overview                                                                             
                                                                                               
  The codebase is a production-grade FastAPI application structured with:                    
  - src/: Core application code
    - main.py: FastAPI application entrypoint
    - routers/: API endpoint definitions
    - models/: Pydantic validation models
    - services/: Business logic implementation
  - tests/: Unit test suite
  - docker/: Production deployment configuration
  - requirements.txt: Production dependencies

  Common Commands

  - Run Development Server: uvicorn src.main:app --reload
  - Run Tests: pytest tests/
  - Format Code: black src/
  - Check Linting: flake8 src/
  - Build Docker Image: docker build -t app .

  Architecture Highlights

  - Async Operations: All endpoints use async for non-blocking I/O
  - Dependency Injection: Services injected via FastAPI dependency system
  - Pydantic Validation: Strict request/response schema validation
  - Dockerized Deployment: Production uses Docker with Uvicorn

  Environment Setup

  - Install dependencies: pip install -r requirements.txt
  - Configure environment variables in .env (e.g., DATABASE_URL, SECRET_KEY)

  This document focuses on actionable guidance for codebase navigation and operations without
  redundant or generic advice.
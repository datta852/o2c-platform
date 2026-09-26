# O2C Platform

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)
![Status](https://img.shields.io/badge/Status-Active%20Development-orange)
![License](https://img.shields.io/badge/License-MIT-blue)

## Overview

O2C Platform is a lightweight backend application built with FastAPI to support customer management and service monitoring. The project currently includes a basic API structure with endpoints for health checks, project information, creating customers, and retrieving customer records by ID.

## Features

- Health monitoring endpoint
- Project metadata endpoint
- Customer creation API
- Customer lookup by ID
- In-memory data storage for early-stage development

## Tech Stack

- Python
- FastAPI
- Pydantic

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Returns a basic welcome response |
| GET | `/health` | Checks service health status |
| GET | `/about` | Returns project information |
| POST | `/customers` | Creates a new customer record |
| GET | `/customers/{customer_id}` | Fetches a customer by ID |

## Current Progress

The project is in its early development stage and establishes a solid backend foundation for future expansion. Current functionality focuses on basic API behavior and core customer data operations, with room for database integration, validation improvements, authentication, and business logic enhancements.

## Getting Started

```bash
pip install fastapi uvicorn
uvicorn main:app --reload
```

Then open:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

## Roadmap

- Add persistent database storage
- Improve customer validation and error handling
- Add authentication and authorization
- Expand business logic for O2C workflows
- Deploy to a production-ready environment

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
| PUT | `/customers/{customer_id}` | Modifies a customer by ID |
| DELETE | `/customers/{customer_id}` | Deletes a customer by ID |

## Current Progress

The project has progressed from a basic backend skeleton into a working FastAPI service with a clean API structure, health checks, project metadata, and full customer CRUD operations. Recent updates include a consistent endpoint layout, in-memory customer management, and a foundation for future validation, persistence, and business workflow expansion.

## Getting Started

```bash
pip install fastapi
fastapi dev
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

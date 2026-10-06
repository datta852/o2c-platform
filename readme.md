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
| GET | `/customers` | Fetches the complete list of customers |
| GET | `/customers/{customer_id}` | Fetches a customer by ID |
| PUT | `/customers/{customer_id}` | Modifies a customer by ID |
| DELETE | `/customers/{customer_id}` | Deletes a customer by ID |
| POST | `/orders` | Creates a new sales order |
| GET | `/orders` | Fetches the complete list of orders |
| GET | `/orders/{order_id}` | Fetches a order by ID |
| PUT | `/orders/{order_id}` | Modifies a order by ID |
| DELETE | `/orders/{order_id}` | Deletes a order by ID |

## Current Progress

The project has progressed from a basic backend skeleton into a working FastAPI service with a clean API structure, health checks, project metadata, and full CRUD operations for customers and sales orders. Recent updates include database-backed sales order storage and complete sales order creation, retrieval, modification, and deletion, alongside in-memory customer management. This provides a foundation for expanding validation, customer persistence, and broader O2C workflows.

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

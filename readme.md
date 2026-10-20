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
| POST | `/invoices` | Creates a new invoice |
| GET | `/invoices` | Fetches the complete list of invoices |
| GET | `/invoices/{invoice_id}` | Fetches an Invoice by ID |
| PUT | `/invoices/{invoice_id}` | Modifies an Invoice by ID |
| DELETE | `/invoices/{invoice_id}` | Deletes an Invoice by ID |
| POST | `/payments` | Creates a new payment |
| GET | `/payments` | Fetches the complete list of payment |
| GET | `/payments/{payment_id}` | Fetches an payment by ID |
| PUT | `/payments/{payment_id}` | Modifies an payment by ID |
| DELETE | `/payments/{payment_id}` | Deletes an payment by ID |

## Current Progress

## Current Project Progress

The O2C (Order-to-Cash) Application Platform has evolved from a basic backend skeleton into a functional FastAPI application with structured REST API endpoints, health checks, project metadata, Pydantic-based request validation, and SQLAlchemy-powered database integration using SQLite.

The application currently implements CRUD operations for **customers, sales orders, invoices, and payments**, along with payment allocation functionality that connects incoming payments to outstanding invoices.

### Key Features Implemented

- **FastAPI Application Structure:** Health check endpoint, root endpoint, project information, and organized API routes.
- **Database Integration:** SQLite database with SQLAlchemy ORM models, database sessions, and dependency injection.
- **Customer Management:** Create, retrieve, update, and delete customers.
- **Sales Order Management:** Create, retrieve, update, and delete sales orders, with database persistence.
- **Invoice Management:** Create, retrieve, update, and delete invoices, with customer and sales order existence checks during creation.
- **Payment Management:** Create, retrieve, update, and delete payments, including payment references, dates, amounts, methods, and statuses.
- **Payment Allocation:** Allocate payments against invoices while validating available payment balances, invoice outstanding balances, and customer consistency.
- **Request Validation:** Pydantic schemas, enumerated values for business statuses and payment methods, and numeric constraints for monetary amounts.
- **Error Handling:** HTTP exceptions for missing records and invalid payment allocation requests.

### Current Database Models

The application currently defines five SQLAlchemy database models:

1. `CustomerDB` — Customer master data and payment terms.
2. `SalesOrderDB` — Sales order details and order status.
3. `InvoiceDB` — Invoice information, due dates, amounts, and payment status.
4. `PaymentDB` — Incoming payment details and payment status.
5. `PaymentAllocationDB` — Allocation of payments to invoices.

### Current Development Status

The project has established the core API and database foundation for an O2C workflow. Payment allocation now includes business rules to prevent over-allocation of payments and invoices, as well as allocations between different customers.

The next stage focuses on strengthening business validations, completing and testing end-to-end O2C workflows, improving consistency across CRUD operations, and expanding the application toward a more modular, maintainable architecture.

**Note:** Customer records are now database-backed; the earlier in-memory customer management approach has been replaced with SQLAlchemy persistence. Some update and retrieval operations, particularly for payment allocations, can be expanded as development continues.


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

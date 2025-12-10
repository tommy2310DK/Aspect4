# Aspect4 Order API

A FastAPI-based application that wraps the Aspect4 SOAP API to provide a clean, RESTful interface for fetching order statuses. This application is designed to be deployed as an Azure Container App and registered as a plugin in Microsoft Copilot Studio.

## Architecture

- **main.py**: The FastAPI application entry point, defining the API routes and schema (Pydantic models).
- **aspect4_client.py**: The core logic layer that communicates with the Aspect4 SOAP service using `zeep`.
- **Dockerfile**: Configuration for building the Docker image.
- **GetOrder.py**: (Legacy) Command-line script for testing purposes.

## API Endpoint

### `GET /orders`

Fetches a list of orders based on the improved filtering logic.

**Parameters:**
- `customer_number` (required): The customer ID (e.g., "010000020").
- `order_status`: Filter by status. Supports specific values ("Delvis leveret") or smart keywords:
    - `"Done"`: Returns only fully delivered orders.
    - `"Open"`: Returns any order that is *not* fully delivered.
- `limit`: Max number of orders to return (default: 50).
- `days`: Look back N days.
- `order_number`: Fetch a specific order.

## Local Development

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables:**
   You must set the following variables with your Aspect4 credentials:
   - `ASPECT4_USERNAME`
   - `ASPECT4_PASSWORD`

3. **Run the Server:**
   ```bash
   uvicorn main:app --reload
   ```

4. **Test the API:**
   Global to `http://localhost:8000/docs` to see the Swagger UI.

## Deployment to Azure Container Apps

1. **Build the Image:**
   ```bash
   docker build -t aspect4-api .
   ```

2. **Push to Registry:**
   Push this image to your Azure Container Registry (ACR).

3. **Deploy Container App:**
   - Create a new Container App in Azure.
   - Use the image from your ACR.
   - **Important**: Set the `ASPECT4_USERNAME` and `ASPECT4_PASSWORD` as environment variables (Secrets) in the Container App configuration.
   - Set "Ingress" to Enabled and "Target Port" to `8000`.

## Registering in Copilot Studio

1. **Get OpenAPI Spec:**
   Once running, go to `https://<your-app-url>/openapi.json`.
2. **Add Action in Copilot:**
   - Go to Copilot Studio -> Actions -> Add an action.
   - Choose "Import from URL" or copy/paste the JSON from the link above.
   - Copilot will automatically understand the inputs (`customer_number`, `status` keys like "Done"/"Open") and the output structure.

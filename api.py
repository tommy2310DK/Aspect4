from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from typing import Optional, List
from pydantic import BaseModel
import Hentkunde
import os
import sys

app = FastAPI(
    title="Aspect4 Order API",
    description="API to fetch customer orders from Aspect4",
    version="1.0.0",
    servers=[
        {"url": "https://aspect4-api-efacama5adafdvfd.westeurope-01.azurewebsites.net", "description": "Production Server"}
    ]
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Force OpenAPI version 3.0.2 for Copilot Studio compatibility
    openapi_schema["openapi"] = "3.0.2"
    
    # Helper to clean up the schema recursively
    def clean_schema(node):
        if isinstance(node, dict):
            # Fix 'anyOf' with 'null' which is standard in OpenAPI 3.1 but breaks some 3.0 parsers
            if "anyOf" in node:
                # Filter out the 'null' type
                non_null_types = [x for x in node["anyOf"] if x.get("type") != "null"]
                if len(non_null_types) == 1:
                    # If only one type remains (e.g. string), use that directly
                    node.update(non_null_types[0])
                    del node["anyOf"]
                    node["nullable"] = True
            
            for key, value in node.items():
                clean_schema(value)
        elif isinstance(node, list):
            for item in node:
                clean_schema(item)

    clean_schema(openapi_schema)
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Aspect4 Order API is running", "docs_url": "/docs", "openapi_url": "/openapi.json"}

@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "ok", "version": "1.0.0"}

@app.on_event("startup")
async def startup_event():
    if not os.path.exists(Hentkunde.WSDL):
        print(f"CRITICAL ERROR: WSDL file not found at: {Hentkunde.WSDL}", file=sys.stderr)
        # List files in current directory to help debug
        print(f"Current working directory: {os.getcwd()}", file=sys.stderr)
        print(f"Files in current directory: {os.listdir(os.getcwd())}", file=sys.stderr)

# Define response models for better documentation in Swagger
class OrderLine(BaseModel):
    varenr: str
    raw_data: dict

from typing import Union

class Order(BaseModel):
    order_number: str
    order_date: int
    order_lines: List[OrderLine]
    status_lines: List[OrderLine]

@app.get("/orders/{customer_id}", response_model=List[Order], operation_id="GetCustomerOrders", summary="Get Customer Orders")
def get_orders(
    customer_id: str = Path(..., description="The ID of the customer to fetch orders for"),
    order_number: Optional[str] = Query(None, description="Specific order number to fetch"),
    days: int = Query(30, description="Number of days to look back")
):
    """
    Fetch orders for a specific customer.
    """
    try:
        # Call the logic from your existing script
        results = Hentkunde.fetch_orders(customer_id, order_number, days)
        return results
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error fetching orders: {e}", file=sys.stderr)
        print(error_details, file=sys.stderr)
        return JSONResponse(status_code=500, content={"message": f"Internal Server Error: {str(e)}", "traceback": error_details})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

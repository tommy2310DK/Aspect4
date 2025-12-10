from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from aspect4_client import fetch_orders

app = FastAPI(
    title="Aspect4 Order API",
    description="API for fetching comprehensive order information from Aspect4, including delivery status and size-level details.",
    version="1.0.0",
    servers=[
        {"url": "https://aspect4-g7bqgchcfahfc4cq.westeurope-01.azurewebsites.net", "description": "Production Server"},
        {"url": "http://localhost:8000", "description": "Local Development"}
    ]
)

class SizeInfo(BaseModel):
    size: str
    qty: int
    ean: Optional[int] = None
    apris1: Optional[float] = None
    # Allow extra fields
    class Config:
        extra = "allow"

class OrderLine(BaseModel):
    line_number: int
    item_number: str
    order_details: Dict[str, Any]
    delivery_status: Dict[str, Any]
    sizes_ordered: List[SizeInfo]
    sizes_delivered: List[SizeInfo]
    sizes_pending: List[SizeInfo]

class Order(BaseModel):
    order_number: int
    order_date: int
    order_status: str
    within_date_filter: bool
    order_lines: List[OrderLine]

class DateFilter(BaseModel):
    min_date: int
    max_date: int

class OrderResponse(BaseModel):
    date_filter: DateFilter
    total_orders_fetched: int
    orders_with_lines: int
    orders_without_lines: int
    orders: List[Order]

@app.get("/orders", response_model=OrderResponse, operation_id="GetOrders")
async def get_orders(
    customer_number: str = Query(..., description="The customer number, e.g., '010000020'"),
    order_number: Optional[str] = Query(None, description="Specific order number to fetch"),
    days: Optional[int] = Query(None, description="Number of days in the past to search"),
    start_date: Optional[str] = Query(None, description="Start date in YYYYMMDD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYYMMDD format"),
    limit: int = Query(50, description="Maximum number of orders to return"),
    order_status: Optional[str] = Query(None, description="Filter by status: 'Done', 'Open', or specific status like 'Delvis leveret'")
):
    """
    Fetch a list of orders based on various filters.
    
    You can filter by:
    - **Customer Number** (Required)
    - **Date Range** (days or start/end date)
    - **Order Status** ("Done" for completed, "Open" for active/pending)
    - **Specific Order Number**
    """
    
    # Validate mutually exclusive parameters
    if (start_date or end_date) and days:
         raise HTTPException(status_code=400, detail="Cannot specify both date range (start_date/end_date) and days parameter")

    try:
        data = fetch_orders(
            customer_number=customer_number,
            limit=limit,
            order_number=order_number,
            order_status_filter=order_status,
            days=days,
            start_date=start_date,
            end_date=end_date
        )
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # In production, log the full error 
        print(f"Internal Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while communicating with Aspect4")


from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    # Generate the schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        servers=app.servers,
    )
    
    # Enforce OpenAPI 3.0.1 for compatibility with Microsoft Power Platform / Copilot Studio
    openapi_schema["openapi"] = "3.0.1"
    
    # Helper to recursively fix Pydantic v2 "anyOf" / type lists to OpenAPI 3.0 "nullable"
    def fix_schema_compatibility(schema_obj):
        if isinstance(schema_obj, dict):
            # Fix: type: ["string", "null"] -> type: string, nullable: true
            if "type" in schema_obj and isinstance(schema_obj["type"], list):
                if "null" in schema_obj["type"]:
                    schema_obj["nullable"] = True
                    schema_obj["type"] = [t for t in schema_obj["type"] if t != "null"][0]

            # Fix: anyOf: [{type: string}, {type: null}] -> type: string, nullable: true
            if "anyOf" in schema_obj:
                types = [x.get("type") for x in schema_obj["anyOf"] if "type" in x]
                if "null" in types and len(schema_obj["anyOf"]) == 2:
                    # Find the non-null type
                    non_null_schema = next((x for x in schema_obj["anyOf"] if x.get("type") != "null"), None)
                    if non_null_schema:
                        # Copy properties from the non-null schema
                        for k, v in non_null_schema.items():
                            schema_obj[k] = v
                        schema_obj["nullable"] = True
                        del schema_obj["anyOf"]
            
            # Recurse
            for value in schema_obj.values():
                fix_schema_compatibility(value)
        
        elif isinstance(schema_obj, list):
            for item in schema_obj:
                fix_schema_compatibility(item)

    # Apply the fix to components and paths
    fix_schema_compatibility(openapi_schema)
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

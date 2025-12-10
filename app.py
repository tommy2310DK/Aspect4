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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

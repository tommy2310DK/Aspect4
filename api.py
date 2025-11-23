import os
import sys
from fastapi import FastAPI, Query
from typing import Optional, List, Union
from pydantic import BaseModel
import Hentkunde

app = FastAPI(
    title="Aspect4 Order API",
    description="API to fetch customer orders from Aspect4",
    version="1.0.0"
)

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
    order_number: Union[str, int]
    order_date: int
    order_lines: List[OrderLine]
    status_lines: List[OrderLine]

@app.get("/orders/{customer_id}", response_model=List[Order])
def get_orders(
    customer_id: str, 
    order_number: Optional[str] = Query(None, description="Specific order number to fetch"),
    days: int = Query(30, description="Number of days to look back")
):
    """
    Fetch orders for a specific customer.
    """
    # Call the logic from your existing script
    results = Hentkunde.fetch_orders(customer_id, order_number, days)
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

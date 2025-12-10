from zeep import Client
from zeep.helpers import serialize_object
from datetime import datetime, timedelta
from decimal import Decimal
import os
import json

# Custom JSON encoder to handle Decimal and other types
def sanitize_data(data):
    """
    Recursively convert Decimal to float and datetime to ISO format string
    for JSON serialization compatibility.
    """
    if isinstance(data, list):
        return [sanitize_data(i) for i in data]
    elif isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, Decimal):
        return float(data)
    elif isinstance(data, datetime):
        return data.isoformat()
    return data

def parse_expected_delivery_date(senlv_value):
    """
    Parse expected delivery date from YYYYWWDD format.
    YYYY = Year, WW = Week number, DD = Day of week (1=Monday, 7=Sunday)
    Returns ISO date string or None if invalid.
    """
    if not senlv_value or senlv_value == 0:
        return None
    
    try:
        senlv_str = str(senlv_value)
        if len(senlv_str) != 8:
            return None
        
        year = int(senlv_str[0:4])
        week = int(senlv_str[4:6])
        day_of_week = int(senlv_str[6:8])
        
        # Calculate the date from ISO week
        # ISO week 1 is the week containing the first Thursday of the year
        jan_4 = datetime(year, 1, 4)
        week_1_monday = jan_4 - timedelta(days=jan_4.weekday())
        target_date = week_1_monday + timedelta(weeks=week-1, days=day_of_week-1)
        
        return target_date.strftime('%Y-%m-%d')
    except (ValueError, OverflowError):
        return None

def fetch_orders(
    customer_number: str,
    limit: int = 50,
    order_number: str = None,
    order_status_filter: str = None,
    days: int = None,
    start_date: str = None,
    end_date: str = None
):
    """
    Core function to fetch and process order data from Aspect4.
    """
    
    wsdl = 'EA7602RA.wsdl'
    # Ensure WSDL path is correct relative to execution context
    if not os.path.exists(wsdl):
        # try fallback to current directory or handle error
        pass 

    client = Client(wsdl)

    # Get credentials from environment variables
    username = os.environ.get('ASPECT4_USERNAME')
    password = os.environ.get('ASPECT4_PASSWORD')

    if not username or not password:
        raise ValueError("Environment variables ASPECT4_USERNAME and ASPECT4_PASSWORD must be set.")

    credentials = {'user': username, 'password': password}

    # Calculate date filter based on parameters
    now = datetime.now()
    
    min_dato = 0
    max_dato = 0

    if start_date and end_date:
        # Use provided date range
        try:
            min_dato = int(start_date)
            max_dato = int(end_date)
        except ValueError:
            raise ValueError("Dates must be in YYYYMMDD format")
    elif days:
        # Use days parameter
        past_date = now - timedelta(days=days)
        min_dato = int(past_date.strftime('%Y%m%d'))
        max_dato = int(now.strftime('%Y%m%d'))
    else:
        # Default: last 30 days
        one_month_ago = now - timedelta(days=30)
        min_dato = int(one_month_ago.strftime('%Y%m%d'))
        max_dato = int(now.strftime('%Y%m%d'))

    # Determine fetch limit (search depth)
    # If filtering by status, fetch more to ensure we find enough matches
    search_limit = limit
    if order_status_filter:
        search_limit = max(1000, limit)

    # Build order request
    order_request = {
        't01.chgto': customer_number,
        'limit': search_limit
    }

    # Add order number filter if specified
    if order_number:
        order_request['aordrenr'] = order_number

    orders = client.service.orderget(credentials, order_request)
    orders = serialize_object(orders)

    # Collect all data in a structured format
    output_data = {
        "date_filter": {
            "min_date": min_dato,
            "max_date": max_dato
        },
        "total_orders_fetched": len(orders.get('grporder', [])),
        "orders_with_lines": 0,
        "orders_without_lines": 0,
        "orders": []
    }

    for order in orders.get('grporder', []) or []:
        ordrenr = order['t01.oordre']
        ordredato = order['ordredato']
        order_status = order.get('status', '')
        
        
        # Filter by order status if specified
        if order_status_filter:
            if order_status_filter == "Done":
                if order_status != "Færdig leveret":
                    continue
            elif order_status_filter == "Open":
                if order_status == "Færdig leveret":
                    continue
            elif order_status != order_status_filter:
                continue

        # Filter by date if specified
        # If min_dato and max_dato are set (non-zero), strict filter apply
        if min_dato > 0 and max_dato > 0:
            if not (min_dato <= ordredato <= max_dato):
                continue
        
        order_data = {
            "order_number": ordrenr,
            "order_date": ordredato,
            "order_status": order_status,
            "within_date_filter": True, # Always true now since we filter above
            "order_lines": []
        }
        
        # Fetch order lines (may be empty for completed orders)
        orderlines_response = client.service.orderlinesget(credentials, {'t01.oordre': ordrenr})
        orderlines_data = serialize_object(orderlines_response)
        orderlines = orderlines_data.get('grpordline', [])
        
        # Fetch status lines (delivery status - this is the key data!)
        statuslines_response = client.service.staordlinesget(credentials, {'t01.oordre': ordrenr})
        statuslines_data = serialize_object(statuslines_response)
        statuslines = statuslines_data.get('grpstaordline', [])
        
        # Fetch size information for order lines
        orderline_sizes_response = client.service.ordlinsizeget(credentials, {'t01.oordre': ordrenr})
        orderline_sizes_data = serialize_object(orderline_sizes_response)
        orderline_sizes_raw = orderline_sizes_data.get('grpordlinsize', [])
        
        # Fetch size information for status lines
        statusline_sizes_response = client.service.stalinsizeget(credentials, {'t01.oordre': ordrenr})
        statusline_sizes_data = serialize_object(statusline_sizes_response)
        statusline_sizes_raw = statusline_sizes_data.get('grpstalinsize', [])
        
        # Create a map of order line sizes by line number
        orderline_sizes_map = {}
        for size_group in orderline_sizes_raw:
            line_num = size_group.get('t01.oorlin')
            if line_num:
                sizes = []
                for size_item in size_group.get('antalprstor2', []) or []:
                    stor = size_item.get('stor')
                    antal = size_item.get('antal')
                    if stor not in (None, "") and antal is not None:
                        try:
                            # Include all fields from size_item, not just size and qty
                            size_data = {"size": str(stor), "qty": int(antal)}
                            # Add any other fields that might exist (like delivery dates)
                            for k, v in size_item.items():
                                if k not in ('stor', 'antal') and v is not None:
                                    size_data[k] = v
                            sizes.append(size_data)
                        except Exception:
                            continue
                if sizes:
                    orderline_sizes_map[line_num] = sizes
        
        # Create a map of status line sizes by line number
        statusline_sizes_map = {}
        for size_group in statusline_sizes_raw:
            line_num = size_group.get('t01.oorlin')
            if line_num:
                sizes = []
                for size_item in size_group.get('antalprstor2', []) or []:
                    stor = size_item.get('stor')
                    antal = size_item.get('antal')
                    if stor not in (None, "") and antal is not None:
                        try:
                            # Include all fields from size_item
                            size_data = {"size": str(stor), "qty": int(antal)}
                            # Add any other fields that might exist (like delivery dates)
                            for k, v in size_item.items():
                                if k not in ('stor', 'antal') and v is not None:
                                    size_data[k] = v
                            sizes.append(size_data)
                        except Exception:
                            continue
                if sizes:
                    statusline_sizes_map[line_num] = sizes

        # Create a map of order lines by line number for reference
        orderlines_map = {}
        for orderline in orderlines:
            line_num = orderline.get('t01.oorlin')
            if line_num:
                orderlines_map[line_num] = orderline
        
        # Use status lines as the primary source (they contain delivery info)
        # Merge with order line data where available
        if statuslines:
            for statusline in statuslines:
                line_num = statusline.get('t01.oorlin')
                
                line_data = {
                    "line_number": line_num,
                    "item_number": f"{statusline['t01.felt2']}-{statusline['t01.felt3']}-{statusline['t01.felt1']}-{statusline['t01.felt5']}-{statusline['t01.felt4']}",
                    "order_details": {},
                    "delivery_status": {},
                    "sizes_ordered": [],
                    "sizes_delivered": [],
                    "sizes_pending": []
                }
                
                # Add order line details if available
                if line_num in orderlines_map:
                    orderline = orderlines_map[line_num]
                    for k, v in orderline.items():
                        if k not in ("t01.felt2", "t01.felt3", "t01.felt1", "t01.felt5", "t01.felt4", "t01.oordre", "t01.oorlin"):
                            line_data["order_details"][k] = v
                    
                    # Parse and add expected delivery date if available
                    if 't01.senlv' in orderline:
                        expected_date = parse_expected_delivery_date(orderline['t01.senlv'])
                        if expected_date:
                            line_data["order_details"]["expected_delivery_date"] = expected_date
                
                # Add delivery status fields
                for k, v in statusline.items():
                    if k not in ("t01.felt2", "t01.felt3", "t01.felt1", "t01.felt5", "t01.felt4", "t01.oordre", "t01.oorlin"):
                        line_data["delivery_status"][k] = v
                
                # Add ordered sizes (from order lines)
                if line_num in orderline_sizes_map:
                    line_data["sizes_ordered"] = orderline_sizes_map[line_num]
                
                # Add delivered sizes (from status lines)
                if line_num in statusline_sizes_map:
                    line_data["sizes_delivered"] = statusline_sizes_map[line_num]
                
                # Calculate pending/undelivered sizes
                if line_data["sizes_ordered"] and line_data["sizes_delivered"]:
                    # Create maps for easy lookup
                    ordered_map = {item["size"]: item["qty"] for item in line_data["sizes_ordered"]}
                    delivered_map = {item["size"]: item["qty"] for item in line_data["sizes_delivered"]}
                    
                    # Calculate pending for each size
                    pending = []
                    for size, ordered_qty in ordered_map.items():
                        delivered_qty = delivered_map.get(size, 0)
                        pending_qty = ordered_qty - delivered_qty
                        if pending_qty > 0:
                            pending.append({"size": size, "qty": pending_qty})
                    
                    line_data["sizes_pending"] = pending
                elif line_data["sizes_ordered"] and not line_data["sizes_delivered"]:
                    # Nothing delivered yet, all ordered sizes are pending
                    line_data["sizes_pending"] = line_data["sizes_ordered"]
    
                
                order_data["order_lines"].append(line_data)
        
        # If no status lines but we have order lines, use those
        elif orderlines:
            for orderline in orderlines:
                line_num = orderline.get('t01.oorlin')
                
                line_data = {
                    "line_number": line_num,
                    "item_number": f"{orderline['t01.felt2']}-{orderline['t01.felt3']}-{orderline['t01.felt1']}-{orderline['t01.felt5']}-{orderline['t01.felt4']}",
                    "order_details": {},
                    "delivery_status": {},
                    "sizes_ordered": [],
                    "sizes_delivered": [],
                    "sizes_pending": []
                }
                
                # Add all order line fields
                for k, v in orderline.items():
                    if k not in ("t01.felt2", "t01.felt3", "t01.felt1", "t01.felt5", "t01.felt4", "t01.oordre", "t01.oorlin"):
                        line_data["order_details"][k] = v
                
                # Parse and add expected delivery date if available
                if 't01.senlv' in orderline:
                    expected_date = parse_expected_delivery_date(orderline['t01.senlv'])
                    if expected_date:
                        line_data["order_details"]["expected_delivery_date"] = expected_date
                
                # Add ordered sizes (from order lines)
                if line_num in orderline_sizes_map:
                    line_data["sizes_ordered"] = orderline_sizes_map[line_num]
                    # If no delivery info, all ordered sizes are pending
                    line_data["sizes_pending"] = orderline_sizes_map[line_num]
                
                order_data["order_lines"].append(line_data)
        
        # Skip orders without any line data
        if not order_data["order_lines"]:
            output_data["orders_without_lines"] += 1
            continue
        
        output_data["orders_with_lines"] += 1
        output_data["orders"].append(order_data)
        
        # Stop if we have reached the requested limit
        if len(output_data["orders"]) >= limit:
            break

    # Return sanitized data (decimals -> floats, dates -> iso strings)
    return sanitize_data(output_data)

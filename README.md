# Aspect4 Order Fetcher

A Python script to fetch comprehensive order information from the Aspect4 SOAP API, including delivery status and size-level details.

## Features

- ✅ Fetch orders by customer number
- ✅ Filter by specific order number
- ✅ Date range filtering (days, start/end dates)
- ✅ Complete delivery status per order line
- ✅ Size-level breakdown with quantities
- ✅ Partial delivery detection (pending sizes)
- ✅ LLM-friendly JSON output

## Requirements

```bash
pip install zeep
```

## Usage

### Basic Syntax

```bash
python GetOrder.py <customer_number> [OPTIONS]
```

### Parameters

#### Mandatory
- `customer_number` - Customer number (e.g., "010000020")

#### Optional
- `--order_number ORDER` - Fetch specific order number
- `--days N` - Fetch orders from last N days
- `--start_date YYYYMMDD` - Start date for date range
- `--end_date YYYYMMDD` - End date for date range
- `--limit N` - Maximum number of orders to fetch (default: 50)
- `--order_status STATUS` - Filter by order delivery status

#### Order Status Values

The `--order_status` parameter filters orders by their delivery status. You can use the simplified keywords "Done" and "Open", or specific Aspect4 status strings:

| Status | Description | Use Case |
|--------|-------------|----------|
| `Done` | Alias for "Færdig leveret" | Show only fully completed orders |
| `Open` | Everything EXCEPT "Færdig leveret" | Show all active/pending orders |
| `Færdig leveret` | Fully delivered | Same as "Done" |
| `Delvis leveret` | Partially delivered | Show orders with pending items |
| `Ikke leveret` | Not delivered | Show orders awaiting delivery |

**Note:** Specific status values (like "Delvis leveret") are case-sensitive. The keywords "Done" and "Open" are added for convenience.

### Examples

#### 1. Fetch last 30 days of orders (default)
```bash
python GetOrder.py "010000020"
```

#### 2. Fetch last 180 days with limit
```bash
python GetOrder.py "010000020" --days 180 --limit 50
```

#### 3. Fetch specific order
```bash
python GetOrder.py "010000020" --order_number 1033900
```

#### 4. Fetch orders in date range
```bash
python GetOrder.py "010000020" --start_date 20250601 --end_date 20250603
```

#### 5. Filter by order status (Done / Fully delivered)
```bash
python GetOrder.py "010000020" --order_status "Done" --limit 20
```

#### 6. Filter by order status (Open / Active orders)
```bash
python GetOrder.py "010000020" --order_status "Open" --days 90
```

#### 7. Find undelivered orders (Specific status)
```bash
python GetOrder.py "010000020" --order_status "Ikke leveret"
```

#### 8. Save output to file
```bash
python GetOrder.py "010000020" --limit 10 > orders.json
```

## Output Structure

```json
{
  "date_filter": {
    "min_date": 20251105,
    "max_date": 20251205
  },
  "total_orders_fetched": 5,
  "orders_with_lines": 5,
  "orders_without_lines": 0,
  "orders": [
    {
      "order_number": 1033900,
      "order_date": 20250602,
      "order_status": "Færdig leveret",
      "within_date_filter": false,
      "order_lines": [
        {
          "line_number": 1,
          "item_number": "2601-20-0-0-700",
          "order_details": {},
          "delivery_status": {
            "t01.faktnr": 953957,
            "antal": 1,
            "brutto": 20.49,
            "apris": 20.49,
            "vartxt": "Herrebuks - jeansfacon"
          },
          "sizes_ordered": [],
          "sizes_delivered": [
            {
              "size": "120",
              "qty": 1,
              "ean": 5704771216213,
              "apris1": 20.49
            }
          ],
          "sizes_pending": []
        }
      ]
    }
  ]
}
```

## Data Fields

### Order Level
- `order_number` - Order number
- `order_date` - Order date (YYYYMMDD)
- `order_status` - Delivery status of the order (e.g., "Færdig leveret", "Delvis leveret", "Ikke leveret")
- `within_date_filter` - Whether order is within the date filter range
- `order_lines` - Array of order lines

### Order Line Level
- `line_number` - Line number within the order
- `item_number` - Product SKU
- `order_details` - Original order line details (if available)
  - `expected_delivery_date` - Expected delivery date in ISO format (YYYY-MM-DD), parsed from `t01.senlv` field
  - `status` - Line status (e.g., "I ordre", "Under ekspedition")
  - `t01.senlv` - Raw expected delivery date in YYYYWWDD format (Year-Week-Day)
  - Other order line fields
- `delivery_status` - Delivery status information
  - `t01.faktnr` - Invoice number
  - `antal` - Total quantity
  - `brutto` - Gross price
  - `apris` - Unit price
  - `vartxt` - Product description
  - `t05.far10` / `t05.far30` - Color information
  - `t06.stxtx1` - Reference number

### Size Level
- `sizes_ordered` - Sizes that were ordered (from order lines)
- `sizes_delivered` - Sizes that have been delivered (from status lines)
- `sizes_pending` - Sizes still pending delivery (calculated)

Each size entry contains:
- `size` - Size name (S, M, L, XL, etc.)
- `qty` - Quantity
- `ean` - EAN barcode
- `apris1` - Unit price

## Partial Delivery Detection

The script automatically calculates pending sizes by comparing ordered vs delivered quantities:

```json
{
  "sizes_ordered": [
    {"size": "M", "qty": 15},
    {"size": "XL", "qty": 50}
  ],
  "sizes_delivered": [
    {"size": "M", "qty": 5},
    {"size": "XL", "qty": 32}
  ],
  "sizes_pending": [
    {"size": "M", "qty": 10},
    {"size": "XL", "qty": 18}
  ]
}
```

## API Calls Per Order

The script makes 4 API calls per order:
1. `orderlinesget` - Order line details
2. `staordlinesget` - Delivery status lines
3. `ordlinsizeget` - Size breakdown for order lines
4. `stalinsizeget` - Size breakdown for status lines

## Notes

- For completed/delivered orders, `sizes_ordered` may be empty as the original order data is archived
- The script uses `staordlinesget` as the primary data source for delivery information
- Date filters apply to the order date, not delivery date
- All monetary values are in the currency specified in the order (typically EUR)
- **Expected Delivery Dates**: The `expected_delivery_date` field is automatically parsed from the `t01.senlv` field (format: YYYYWWDD where YYYY=Year, WW=Week number, DD=Day of week). This field is only available for undelivered/pending order lines.

## Error Handling

The script will exit with an error if:
- Customer number is not provided
- Both date range and days parameter are specified
- Date format is invalid (must be YYYYMMDD)

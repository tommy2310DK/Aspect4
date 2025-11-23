import os
from zeep import Client
from zeep.helpers import serialize_object
from datetime import datetime, timedelta

# BEST PRACTICE: Load these from environment variables or a config file
# import os
# WSDL = os.getenv('ASPECT4_WSDL', r'C:\Users\tom\myenv\EA7602RA.wdsl')
# USER = os.getenv('ASPECT4_USER', 'KETTOM')
# PASSWORD = os.getenv('ASPECT4_PASSWORD', 'mercedesbenz2310')

# For now, keeping them here but moved to constants at the top
import json
import argparse

# WSDL file is in the same directory as this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WSDL = os.path.join(BASE_DIR, 'EA7602RA.wsdl')
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

def load_credentials():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{CONFIG_FILE}' not found.")
        print("Please create a 'config.json' file with 'user' and 'password' keys.")
        exit(1)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{CONFIG_FILE}'.")
        exit(1)

CREDENTIALS = load_credentials()

def get_date_filters(days=30):
    """Returns min and max dates in YYYYMMDD integer format."""
    now = datetime.now()
    one_month_ago = now - timedelta(days=days)
    return int(one_month_ago.strftime('%Y%m%d')), int(now.strftime('%Y%m%d'))

def print_line_details(lines, line_type_key):
    """Helper function to print lines to avoid duplicated code."""
    items = lines.get(line_type_key, [])
    if not items:
        return

    print(f"  Found {len(items)} items in {line_type_key}:")
    
    for line in items:
        output = []
        # Use .get() to avoid crashes if fields are missing
        varenr = f"{line.get('t01.felt2', '')}-{line.get('t01.felt3', '')}-{line.get('t01.felt1', '')}-{line.get('t01.felt5', '')}-{line.get('t01.felt4', '')}"
        output.append(f"Varenr: {varenr}")

        # Exclude specific keys from the generic output
        exclude_keys = {"t01.felt2", "t01.felt3", "t01.felt1", "t01.felt5", "t01.felt4", "t01.oordre"}
        
        for k, v in line.items():
            if k not in exclude_keys:
                output.append(f"{k}: {v}")
        
        print("    " + " | ".join(output))

def main():
    parser = argparse.ArgumentParser(description='Fetch customer orders from Aspect4')
    parser.add_argument('customer', type=str, help='Customer number')
    parser.add_argument('--order', type=str, help='Order number (optional)')
    parser.add_argument('--days', type=int, default=30, help='Days to look back (default: 30)')
    args = parser.parse_args()

    try:
        client = Client(WSDL)
    except Exception as e:
        print(f"Error loading WSDL: {e}")
        return

    min_dato, max_dato = get_date_filters(args.days)

    order_request = {
        't01.chgto': args.customer,
    }
    if args.order:
        order_request['aordrenr'] = args.order

    try:
        orders_response = client.service.orderget(CREDENTIALS, order_request)
        orders = serialize_object(orders_response)
    except Exception as e:
        print(f"Error fetching orders: {e}")
        return

    # Check if 'grporder' exists before iterating
    if not orders or 'grporder' not in orders:
        print("No orders found.")
        return

    for order in orders['grporder']:
        ordrenr = order.get('t01.oordre')
        ordredato = order.get('ordredato')

        # Ensure we have data to compare
        if ordrenr and ordredato and (min_dato <= ordredato <= max_dato):
            print(f"Ordre nr: {ordrenr} ordre dato: {ordredato}")
            print('----------------------')

            # Fetch and print standard order lines
            try:
                lines_response = client.service.orderlinesget(CREDENTIALS, {'t01.oordre': ordrenr})
                lines = serialize_object(lines_response)
                print_line_details(lines, 'grpordline')
            except Exception as e:
                print(f"    Error fetching orderlines: {e}")

            # Fetch and print status order lines
            try:
                sta_lines_response = client.service.staordlinesget(CREDENTIALS, {'t01.oordre': ordrenr})
                sta_lines = serialize_object(sta_lines_response)
                print_line_details(sta_lines, 'grpstaordline')
            except Exception as e:
                print(f"    Error fetching staordlines: {e}")

            print('-----------------------\n')

if __name__ == "__main__":
    main()

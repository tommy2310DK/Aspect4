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

import sys

from decimal import Decimal

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, timedelta)):
        return str(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError (f"Type {type(obj)} not serializable")

def extract_lines(lines, line_type_key):
    """Helper function to extract lines into a list of dictionaries."""
    items = lines.get(line_type_key, [])
    if not items:
        return []

    extracted_items = []
    for line in items:
        # Construct Varenr
        varenr = f"{line.get('t01.felt2', '')}-{line.get('t01.felt3', '')}-{line.get('t01.felt1', '')}-{line.get('t01.felt5', '')}-{line.get('t01.felt4', '')}"
        
        item_data = {
            'varenr': varenr,
            'raw_data': line
        }
        extracted_items.append(item_data)
    return extracted_items

def fetch_orders(customer, order_number=None, days=30):
    """
    Fetches orders for a given customer.
    Returns a list of dictionaries (order objects).
    """
    try:
        client = Client(WSDL)
    except Exception as e:
        # In a real app, you might want to raise a specific error or return it
        print(json.dumps({"error": f"Error loading WSDL: {str(e)}"}), file=sys.stderr)
        return []

    min_dato, max_dato = get_date_filters(days)

    order_request = {
        't01.chgto': customer,
    }
    if order_number:
        order_request['aordrenr'] = order_number

    try:
        orders_response = client.service.orderget(CREDENTIALS, order_request)
        orders = serialize_object(orders_response)
    except Exception as e:
        print(json.dumps({"error": f"Error fetching orders: {str(e)}"}), file=sys.stderr)
        return []

    # Check if 'grporder' exists before iterating
    if not orders or 'grporder' not in orders:
        return []

    output_results = []

    for order in orders['grporder']:
        ordrenr = order.get('t01.oordre')
        ordredato = order.get('ordredato')

        # Ensure we have data to compare
        if ordrenr and ordredato and (min_dato <= ordredato <= max_dato):
            order_obj = {
                'order_number': ordrenr,
                'order_date': ordredato,
                'order_lines': [],
                'status_lines': []
            }

            # Fetch standard order lines
            try:
                lines_response = client.service.orderlinesget(CREDENTIALS, {'t01.oordre': ordrenr})
                lines = serialize_object(lines_response)
                order_obj['order_lines'] = extract_lines(lines, 'grpordline')
            except Exception as e:
                print(f"Error fetching orderlines for {ordrenr}: {e}", file=sys.stderr)

            # Fetch status order lines
            try:
                sta_lines_response = client.service.staordlinesget(CREDENTIALS, {'t01.oordre': ordrenr})
                sta_lines = serialize_object(sta_lines_response)
                order_obj['status_lines'] = extract_lines(sta_lines, 'grpstaordline')
            except Exception as e:
                print(f"Error fetching staordlines for {ordrenr}: {e}", file=sys.stderr)

            output_results.append(order_obj)
            
    return output_results

def run_cli():
    parser = argparse.ArgumentParser(description='Fetch customer orders from Aspect4')
    parser.add_argument('customer', type=str, help='Customer number')
    parser.add_argument('--order', type=str, help='Order number (optional)')
    parser.add_argument('--days', type=int, default=30, help='Days to look back (default: 30)')
    args = parser.parse_args()

    results = fetch_orders(args.customer, args.order, args.days)
    print(json.dumps(results, indent=2, default=json_serial))

if __name__ == "__main__":
    run_cli()

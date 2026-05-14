from django.conf import settings
from .models import Product, OrderItem
from .utils import TerminalAfricaClient

def fulfill_order(order):
    """
    Creates a shipment in Terminal Africa after payment confirmation.
    """
    try:
        shipping_address = order.shipping_address
        items = order.items.all()
        
        total_weight = 0
        max_length = 0
        max_width = 0
        total_height = 0
        
        for item in items:
            product = item.product
            qty = item.quantity
            total_weight += (product.weight * qty)
            # Estimation: stacking items vertically
            total_height += (product.height * qty)
            max_length = max(max_length, product.length)
            max_width = max(max_width, product.width)

        # Ensure we have some minimums if products don't have dimensions
        total_weight = max(total_weight, 0.1)
        max_length = max(max_length, 1.0)
        max_width = max(max_width, 1.0)
        total_height = max(total_height, 1.0)

        # Prepare data for Terminal Africa
        shipment_data = {
            "address_from": settings.DEFAULT_SENDER_ADDRESS_ID, # Assume set in settings
            "address_to": {
                "first_name": shipping_address.first_name,
                "last_name": shipping_address.last_name,
                "phone": shipping_address.phone_number,
                "email": order.user.email if order.user else "guest@example.com",
                "address": shipping_address.address_line1,
                "city": shipping_address.city,
                "state": shipping_address.state,
                "country": shipping_address.country,
            },
            "parcel": {
                "length": max_length,
                "width": max_width,
                "height": total_height,
                "weight": total_weight,
            },
            "rate": order.shipping_rate_id
        }
        
        print(f"Fulfilling order {order.id} via Terminal Africa with parcel: {shipment_data['parcel']}")
        
        if order.shipping_rate_id:
            shipment_result = TerminalAfricaClient.create_shipment(shipment_data)
            if 'data' in shipment_result and 'id' in shipment_result['data']:
                order.terminal_africa_shipment_id = shipment_result['data']['id']
                order.tracking_number = shipment_result['data'].get('tracking_number')
                order.status = 'Shipped'
                order.save()
                print(f"Shipment created: {order.terminal_africa_shipment_id}")
            else:
                print(f"Failed to create shipment: {shipment_result}")
        else:
            print("No shipping_rate_id found for order, skipping Terminal Africa shipment creation.")
            
    except Exception as e:
        print(f"Error fulfilling order: {e}")

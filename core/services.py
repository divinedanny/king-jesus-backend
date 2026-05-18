from django.conf import settings
from django.db import transaction
from .models import Product, OrderItem, Inventory, StockTransaction
from .utils import TerminalAfricaClient

def fulfill_order(order, performed_by=None):
    """
    Creates a shipment in Terminal Africa after payment confirmation
    and updates inventory.
    """
    try:
        with transaction.atomic():
            # 1. Update Inventory and create Stock Transactions
            if order.store:
                for item in order.items.all():
                    inventory, created = Inventory.objects.get_or_create(
                        store=order.store,
                        product=item.product,
                        defaults={'quantity': 0}
                    )
                    inventory.quantity -= item.quantity
                    inventory.save()
                    
                    StockTransaction.objects.create(
                        from_store=order.store,
                        product=item.product,
                        transaction_type='Sale',
                        quantity=-item.quantity,
                        performed_by=performed_by or order.user,
                        reference_id=str(order.id),
                        notes=f"Order {order.id} fulfilled via {order.order_source}"
                    )
                    
                    # Also update global stock_quantity
                    item.product.stock_quantity -= item.quantity
                    item.product.save()

            # 2. Terminal Africa Shipment Creation (Only for Web orders with shipping rate)
            if order.order_source == 'Web' and order.shipping_rate_id:
                shipping_address = getattr(order, 'shipping_address', None)
                if not shipping_address:
                    print(f"Order {order.id} is Web but has no shipping address.")
                else:
                    items = order.items.all()
                    
                    total_weight = 0
                    max_length = 0
                    max_width = 0
                    total_height = 0
                    
                    for item in items:
                        product = item.product
                        qty = item.quantity
                        total_weight += (product.weight * qty)
                        total_height += (product.height * qty)
                        max_length = max(max_length, product.length)
                        max_width = max(max_width, product.width)

                    total_weight = max(total_weight, 0.1)
                    max_length = max(max_length, 1.0)
                    max_width = max(max_width, 1.0)
                    total_height = max(total_height, 1.0)

                    shipment_data = {
                        "address_from": settings.DEFAULT_SENDER_ADDRESS_ID,
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
                    
                    print(f"Fulfilling order {order.id} via Terminal Africa")
                    
                    shipment_result = TerminalAfricaClient.create_shipment(shipment_data)
                    if 'data' in shipment_result and 'id' in shipment_result['data']:
                        order.terminal_africa_shipment_id = shipment_result['data']['id']
                        order.tracking_number = shipment_result['data'].get('tracking_number')
                        order.status = 'Shipped'
                        order.save()
                    else:
                        print(f"Failed to create shipment: {shipment_result}")
            else:
                print(f"Order {order.id} fulfills without Terminal Africa (Source: {order.order_source})")
                if order.status == 'Paid':
                    if order.order_source == 'POS':
                        order.status = 'Delivered'
                    else:
                        order.status = 'Shipped'
                    order.save()
            
    except Exception as e:
        print(f"Error fulfilling order: {e}")
        raise e

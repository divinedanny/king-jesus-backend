import json
import stripe
import uuid
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework import viewsets, permissions, filters, generics, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from .models import User, Category, Product, Order, OrderItem, ShippingAddress, Review, Wishlist, Store, Inventory, StockTransaction
from .serializers import (
    UserSerializer, CategorySerializer, ProductSerializer, OrderSerializer, 
    ReviewSerializer, WishlistSerializer, StoreSerializer, InventorySerializer, 
    StockTransactionSerializer
)
from .permissions import IsAdmin, IsManager, IsAttendant, IsCustomer

class StoreViewSet(viewsets.ModelViewSet):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [IsManager]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return super().get_permissions()

class InventoryViewSet(viewsets.ModelViewSet):
    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer
    permission_classes = [IsAttendant]
    filter_backends = [filters.SearchFilter]
    search_fields = ['product__name', 'store__name', 'product__sku', 'product__barcode_data']

    def get_queryset(self):
        queryset = Inventory.objects.all()
        store_id = self.request.query_params.get('store_id')
        if store_id:
            queryset = queryset.filter(store_id=store_id)
        return queryset

    @action(detail=False, methods=['post'], permission_classes=[IsManager])
    def transfer(self, request):
        """
        Initiate a stock transfer between stores.
        """
        product_id = request.data.get('product_id')
        from_store_id = request.data.get('from_store_id')
        to_store_id = request.data.get('to_store_id')
        quantity = int(request.data.get('quantity', 0))

        if not all([product_id, from_store_id, to_store_id, quantity > 0]):
            return Response({'error': 'Missing required fields or invalid quantity'}, status=400)

        try:
            with transaction.atomic():
                # 1. Check stock in from_store
                from_inventory = Inventory.objects.get(product_id=product_id, store_id=from_store_id)
                if from_inventory.quantity < quantity:
                    return Response({'error': 'Insufficient stock in originating store'}, status=400)

                # 2. Deduct from from_store
                from_inventory.quantity -= quantity
                from_inventory.save()

                # 3. Add to to_store (or create if doesn't exist)
                to_inventory, _ = Inventory.objects.get_or_create(
                    product_id=product_id, store_id=to_store_id,
                    defaults={'quantity': 0}
                )
                to_inventory.quantity += quantity
                to_inventory.save()

                # 4. Log Transaction
                StockTransaction.objects.create(
                    product_id=product_id,
                    from_store_id=from_store_id,
                    to_store_id=to_store_id,
                    transaction_type='Transfer',
                    quantity=quantity,
                    performed_by=request.user,
                    notes=request.data.get('notes', '')
                )

                return Response({'status': 'Transfer successful'})
        except Inventory.DoesNotExist:
            return Response({'error': 'Inventory record not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

class StockTransactionViewSet(viewsets.ModelViewSet):
    queryset = StockTransaction.objects.all()
    serializer_class = StockTransactionSerializer
    permission_classes = [IsManager]

    def perform_create(self, serializer):
        serializer.save(performed_by=self.request.user)

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class WishlistViewSet(viewsets.ModelViewSet):
    queryset = Wishlist.objects.all()
    serializer_class = WishlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def add_product(self, request):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'error': 'product_id is required'}, status=400)
        
        try:
            product = Product.objects.get(id=product_id)
            wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
            wishlist.products.add(product)
            return Response({'status': 'product added to wishlist'})
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=404)

    @action(detail=False, methods=['post'])
    def remove_product(self, request):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'error': 'product_id is required'}, status=400)
        
        try:
            product = Product.objects.get(id=product_id)
            wishlist = Wishlist.objects.get(user=request.user)
            wishlist.products.remove(product)
            return Response({'status': 'product removed from wishlist'})
        except (Product.DoesNotExist, Wishlist.DoesNotExist):
            return Response({'error': 'Product or Wishlist not found'}, status=404)

from .utils import TerminalAfricaClient, PaymentProvider, EmailNotifier
from .services import fulfill_order

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView

class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    callback_url = settings.GOOGLE_AUTH_CALLBACK_URL
    client_class = OAuth2Client

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'sku', 'barcode_data']
    ordering_fields = ['price', 'created_at']

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'by_barcode']:
            return [permissions.AllowAny()]
        return super().get_permissions()

    @action(detail=False, methods=['get'])
    def by_barcode(self, request):
        code = request.query_params.get('code')
        if not code:
            return Response({'error': 'Barcode code required'}, status=400)
        try:
            product = Product.objects.get(Q(barcode_data=code) | Q(sku=code))
            serializer = self.get_serializer(product)
            return Response(serializer.data)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=404)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def generate_barcode(self, request, pk=None):
        product = self.get_object()
        if not product.barcode_data:
            product.barcode_data = f"KJ-{uuid.uuid4().hex[:8].upper()}"
        if not product.sku:
            product.sku = f"SKU-{uuid.uuid4().hex[:6].upper()}"
        product.save()
        return Response({'barcode_data': product.barcode_data, 'sku': product.sku})

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['Admin', 'Manager']:
            return Order.objects.all()
        return Order.objects.filter(user=user)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def calculate_shipping(request):
    """
    Expects recipient address and parcel details (or items).
    """
    data = request.data
    
    # If items are provided, calculate parcel dimensions and weight
    if 'items' in data:
        total_weight = 0
        max_length = 0
        max_width = 0
        total_height = 0
        
        for item in data['items']:
            try:
                product = Product.objects.get(id=item['product_id'])
                qty = item.get('quantity', 1)
                total_weight += (product.weight * qty)
                # Estimation: stacking items vertically
                total_height += (product.height * qty)
                max_length = max(max_length, product.length)
                max_width = max(max_width, product.width)
            except Product.DoesNotExist:
                continue

        # Ensure minimums if no products found or they have no dimensions
        data['parcel'] = {
            "length": max(max_length, 1.0),
            "width": max(max_width, 1.0),
            "height": max(total_height, 1.0),
            "weight": max(total_weight, 0.1),
        }
    
    # Ensure sender address is included if not provided
    if 'address_from' not in data:
        data['address_from'] = settings.DEFAULT_SENDER_ADDRESS_ID

    result = TerminalAfricaClient.get_rates(data)
    return Response(result)

@api_view(['POST'])
@permission_classes([IsCustomer | IsAttendant])
def create_order(request):
    """
    Creates an order and returns payment initialization data.
    """
    user = request.user if request.user.is_authenticated else None
    items_data = request.data.get('items', [])
    shipping_data = request.data.get('shipping_address', {})
    payment_method = request.data.get('payment_method')
    currency = request.data.get('currency', 'NGN')
    total_amount = request.data.get('total_amount')
    shipping_rate_id = request.data.get('shipping_rate_id')
    store_id = request.data.get('store_id')
    order_source = request.data.get('order_source', 'Web')
    negotiated_discount = float(request.data.get('negotiated_discount', 0.00))

    # RBAC: Only Attendants/Managers can process POS orders or apply discounts
    if order_source == 'POS' or negotiated_discount > 0:
        if user and user.role not in ['Admin', 'Manager', 'Attendant']:
            return Response({'error': 'Unauthorized to process POS sales or apply discounts'}, status=403)

    # 1. Create Order
    order = Order.objects.create(
        user=user if order_source == 'Web' else None, # POS orders might not have a registered user
        store_id=store_id,
        order_source=order_source,
        total_amount=total_amount,
        negotiated_discount=negotiated_discount,
        currency=currency,
        payment_method=payment_method,
        status='Pending',
        shipping_rate_id=shipping_rate_id
    )

    # 2. Create Order Items
    for item in items_data:
        product = Product.objects.get(id=item['product_id'])
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=item['quantity'],
            price_at_purchase=item['price']
        )

    # 3. Create Shipping Address (only for Web orders)
    if order_source == 'Web':
        ShippingAddress.objects.create(
            order=order,
            **shipping_data
        )

    # 4. Initialize Payment / Fulfill if POS
    if payment_method == 'Paystack':
        # Local payment
        ref = str(order.id)
        email = user.email if user else shipping_data.get('email', 'guest@example.com')
        paystack_response = PaymentProvider.create_paystack_payment(total_amount, email, ref)
        return Response({
            'order_id': order.id,
            'payment_data': paystack_response
        })
    elif payment_method == 'Stripe':
        # International payment
        intent = PaymentProvider.create_stripe_payment(total_amount, currency, str(order.id))
        return Response({
            'order_id': order.id,
            'client_secret': intent.client_secret
        })
    elif payment_method in ['Cash', 'POS-Terminal', 'Transfer']:
        # POS payment - fulfill immediately
        order.status = 'Paid'
        order.save()
        fulfill_order(order)
        return Response({
            'order_id': order.id,
            'status': 'Order recorded and fulfilled'
        })
    
    return Response({'error': 'Invalid payment method'}, status=400)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def whatsapp_order(request):
    """
    Records a WhatsApp-pending order and returns the pre-filled link.
    """
    user = request.user if request.user.is_authenticated else None
    items_data = request.data.get('items', [])
    shipping_data = request.data.get('shipping_address', {})
    currency = request.data.get('currency', 'NGN')
    total_amount = request.data.get('total_amount')

    # 1. Create Order
    order = Order.objects.create(
        user=user,
        total_amount=total_amount,
        currency=currency,
        payment_method='WhatsApp-Pending',
        order_source='Web',
        status='Pending'
    )

    # 2. Create Order Items and Format for Message
    items_text = ""
    for item in items_data:
        product = Product.objects.get(id=item['product_id'])
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=item['quantity'],
            price_at_purchase=item['price']
        )
        items_text += f"- {product.name} x {item['quantity']}\n"

    # 3. Create Shipping Address
    addr = ShippingAddress.objects.create(
        order=order,
        **shipping_data
    )
    address_text = f"{addr.address_line1}, {addr.city}, {addr.state}, {addr.country}"

    # 4. Generate WhatsApp Link
    name = f"{addr.first_name} {addr.last_name}"
    message = (
        f"New Order from {name}:\n"
        f"Items:\n{items_text}"
        f"Total: {total_amount} {currency}\n"
        f"Shipping Address: {address_text}"
    )
    
    from urllib.parse import quote
    encoded_message = quote(message)
    whatsapp_link = f"https://wa.me/2347049497394?text={encoded_message}"

    return Response({
        'order_id': order.id,
        'whatsapp_link': whatsapp_link
    })

@api_view(['GET'])
@permission_classes([IsAttendant])
def sales_analytics(request):
    """
    Sales data filtered by store/source.
    """
    store_id = request.query_params.get('store_id')
    source = request.query_params.get('order_source')
    start_date = request.query_params.get('start_date')
    
    queryset = Order.objects.filter(status='Paid')
    if store_id:
        queryset = queryset.filter(store_id=store_id)
    if source:
        queryset = queryset.filter(order_source=source)
    if start_date:
        queryset = queryset.filter(created_at__gte=start_date)

    total_sales = queryset.aggregate(total=Sum('total_amount'))['total'] or 0
    count = queryset.count()
    
    # Sales by source
    by_source = queryset.values('order_source').annotate(total=Sum('total_amount'))
    
    return Response({
        'total_revenue': total_sales,
        'order_count': count,
        'breakdown_by_source': by_source
    })

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def track_shipment(request, tracking_number):
    result = TerminalAfricaClient.track_shipment(tracking_number)
    return Response(result)


# Webhooks
@csrf_exempt
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def paystack_webhook(request):
    payload = request.data
    if payload['event'] == 'transaction.success':
        order_id = payload['data']['reference']
        try:
            order = Order.objects.get(id=order_id)
            if order.status != 'Paid':
                order.status = 'Paid'
                order.save()
                fulfill_order(order)
                EmailNotifier.send_order_confirmation(order)
        except Order.DoesNotExist:
            return Response(status=404)
    return Response(status=200)

@csrf_exempt
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        return HttpResponse(status=400)

    if event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
        order_id = intent['metadata'].get('order_id')
        try:
            order = Order.objects.get(id=order_id)
            if order.status != 'Paid':
                order.status = 'Paid'
                order.save()
                fulfill_order(order)
                EmailNotifier.send_order_confirmation(order)
        except Order.DoesNotExist:
            return HttpResponse(status=404)
    return HttpResponse(status=200)

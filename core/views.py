import json
import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets, permissions, filters, generics, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from .models import User, Category, Product, Order, OrderItem, ShippingAddress, Review, Wishlist
from .serializers import UserSerializer, CategorySerializer, ProductSerializer, OrderSerializer, ReviewSerializer, WishlistSerializer
# ... (rest of imports)

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
    permission_classes = [permissions.IsAdminUser]

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at']

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Order.objects.all()
        return Order.objects.filter(user=self.request.user)

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
@permission_classes([permissions.AllowAny])
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

    # 1. Create Order
    order = Order.objects.create(
        user=user,
        total_amount=total_amount,
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

    # 3. Create Shipping Address
    ShippingAddress.objects.create(
        order=order,
        **shipping_data
    )

    # 4. Initialize Payment
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
@permission_classes([permissions.AllowAny])
def track_shipment(request, tracking_number):
    # In a real scenario, tracking_number might be the terminal_africa_shipment_id
    # or we might search our database for the shipment ID associated with this tracking number.
    # For now, we proxy to Terminal Africa.
    result = TerminalAfricaClient.track_shipment(tracking_number)
    return Response(result)


# Webhooks
@csrf_exempt
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def paystack_webhook(request):
    # Verify Paystack signature here in production
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
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
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

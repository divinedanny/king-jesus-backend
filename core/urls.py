from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, CategoryViewSet, ProductViewSet, OrderViewSet, UserProfileView,
    ReviewViewSet, WishlistViewSet, StoreViewSet, InventoryViewSet, StockTransactionViewSet,
    StockTransferViewSet, StaffViewSet,
    calculate_shipping, create_order, whatsapp_order, track_shipment,
    paystack_webhook, stripe_webhook, sales_analytics
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'staff', StaffViewSet, basename='staff')
router.register(r'categories', CategoryViewSet)
router.register(r'products', ProductViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'reviews', ReviewViewSet)
router.register(r'wishlist', WishlistViewSet)
router.register(r'stores', StoreViewSet)
router.register(r'inventory', InventoryViewSet)
router.register(r'stock-transactions', StockTransactionViewSet)
router.register(r'stock-transfers', StockTransferViewSet)

urlpatterns = [
    path('user/profile/', UserProfileView.as_view(), name='user-profile'),
    path('checkout/calculate-shipping/', calculate_shipping, name='calculate-shipping'),
    path('checkout/create-order/', create_order, name='create-order'),
    path('checkout/whatsapp-order/', whatsapp_order, name='whatsapp-order'),
    path('analytics/sales/', sales_analytics, name='sales-analytics'),
    path('tracking/<str:tracking_number>/', track_shipment, name='track-shipment'),
    path('pos/product-by-barcode/', ProductViewSet.as_view({'get': 'by_barcode'}), name='pos-product-by-barcode'),
    path('payments/paystack/webhook/', paystack_webhook, name='paystack-webhook'),
    path('payments/stripe/webhook/', stripe_webhook, name='stripe-webhook'),
    path('', include(router.urls)),
]

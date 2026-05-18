from rest_framework import serializers
from .models import User, Category, Product, Order, OrderItem, ShippingAddress, Review, Wishlist, Store, Inventory, StockTransaction

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'google_id', 'date_joined')
        read_only_fields = ('id', 'date_joined')

class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = '__all__'

class InventorySerializer(serializers.ModelSerializer):
    store_name = serializers.ReadOnlyField(source='store.name')
    product_name = serializers.ReadOnlyField(source='product.name')

    class Meta:
        model = Inventory
        fields = '__all__'

class StockTransactionSerializer(serializers.ModelSerializer):
    from_store_name = serializers.ReadOnlyField(source='from_store.name')
    to_store_name = serializers.ReadOnlyField(source='to_store.name')
    product_name = serializers.ReadOnlyField(source='product.name')
    performed_by_email = serializers.ReadOnlyField(source='performed_by.email')

    class Meta:
        model = StockTransaction
        fields = '__all__'

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class ReviewSerializer(serializers.ModelSerializer):
    user_email = serializers.ReadOnlyField(source='user.email')

    class Meta:
        model = Review
        fields = ('id', 'product', 'user', 'user_email', 'rating', 'comment', 'created_at')
        read_only_fields = ('id', 'user', 'created_at')

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    reviews = ReviewSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    inventory = InventorySerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = '__all__'

    def get_average_rating(self, obj):
        return obj.average_rating

class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')

    class Meta:
        model = OrderItem
        fields = '__all__'

class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = '__all__'

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    shipping_address = ShippingAddressSerializer(read_only=True)
    store_name = serializers.ReadOnlyField(source='store.name')

    class Meta:
        model = Order
        fields = '__all__'

class WishlistSerializer(serializers.ModelSerializer):
    products = ProductSerializer(many=True, read_only=True)

    class Meta:
        model = Wishlist
        fields = ('id', 'user', 'products', 'updated_at')
        read_only_fields = ('id', 'user')

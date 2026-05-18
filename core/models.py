import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = [
        ('Admin', 'Super Admin'),
        ('Manager', 'Store Manager'),
        ('Attendant', 'Store Attendant'),
        ('Customer', 'Customer'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    google_id = models.CharField(max_length=255, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Customer')
    
    # Use email as username
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.email} ({self.role})"

class Store(models.Model):
    LOCATION_TYPES = [
        ('Warehouse', 'Main Warehouse'),
        ('Retail', 'Retail Branch'),
        ('Popup', 'Pop-up Store'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPES, default='Retail')
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=100, unique=True, null=True, blank=True)
    barcode_data = models.CharField(max_length=255, blank=True, null=True)
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2) # Base Price
    currency = models.CharField(max_length=3, choices=[('NGN', 'Naira'), ('USD', 'US Dollar')])
    stock_quantity = models.IntegerField(default=0) # Total stock (legacy)
    images = models.JSONField(default=list) # Array of URLs
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Physical properties for shipping
    length = models.FloatField(default=0.0) # in cm
    width = models.FloatField(default=0.0)  # in cm
    height = models.FloatField(default=0.0) # in cm
    weight = models.FloatField(default=0.0) # in kg

    @property
    def average_rating(self):
        reviews = self.reviews.all()
        if not reviews:
            return 0
        return sum(r.rating for r in reviews) / len(reviews)

    def __str__(self):
        return self.name

class Inventory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='inventory')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory')
    quantity = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Inventories"
        unique_together = ('store', 'product')

    def __str__(self):
        return f"{self.product.name} @ {self.store.name}: {self.quantity}"

class StockTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('Sale', 'Sale'),
        ('Transfer', 'Transfer'),
        ('Adjustment', 'Stock Adjustment'),
        ('Return', 'Customer Return'),
        ('Restock', 'Restock'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_transactions')
    from_store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True, related_name='outgoing_transactions')
    to_store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True, related_name='incoming_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField() # Positive for increase, negative for decrease
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reference_id = models.CharField(max_length=255, blank=True, null=True) # e.g. Order ID or Transfer ID
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type}: {self.product.name} ({self.quantity})"

class StockTransfer(models.Model):
    STATUS_CHOICES = [
        ('Initiated', 'Initiated (In-Transit)'),
        ('Received', 'Received'),
        ('Cancelled', 'Cancelled'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    from_store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='initiated_transfers')
    to_store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='received_transfers')
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Initiated')
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='initiated_transfers')
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_transfers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Transfer {self.id}: {self.product.name} ({self.quantity}) from {self.from_store.name} to {self.to_store.name}"

class Order(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('Paystack', 'Paystack'),
        ('Stripe', 'Stripe'),
        ('WhatsApp-Pending', 'WhatsApp-Pending'),
        ('Cash', 'Cash'),
        ('POS-Terminal', 'POS Terminal'),
        ('Transfer', 'Bank Transfer'),
    ]
    SOURCE_CHOICES = [
        ('Web', 'Online Store'),
        ('POS', 'Point of Sale'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    order_source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='Web')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    negotiated_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    shipping_rate_id = models.CharField(max_length=255, blank=True, null=True)
    terminal_africa_shipment_id = models.CharField(max_length=255, blank=True, null=True)
    tracking_number = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.id} ({self.order_source})"

class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

class ShippingAddress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipping_address')
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)

    class Meta:
        verbose_name_plural = "Shipping Addresses"

    def __str__(self):
        return f"{self.first_name} {self.last_name}, {self.city}"

class Review(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')

    def __str__(self):
        return f"{self.user.email} - {self.product.name} - {self.rating}"

class Wishlist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wishlist')
    products = models.ManyToManyField(Product, related_name='wishlisted_by')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wishlist of {self.user.email}"

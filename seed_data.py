import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import Category, Product, User, Store, Inventory

def seed_data():
    # Superuser
    if not User.objects.filter(email='admin@kingjesus.com').exists():
        User.objects.create_superuser(username='admin', email='admin@kingjesus.com', password='Admin@123456')
        print("Superuser created successfully.")

    # Stores
    warehouse, _ = Store.objects.get_or_create(
        name='Main Warehouse', 
        defaults={'location_type': 'Warehouse', 'address': '123 Warehouse Way', 'city': 'Lagos'}
    )
    retail_lagos, _ = Store.objects.get_or_create(
        name='Lagos Retail Branch', 
        defaults={'location_type': 'Retail', 'address': '456 Retail Road', 'city': 'Lagos'}
    )
    print("Stores created/retrieved.")

    # Categories
    shirts, _ = Category.objects.get_or_create(name='Shirts', slug='shirts')
    accessories, _ = Category.objects.get_or_create(name='Accessories', slug='accessories')
    hoodies, _ = Category.objects.get_or_create(name='Hoodies', slug='hoodies')

    # Products
    products_data = [
        {
            'name': 'Grace T-Shirt',
            'sku': 'SHIRT-GRACE-001',
            'barcode_data': 'KJ-SH-GR-001',
            'description': 'A premium cotton t-shirt with a "Grace" print.',
            'price': 5000.00,
            'currency': 'NGN',
            'stock_quantity': 50,
            'category': shirts,
            'images': ['https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&q=80&w=1000'],
            'length': 30, 'width': 25, 'height': 2, 'weight': 0.3
        },
        {
            'name': 'Faith Hoodie',
            'sku': 'HOOD-FAITH-001',
            'barcode_data': 'KJ-HD-FA-001',
            'description': 'Stay warm and stylish with the Faith Hoodie.',
            'price': 15000.00,
            'currency': 'NGN',
            'stock_quantity': 30,
            'category': hoodies,
            'images': ['https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&q=80&w=1000'],
            'length': 35, 'width': 30, 'height': 5, 'weight': 0.6
        },
        {
            'name': 'Cross Keychain',
            'sku': 'ACC-CROSS-001',
            'barcode_data': 'KJ-AC-CR-001',
            'description': 'A simple yet meaningful cross keychain.',
            'price': 1000.00,
            'currency': 'NGN',
            'stock_quantity': 100,
            'category': accessories,
            'images': ['https://images.unsplash.com/photo-1590483734748-361463c4424c?auto=format&fit=crop&q=80&w=1000'],
            'length': 5, 'width': 5, 'height': 1, 'weight': 0.05
        },
        {
            'name': 'International Grace T-Shirt',
            'sku': 'INT-SHIRT-GRACE-001',
            'barcode_data': 'KJ-INT-SH-GR-001',
            'description': 'A premium cotton t-shirt with a "Grace" print (USD version).',
            'price': 25.00,
            'currency': 'USD',
            'stock_quantity': 50,
            'category': shirts,
            'images': ['https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&q=80&w=1000'],
            'length': 30, 'width': 25, 'height': 2, 'weight': 0.3
        }
    ]

    for item in products_data:
        name = item.pop('name')
        product, created = Product.objects.update_or_create(name=name, defaults=item)
        
        # Seed Inventory
        # Distribution: 70% Warehouse, 30% Retail
        warehouse_qty = int(product.stock_quantity * 0.7)
        retail_qty = product.stock_quantity - warehouse_qty
        
        Inventory.objects.update_or_create(
            store=warehouse, product=product, 
            defaults={'quantity': warehouse_qty}
        )
        Inventory.objects.update_or_create(
            store=retail_lagos, product=product, 
            defaults={'quantity': retail_qty}
        )

    print("Seed data updated with Multi-Store support successfully.")

if __name__ == '__main__':
    seed_data()

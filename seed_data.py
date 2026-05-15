import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import Category, Product

def seed_data():
    # Categories
    shirts, _ = Category.objects.get_or_create(name='Shirts', slug='shirts')
    accessories, _ = Category.objects.get_or_create(name='Accessories', slug='accessories')
    hoodies, _ = Category.objects.get_or_create(name='Hoodies', slug='hoodies')

    # Products
    Product.objects.get_or_create(
        name='Grace T-Shirt',
        description='A premium cotton t-shirt with a "Grace" print.',
        price=5000.00,
        currency='NGN',
        stock_quantity=50,
        category=shirts,
        images=['https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&q=80&w=1000'],
        length=30, width=25, height=2, weight=0.3
    )

    Product.objects.get_or_create(
        name='Faith Hoodie',
        description='Stay warm and stylish with the Faith Hoodie.',
        price=15000.00,
        currency='NGN',
        stock_quantity=30,
        category=hoodies,
        images=['https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&q=80&w=1000'],
        length=35, width=30, height=5, weight=0.6
    )

    Product.objects.get_or_create(
        name='Cross Keychain',
        description='A simple yet meaningful cross keychain.',
        price=1000.00,
        currency='NGN',
        stock_quantity=100,
        category=accessories,
        images=['https://images.unsplash.com/photo-1590483734748-361463c4424c?auto=format&fit=crop&q=80&w=1000'],
        length=5, width=5, height=1, weight=0.05
    )

    Product.objects.get_or_create(
        name='International Grace T-Shirt',
        description='A premium cotton t-shirt with a "Grace" print (USD version).',
        price=25.00,
        currency='USD',
        stock_quantity=50,
        category=shirts,
        images=['https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&q=80&w=1000'],
        length=30, width=25, height=2, weight=0.3
    )

    print("Seed data created successfully.")

if __name__ == '__main__':
    seed_data()

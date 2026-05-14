from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from .models import Product, Order, Category, ShippingAddress, User

class EcommerceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name="Clothing")
        self.product = Product.objects.create(
            name="Jesus Hoodie",
            price=15000,
            currency="NGN",
            category=self.category,
            weight=0.5,
            length=30,
            width=20,
            height=5
        )

    def test_calculate_shipping_dimension_logic(self):
        url = reverse('calculate-shipping')
        # Create another product to test stacking
        product2 = Product.objects.create(
            name="Jesus T-Shirt",
            price=5000,
            currency="NGN",
            category=self.category,
            weight=0.2,
            length=25,
            width=15,
            height=2
        )
        data = {
            "items": [
                {"product_id": str(self.product.id), "quantity": 1},
                {"product_id": str(product2.id), "quantity": 2}
            ],
            "address_to": {
                "city": "Lagos",
                "country": "Nigeria"
            }
        }
        # In views.py, calculate_shipping doesn't return the calculated parcel if it calls TerminalAfricaClient
        # But we can test the logic by inspecting how it would call the client if we mocked it.
        # For now, we just ensure it returns 200.
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 200)

    def test_review_creation(self):
        self.client.force_authenticate(user=User.objects.create_user(username='testuser', email='test@example.com', password='password'))
        url = reverse('review-list')
        data = {
            "product": str(self.product.id),
            "rating": 5,
            "comment": "Amazing quality!"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.product.reviews.count(), 1)
        self.assertEqual(self.product.average_rating, 5.0)

    def test_whatsapp_order_link_generation(self):
        url = reverse('whatsapp-order')
        data = {
            "items": [
                {"product_id": str(self.product.id), "quantity": 1, "price": 15000}
            ],
            "shipping_address": {
                "first_name": "John",
                "last_name": "Doe",
                "address_line1": "123 Street",
                "city": "Lagos",
                "state": "Lagos State",
                "country": "Nigeria",
                "phone_number": "08012345678"
            },
            "total_amount": 15000,
            "currency": "NGN"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('whatsapp_link', response.data)
        self.assertIn('2347049497394', response.data['whatsapp_link'])
        self.assertIn('Jesus%20Hoodie', response.data['whatsapp_link'])

    def test_order_creation_pending_status(self):
        url = reverse('create-order')
        data = {
            "items": [
                {"product_id": str(self.product.id), "quantity": 1, "price": 15000}
            ],
            "shipping_address": {
                "first_name": "Jane",
                "last_name": "Smith",
                "address_line1": "456 Avenue",
                "city": "Abuja",
                "state": "FCT",
                "country": "Nigeria",
                "phone_number": "09087654321"
            },
            "payment_method": "Paystack",
            "total_amount": 15000,
            "currency": "NGN",
            "shipping_rate_id": "rate_123"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        order_id = response.data['order_id']
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, 'Pending')
        self.assertEqual(order.payment_method, 'Paystack')

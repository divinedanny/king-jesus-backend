import requests
import stripe
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from paystackapi.paystack import Paystack

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Initialize Paystack
paystack = Paystack(secret_key=settings.PAYSTACK_SECRET_KEY)

class TerminalAfricaClient:
    BASE_URL = "https://api.terminal.africa/v1"
    HEADERS = {
        "Authorization": f"Bearer {settings.TERMINAL_AFRICA_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    @classmethod
    def get_rates(cls, data):
        """
        data expected: sender_address, recipient_address, parcel
        """
        response = requests.post(f"{cls.BASE_URL}/rates", json=data, headers=cls.HEADERS)
        return response.json()

    @classmethod
    def create_shipment(cls, data):
        """
        data expected: address_from, address_to, parcel, rate, etc.
        """
        response = requests.post(f"{cls.BASE_URL}/shipments", json=data, headers=cls.HEADERS)
        return response.json()

    @classmethod
    def track_shipment(cls, shipment_id):
        response = requests.get(f"{cls.BASE_URL}/track/{shipment_id}", headers=cls.HEADERS)
        return response.json()

class EmailNotifier:
    @staticmethod
    def send_order_confirmation(order):
        subject = f"Order Confirmation - {order.id}"
        # In a real app, use templates. For now, a simple text message.
        message = f"Thank you for your order {order.id}.\nTotal: {order.total_amount} {order.currency}\nStatus: {order.status}"
        
        # If no email is found, we might skip or log
        email_to = order.user.email if (order.user and order.user.email) else None
        
        if email_to:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email_to],
                fail_silently=True,
            )

class PaymentProvider:
    @staticmethod
    def create_paystack_payment(amount, email, reference):
        # Paystack amount is in kobo
        response = paystack.transaction.initialize(
            reference=reference,
            amount=int(amount * 100),
            email=email,
        )
        return response

    @staticmethod
    def create_stripe_payment(amount, currency, order_id):
        # Stripe amount is in cents
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),
            currency=currency.lower(),
            metadata={'order_id': order_id}
        )
        return intent

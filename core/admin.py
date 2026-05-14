from django.contrib import admin
from .models import User, Category, Product, Order, OrderItem, ShippingAddress, Review, Wishlist
from .services import fulfill_order

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('product__name', 'user__email', 'comment')

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'updated_at')
    search_fields = ('user__email',)
    filter_horizontal = ('products',)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'full_name', 'is_staff', 'date_joined')
    search_fields = ('email', 'full_name')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'currency', 'stock_quantity', 'category')
    list_filter = ('category', 'currency')
    search_fields = ('name', 'description')

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

class ShippingAddressInline(admin.StackedInline):
    model = ShippingAddress

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'total_amount', 'currency', 'status', 'payment_method', 'created_at')
    list_filter = ('status', 'payment_method', 'currency')
    inlines = [OrderItemInline, ShippingAddressInline]
    actions = ['trigger_fulfillment']

    def trigger_fulfillment(self, request, queryset):
        for order in queryset:
            if order.status == 'Paid':
                fulfill_order(order)
                self.message_user(request, f"Fulfillment triggered for order {order.id}")
            else:
                self.message_user(request, f"Order {order.id} is not marked as Paid. Skipping.", level='warning')
    trigger_fulfillment.short_description = "Trigger fulfillment via Terminal Africa"

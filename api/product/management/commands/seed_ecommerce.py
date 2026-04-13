from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import random
import string

from api.vendor.models import Vendor, VendorPlan, VendorSubscription
from api.product.models import Categories, Brand, Product, ProductEvent, EventType
from api.wishlist.models import ProductWishlist

User = get_user_model()

def random_string(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

class Command(BaseCommand):
    help = 'Seeds the database with dummy E-Commerce data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting E-Commerce Seed (High Volume)...')

        # 1. Create a Primary Customer User
        customer_email = 'petlover_seed@petnabor.dev'
        customer_user, _ = User.objects.get_or_create(email=customer_email, defaults={
            'first_name': 'Seed',
            'last_name': 'Customer',
            'user_type': 'individual',
            'phone': f'+15550000000'
        })
        if not customer_user.has_usable_password():
            customer_user.set_password('password123')
            customer_user.save()

        # 2. Setup Vendor Plans
        basic_plan, _ = VendorPlan.objects.get_or_create(name='Basic Plan', defaults={
            'price': Decimal('0.00'),
            'max_products': 50,
            'has_category_top_slot': False
        })
        pro_plan, _ = VendorPlan.objects.get_or_create(name='Pro Vendor', defaults={
            'price': Decimal('29.99'),
            'max_products': 500,
            'has_category_top_slot': True,
            'has_advanced_analytics': True
        })
        plans = [basic_plan, pro_plan]

        # 3. Create 20 Vendors
        self.stdout.write('Generating 20 Vendors...')
        vendors = []
        for i in range(20):
            v_user, _ = User.objects.get_or_create(email=f'vendor{i}_{random_string(4)}@petnabor.dev', defaults={
                'first_name': f'Vendor',
                'last_name': f'{i}',
                'user_type': 'business',
                'phone': f'+1555{random.randint(1000000, 9999999)}'
            })
            if not v_user.has_usable_password():
                v_user.set_password('password123')
                v_user.save()

            plan = random.choice(plans)
            vendor, created = Vendor.objects.get_or_create(user=v_user, defaults={
                'business_name': f'Pet Store {i} {random_string(4)}',
                'descriptions': 'A premium pet store.',
                'contact_number': v_user.phone,
                'address_street': f'{random.randint(100, 999)} Seed St',
                'city': 'Seedville',
                'state': 'CA',
                'zipcode': '90000',
                'plan': plan,
            })
            if created:
                VendorSubscription.objects.create(
                    vendor=vendor,
                    plan=plan,
                    status='active',
                    started_at=timezone.now(),
                    expires_at=timezone.now() + timezone.timedelta(days=365)
                )
            vendors.append(vendor)

        # 4. Create 40 Categories
        self.stdout.write('Generating 40 Categories...')
        categories = []
        for i in range(40):
            cat, _ = Categories.objects.get_or_create(name=f'Category {i} {random_string(4)}', defaults={
                'description': 'A generated category.'
            })
            categories.append(cat)

        # 5. Create 30 Brands
        self.stdout.write('Generating 30 Brands...')
        brands = []
        for i in range(30):
            brand, _ = Brand.objects.get_or_create(name=f'Brand {i} {random_string(4)}', defaults={
                'description': 'A generated brand.'
            })
            brands.append(brand)

        # 6. Create 50 Products
        self.stdout.write('Generating 50 Products...')
        products = []
        for i in range(50):
            p, _ = Product.objects.get_or_create(
                name=f'Gen Product {i} {random_string(4)}', 
                vendor=random.choice(vendors), 
                defaults={
                    'category': random.choice(categories),
                    'brand': random.choice(brands),
                    'price': Decimal(f"{random.randint(5, 100)}.{random.choice(['00', '50', '99'])}"),
                    'description': "A fantastic generated product."
                }
            )
            products.append(p)

        # 7. Generate Random Interactions & Wishlists
        self.stdout.write('Generating Events and Wishlists...')
        # Wishlist 10 random products for the customer
        for p in random.sample(products, 10):
            ProductWishlist.objects.get_or_create(user=customer_user, product=p)

        # Generate 200 random product events
        for _ in range(200):
            p = random.choice(products)
            event_type = random.choice([EventType.VIEW, EventType.VIEW, EventType.IMPRESSION, EventType.CLICK])
            dt = timezone.now() - timezone.timedelta(days=random.randint(0, 29), hours=random.randint(0, 23))
            
            event = ProductEvent(
                product=p,
                user=customer_user if random.choice([True, False]) else None,
                event_type=event_type,
            )
            event.save()
            # Override created_at for historical mock data
            ProductEvent.objects.filter(id=event.id).update(created_at=dt)

        self.stdout.write(self.style.SUCCESS('Successfully seeded High-Volume E-Commerce dummy data!'))

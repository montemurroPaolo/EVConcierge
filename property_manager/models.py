"""
Property Manager models for EVConcierge.

Covers: UserProfile, Properties, Categories, Services, Bookings,
        Orders, Instructions, Experiences, Co-hosting, Push Notifications,
        Chat, Specials, Feedback, Promo Codes, Translations, Daily Views.
"""

import datetime
import os
import random
import string
import uuid

from django.conf import settings
from django.db import models
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify

# Save built-in 'property' before model fields shadow it
_property = property


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def generate_random_password(length=8):
    """Generate a random password for property instructions."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(length))


def profile_photo_path(instance, filename):
    """Generate a path for profile photos."""
    ext = filename.split('.')[-1]
    filename = f"{instance.user.username}_{instance.id}.{ext}"
    return os.path.join('profile_photos', filename)


def property_image_path(instance, filename):
    """Generate path for property images: property_images/{id}/{unique}.ext"""
    property_id = instance.property.id
    ext = filename.split('.')[-1]
    new_filename = f"{property_id}_{uuid.uuid4().hex}.{ext}"
    return os.path.join('property_images', str(property_id), new_filename)


def geocode_address(address):
    """Geocode an address to lat/long coordinates."""
    try:
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="geoapiExercises")
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
    except ImportError:
        pass
    except Exception as e:
        print(f"Error geocoding: {e}")
    return None, None


# ---------------------------------------------------------------------------
# User Profile
# ---------------------------------------------------------------------------

class UserProfile(models.Model):
    SUBSCRIPTION_PLANS = [
        ('free', 'Free'),
        ('casual_renter', 'Casual Renter'),
        ('property_manager', 'Property Manager'),
        ('big_boss', 'Big Boss'),
    ]

    LANGUAGE_CHOICES = [
        ('original', 'Original'),
        ('eng', 'English'),
        ('it', 'Italian'),
        ('de', 'German'),
        ('fr', 'French'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile',
    )
    bio = models.TextField(blank=True, max_length=500)
    photo = models.ImageField(upload_to=profile_photo_path, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True)
    instagram = models.CharField(max_length=100, blank=True)
    subscription_plan = models.CharField(
        max_length=20, choices=SUBSCRIPTION_PLANS, default='free',
    )
    is_banned = models.BooleanField(
        default=False,
        help_text="Banned users cannot access their content and must contact support",
    )

    # Stripe integration
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    subscription_status = models.CharField(max_length=50, blank=True, null=True)
    subscription_end_date = models.DateTimeField(blank=True, null=True)

    # Gift tracking
    is_gifted = models.BooleanField(default=False)
    gift_plan = models.CharField(
        max_length=20, choices=SUBSCRIPTION_PLANS, blank=True, null=True,
    )
    gift_expiry_date = models.DateTimeField(blank=True, null=True)

    used_trial = models.BooleanField(default=False)
    pending_fb_purchase_event = models.JSONField(blank=True, null=True)
    preferred_language = models.CharField(
        max_length=8, choices=LANGUAGE_CHOICES, default='original',
    )

    def __str__(self):
        return f"{self.user.username}'s profile"

    @_property
    def email(self):
        return self.user.email


# ---------------------------------------------------------------------------
# Property
# ---------------------------------------------------------------------------

class Property(models.Model):
    """A vacation rental property managed by a property manager."""

    PROPERTY_TYPES = [
        ('apartment', 'Apartment'), ('house', 'House'), ('villa', 'Villa'),
        ('condo', 'Condominium'), ('cabin', 'Cabin'), ('cottage', 'Cottage'),
        ('other', 'Other'),
    ]
    ROOM_TYPES = [
        ('entire_place', 'Entire Place'), ('private_room', 'Private Room'),
        ('shared_room', 'Shared Room'),
    ]
    POOL_OPTIONS = [
        ('none', 'No Pool'), ('private', 'Private Pool'),
        ('shared', 'Shared Pool'),
    ]
    CANCELLATION_POLICIES = [
        ('flexible', 'Flexible'), ('moderate', 'Moderate'), ('strict', 'Strict'),
    ]
    PARKING_CHOICES = [
        ('none', 'No Parking'), ('free', 'Free Parking'), ('paid', 'Paid Parking'),
    ]
    LUGGAGE_STORAGE_CHOICES = [
        ('none', 'No Luggage Storage'), ('free', 'Free Luggage Storage'),
        ('paid', 'Paid Luggage Storage'),
    ]

    # Core
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="properties",
    )
    name = models.CharField(max_length=200)
    nickname = models.SlugField(max_length=100, unique=True, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    property_manager_name = models.CharField(max_length=100, blank=True)
    property_manager_phone = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    ai_summary = models.TextField(blank=True)

    # Existing fields kept for backward compatibility
    house_rules = models.TextField(blank=True)
    wifi_network = models.CharField(max_length=100, blank=True)
    wifi_password = models.CharField(max_length=100, blank=True)
    emergency_contacts = models.TextField(
        blank=True, help_text="Emergency phone numbers and contacts, one per line.",
    )

    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    # Property Details
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES, default='apartment', blank=True)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='entire_place', blank=True)
    capacity = models.PositiveIntegerField(default=2, blank=True)
    bedrooms = models.PositiveIntegerField(blank=True, null=True)
    beds = models.PositiveIntegerField(default=1, blank=True)
    bathrooms = models.PositiveIntegerField(blank=True, null=True)
    size = models.PositiveIntegerField(blank=True, null=True, help_text="Size in square meters")

    # Location
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    neighborhood = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True, default=None)
    longitude = models.FloatField(null=True, blank=True, default=None)
    manual_geolocalization = models.BooleanField(default=False)

    # Amenities
    has_wifi = models.BooleanField(default=False)
    has_air_conditioning = models.BooleanField(default=False)
    has_heating = models.BooleanField(default=False)
    has_kitchen = models.BooleanField(default=False)
    has_washer = models.BooleanField(default=False)
    has_netflix = models.BooleanField(default=False)
    has_barbecue = models.BooleanField(default=False)
    parking = models.CharField(max_length=10, choices=PARKING_CHOICES, default='none', blank=True)
    parking_price = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)

    # Outdoor
    pool = models.CharField(max_length=20, choices=POOL_OPTIONS, default='none', blank=True)
    has_garden = models.BooleanField(default=False)
    has_balcony = models.BooleanField(default=False)

    # Booking & Rules
    check_in_time = models.TimeField(default=datetime.time(16, 0), blank=True, null=True)
    check_out_time = models.TimeField(default=datetime.time(11, 0), blank=True, null=True)
    minimum_stay = models.PositiveIntegerField(default=1, blank=True)
    cancellation_policy = models.CharField(max_length=20, choices=CANCELLATION_POLICIES, default='moderate', blank=True)
    pets_allowed = models.BooleanField(default=False)
    smoking_allowed = models.BooleanField(default=False)
    parties_allowed = models.BooleanField(default=False)
    luggage_storage = models.CharField(max_length=10, choices=LUGGAGE_STORAGE_CHOICES, default='none', blank=True)
    luggage_storage_price = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)

    price_range = models.CharField(max_length=100, blank=True)
    ical_url = models.URLField(max_length=500, blank=True)
    instruction_password = models.CharField(max_length=20, default=generate_random_password, blank=True)
    welcome_message = models.CharField(max_length=200, default="Hello! How can I help you with this property today?", blank=True)
    view_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "properties"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @_property
    def active_bookings(self):
        today = timezone.now().date()
        return self.bookings.filter(check_in_date__lte=today, check_out_date__gte=today)

    def get_property_type_display(self):
        return dict(self.PROPERTY_TYPES).get(self.property_type, 'Not specified')

    def get_room_type_display(self):
        return dict(self.ROOM_TYPES).get(self.room_type, 'Not specified')

    def get_pool_display(self):
        return dict(self.POOL_OPTIONS).get(self.pool, 'No Pool')

    def get_cancellation_policy_display(self):
        return dict(self.CANCELLATION_POLICIES).get(self.cancellation_policy, self.cancellation_policy)

    def get_luggage_storage_display(self):
        if self.luggage_storage == 'none':
            return "No Luggage Storage"
        elif self.luggage_storage == 'free':
            return "Free Luggage Storage"
        elif self.luggage_storage == 'paid' and self.luggage_storage_price:
            return f"Luggage Storage: €{self.luggage_storage_price}/day"
        return "Luggage Storage Available"

    def get_parking_display(self):
        if self.parking == 'none':
            return "No Parking"
        elif self.parking == 'free':
            return "Free Parking"
        elif self.parking == 'paid' and self.parking_price:
            return f"Parking: €{self.parking_price}/day"
        return "Parking Available"

    def get_main_image(self):
        first_image = self.images.order_by('order').first()
        if first_image:
            return first_image.image
        return None

    def get_gallery_images(self):
        return self.images.order_by('order').all()

    def get_total_beds(self):
        total = sum(bed.quantity for bed in self.property_beds.all())
        return total if total > 0 else self.beds

    def get_total_bathrooms(self):
        total = self.property_bathrooms.count()
        return total if total > 0 else self.bathrooms

    def get_bed_details(self):
        beds_by_room = {}
        for bed in self.property_beds.all():
            room = bed.room_name or "Unspecified Room"
            if room not in beds_by_room:
                beds_by_room[room] = []
            beds_by_room[room].append(bed)
        return beds_by_room

    def get_bathroom_details(self):
        return self.property_bathrooms.all()

    def increment_view_count(self):
        Property.objects.filter(pk=self.pk).update(view_count=F('view_count') + 1)
        self.refresh_from_db(fields=['view_count'])
        DailyView.increment_daily_view('property', self.pk)

    def save(self, *args, **kwargs):
        if not self.nickname and self.name:
            base_nickname = slugify(self.name)
            nickname = base_nickname
            suffix = 1
            while Property.objects.filter(nickname=nickname).exists():
                nickname = f"{base_nickname}-{suffix}"
                suffix += 1
            self.nickname = nickname
        if self.address and (self.latitude is None or self.longitude is None):
            try:
                lat, lon = geocode_address(self.address)
                if lat and lon:
                    self.latitude = lat
                    self.longitude = lon
            except Exception as e:
                print(f"Error geocoding address: {e}")
        super().save(*args, **kwargs)

    def get_display_preferences(self):
        return {
            'font_family': 'Poppins, sans-serif',
            'font_size': '16px',
            'primary_color': '#D4AF37',
            'secondary_color': '#aaaaaa',
            'accent_color': '#D4AF37',
        }

    def can_edit(self, user):
        if not user.is_authenticated:
            return False
        if self.owner == user:
            return True
        return self.co_hosts.filter(co_host=user).exists()

    def can_delete(self, user):
        if not user.is_authenticated:
            return False
        return self.owner == user

    def is_co_host(self, user):
        if not user.is_authenticated:
            return False
        return self.co_hosts.filter(co_host=user).exists()


class PropertyPhoto(models.Model):
    """Photo attached to a property (legacy)."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="properties/photos/%Y/%m/")
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.property.name} — photo {self.order}"


class PropertyImage(models.Model):
    """Property image with computed upload paths."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=property_image_path)
    caption = models.CharField(max_length=200, blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Image for {self.property.name}"


class PropertyBed(models.Model):
    BED_TYPES = [
        ('single', 'Single Bed'), ('single_plus', '1.5 Bed'),
        ('double', 'Double Bed'), ('queen', 'Queen Bed'),
        ('king', 'King Bed'), ('sofa_bed', 'Sofa Bed'),
        ('bunk_bed', 'Bunk Bed'),
    ]
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_beds')
    bed_type = models.CharField(max_length=20, choices=BED_TYPES)
    room_name = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['room_name', 'bed_type']

    def __str__(self):
        room_part = f" in {self.room_name}" if self.room_name else ""
        qty = f"{self.quantity}x " if self.quantity > 1 else ""
        return f"{qty}{self.get_bed_type_display()}{room_part} - {self.property.name}"


class PropertyBathroom(models.Model):
    BATHROOM_TYPES = [
        ('service', 'Service/Half Bath'),
        ('full', 'Full Bathroom'),
        ('royal', 'Royal/Luxury Bath'),
    ]
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_bathrooms')
    bathroom_type = models.CharField(max_length=20, choices=BATHROOM_TYPES)
    location = models.CharField(max_length=100, blank=True)
    has_bidet = models.BooleanField(default=False)
    has_bathtub = models.BooleanField(default=False)
    has_shower = models.BooleanField(default=True)
    has_hairdryer = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['bathroom_type', 'location']

    def __str__(self):
        loc = f" ({self.location})" if self.location else ""
        return f"{self.get_bathroom_type_display()}{loc} - {self.property.name}"


# ---------------------------------------------------------------------------
# Categories & Services (existing)
# ---------------------------------------------------------------------------

class Category(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=10, blank=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["order", "name"]
        unique_together = [("property", "name")]

    def __str__(self):
        return f"{self.name} ({self.property.name})"


class ServiceItem(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to="services/photos/%Y/%m/", blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_available = models.BooleanField(default=True)
    is_special = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} (€{self.price})"

    @_property
    def linked_property(self):
        return self.category.property


# ---------------------------------------------------------------------------
# Bookings & Guest Documents (existing)
# ---------------------------------------------------------------------------

LANGUAGE_CHOICES = [
    ("en", "English"), ("it", "Italian"), ("de", "German"),
    ("fr", "French"), ("es", "Spanish"),
]


class Booking(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="bookings")
    guest_name = models.CharField(max_length=200)
    guest_email = models.EmailField(blank=True)
    guest_phone = models.CharField(max_length=50, blank=True)
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    access_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    language_preference = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default="en")
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-check_in_date"]

    def __str__(self):
        return f"{self.guest_name} @ {self.property.name} ({self.check_in_date} → {self.check_out_date})"

    @_property
    def is_current(self):
        today = timezone.now().date()
        return self.check_in_date <= today <= self.check_out_date

    @_property
    def stay_day(self):
        today = timezone.now().date()
        if today < self.check_in_date:
            return 0
        return (today - self.check_in_date).days + 1

    @_property
    def total_nights(self):
        return (self.check_out_date - self.check_in_date).days

    @_property
    def total_expenses(self):
        total = self.orders.aggregate(total=models.Sum("items__subtotal"))["total"]
        return total or 0


DOCUMENT_TYPE_CHOICES = [
    ("passport", "Passport"), ("id_card", "ID Card"),
    ("drivers_license", "Driver's License"), ("other", "Other"),
]


class GuestDocument(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES, default="passport")
    image = models.ImageField(upload_to="guests/documents/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_document_type_display()} — {self.booking.guest_name}"


# ---------------------------------------------------------------------------
# Orders (existing)
# ---------------------------------------------------------------------------

ORDER_STATUS_CHOICES = [
    ("pending", "Pending"), ("confirmed", "Confirmed"),
    ("declined", "Declined"), ("fulfilled", "Fulfilled"),
]


class Order(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default="pending")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} — {self.booking.guest_name} ({self.status})"

    @_property
    def total(self):
        return sum(item.subtotal for item in self.items.all())

    @_property
    def linked_property(self):
        return self.booking.property


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    service_item = models.ForeignKey(ServiceItem, on_delete=models.SET_NULL, null=True, related_name="order_items")
    name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} x{self.quantity}"


# ---------------------------------------------------------------------------
# Instructions (new)
# ---------------------------------------------------------------------------

class Instruction(models.Model):
    INSTRUCTION_TYPES = [
        ('reaching_property', 'Reaching Property'), ('public_transport', 'Public Transport'),
        ('parking', 'Parking'), ('checkin', 'Check-in'), ('checkout', 'Check-out'),
        ('garbage', 'Garbage'), ('wifi', 'WiFi'), ('house_rules', 'House Rules'),
        ('appliances', 'Technology'), ('useful_contacts', 'Useful Contacts'),
        ('emergency', 'Emergency Information'), ('taxes', 'Taxes'),
        ('burocracy', 'Burocracy'), ('other', 'Other'),
    ]
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='instructions')
    title = models.CharField(max_length=200)
    content = models.TextField()
    instruction_type = models.CharField(max_length=20, choices=INSTRUCTION_TYPES)
    video = models.URLField(blank=True, null=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'instruction_type']

    def __str__(self):
        return f"{self.get_instruction_type_display()} - {self.property.name}"

    def get_main_image(self):
        image = self.images.filter(is_main=True).first()
        if not image:
            image = self.images.first()
        return image


class InstructionImage(models.Model):
    instruction = models.ForeignKey(Instruction, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='instruction_images/')
    caption = models.CharField(max_length=200, blank=True)
    is_main = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"Image for {self.instruction}"

    def save(self, *args, **kwargs):
        if self.is_main:
            InstructionImage.objects.filter(
                instruction=self.instruction, is_main=True,
            ).exclude(pk=self.pk).update(is_main=False)
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Experiences (new)
# ---------------------------------------------------------------------------

class Experience(models.Model):
    CATEGORY_CHOICES = [
        ('food', 'Food'), ('nature', 'Nature'),
        ('experiences', 'Experiences'), ('services', 'Services'),
    ]
    GROUP_SIZE_CHOICES = [
        ('any_size', 'Any Size'), ('1-2', '1-2 People'), ('3-5', '3-5 People'),
        ('6-10', '6-10 People'), ('11-20', '11-20 People'), ('20+', '20+ People'),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='experiences')
    title = models.CharField(max_length=200)
    description = models.TextField()
    ai_summary = models.TextField(blank=True)
    duration = models.IntegerField(help_text="Duration in minutes", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    address = models.CharField(max_length=200, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    manual_geolocalization = models.BooleanField(default=False)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    group_size = models.CharField(max_length=20, choices=GROUP_SIZE_CHOICES, default='any_size')
    ical_url = models.URLField(max_length=500, blank=True)
    booking_method = models.TextField(blank=True)
    booking_phone = models.CharField(max_length=30, blank=True)
    booking_link = models.URLField(max_length=500, blank=True)
    referral_code = models.CharField(max_length=50, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def get_main_image(self):
        first_image = self.images.order_by('order').first()
        if first_image:
            return first_image.image
        return None

    def increment_view_count(self):
        Experience.objects.filter(pk=self.pk).update(view_count=F('view_count') + 1)
        self.refresh_from_db(fields=['view_count'])
        DailyView.increment_daily_view('experience', self.pk)

    def save(self, *args, **kwargs):
        if self.address and (not self.latitude or not self.longitude):
            try:
                lat, lon = geocode_address(self.address)
                if lat and lon:
                    self.latitude = lat
                    self.longitude = lon
            except Exception as e:
                print(f"Error geocoding address: {e}")
        super().save(*args, **kwargs)


class ExperienceImage(models.Model):
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='experience_images/')
    caption = models.CharField(max_length=200, blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Image for {self.experience.title}"


class PropertyExperience(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_experiences')
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name='property_experiences')
    distance = models.DecimalField(max_digits=5, decimal_places=2, help_text="Distance in km")
    count = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('property', 'experience')

    def __str__(self):
        return f"{self.property.name} - {self.experience.title} (Count: {self.count})"

    def save(self, *args, **kwargs):
        if (self.property.latitude and self.property.longitude and
                self.experience.latitude and self.experience.longitude):
            try:
                from .utils import calculate_distance
                self.distance = calculate_distance(
                    self.property.latitude, self.property.longitude,
                    self.experience.latitude, self.experience.longitude,
                )
            except Exception:
                pass
        if not self.pk:
            existing = PropertyExperience.objects.filter(
                property=self.property, experience=self.experience,
            ).first()
            if existing:
                existing.count += 1
                existing.save()
                return
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# External Links (new)
# ---------------------------------------------------------------------------

class ExternalLink(models.Model):
    LINK_TYPES = [
        ('social', 'Social Media'), ('website', 'Official Website'), ('other', 'Other'),
    ]
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='external_links')
    title = models.CharField(max_length=100)
    url = models.URLField()
    description = models.TextField(blank=True)
    link_type = models.CharField(max_length=20, choices=LINK_TYPES)

    def __str__(self):
        return f"{self.title} - {self.property.name}"


# ---------------------------------------------------------------------------
# Co-hosting (new)
# ---------------------------------------------------------------------------

class PropertyCoHost(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='co_hosts')
    co_host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='co_hosted_properties')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('property', 'co_host')

    def __str__(self):
        return f"{self.co_host.username} co-hosts {self.property.name}"


class CoHostRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Declined'),
    ]
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='cohost_requests')
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_cohost_requests')
    co_host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_cohost_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('property', 'co_host')

    def __str__(self):
        return f"Co-host request for {self.property.name} to {self.co_host.username} ({self.status})"


# ---------------------------------------------------------------------------
# Push Notifications (existing)
# ---------------------------------------------------------------------------

NOTIFICATION_TARGET_CHOICES = [
    ("all_guests", "All Current Guests"),
    ("specific_booking", "Specific Booking"),
]


class PushNotification(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    body = models.TextField()
    target_type = models.CharField(max_length=20, choices=NOTIFICATION_TARGET_CHOICES, default="all_guests")
    target_booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name="targeted_notifications")
    linked_item = models.ForeignKey(ServiceItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    recurring_rule = models.CharField(max_length=200, blank=True)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        status = "Sent" if self.is_sent else "Draft"
        return f"[{status}] {self.title}"


# ---------------------------------------------------------------------------
# Chat (existing + new ChatLog)
# ---------------------------------------------------------------------------

class ChatConversation(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="conversations")
    is_escalated = models.BooleanField(default=False)
    escalated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        tag = " [ESCALATED]" if self.is_escalated else ""
        return f"Chat — {self.booking.guest_name}{tag}"

    @_property
    def last_message(self):
        return self.messages.order_by("-created_at").first()


SENDER_TYPE_CHOICES = [
    ("guest", "Guest"), ("ai", "AI Assistant"), ("manager", "Property Manager"),
]


class ChatMessage(models.Model):
    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name="messages")
    sender_type = models.CharField(max_length=10, choices=SENDER_TYPE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.sender_type}] {self.content[:50]}"


class ChatLog(models.Model):
    """Log AI chat interactions for admin review."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='chat_logs')
    user_question = models.TextField()
    ai_response = models.TextField()
    session_key = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    is_authenticated = models.BooleanField(default=False)
    has_password_access = models.BooleanField(default=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Chat Log'
        verbose_name_plural = 'Chat Logs'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['property', '-created_at']),
            models.Index(fields=['session_key', '-created_at']),
        ]

    def __str__(self):
        return f"Chat for {self.property.name} at {self.created_at.strftime('%Y-%m-%d %H:%M')}: {self.user_question[:50]}..."

    def get_user_display(self):
        if self.user:
            return f"{self.user.username} (authenticated)"
        elif self.session_key:
            return f"Anonymous ({self.session_key[:8]}...)"
        return "Anonymous"


# ---------------------------------------------------------------------------
# Specials / Promotions (existing)
# ---------------------------------------------------------------------------

class Special(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="specials")
    service_item = models.ForeignKey(ServiceItem, on_delete=models.CASCADE, related_name="specials")
    title = models.CharField(max_length=200, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    linked_notification = models.ForeignKey(PushNotification, on_delete=models.SET_NULL, null=True, blank=True, related_name="specials")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        display = self.title or self.service_item.name
        return f"⭐ {display} ({self.start_date} → {self.end_date})"

    @_property
    def is_current(self):
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date and self.is_active


# ---------------------------------------------------------------------------
# Feedback (new)
# ---------------------------------------------------------------------------

class Feedback(models.Model):
    RATING_CHOICES = [(i, f'{i} - {label}') for i, label in enumerate(
        ['', 'Very Poor', 'Poor', 'Average', 'Good', 'Excellent'], 0) if i > 0]
    FEEDBACK_TYPES = [
        ('general', 'General Feedback'), ('bug_report', 'Bug Report'),
        ('feature_request', 'Feature Request'), ('user_experience', 'User Experience'),
        ('property_related', 'Property Related'), ('other', 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES, default='general')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    rating = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Feedback'
        verbose_name_plural = 'Feedback'

    def __str__(self):
        user_info = self.user.username if self.user else (self.name or 'Anonymous')
        return f"Feedback from {user_info}: {self.subject[:50]}"


# ---------------------------------------------------------------------------
# Promo Codes (new)
# ---------------------------------------------------------------------------

class PromoCode(models.Model):
    DURATION_CHOICES = [(1, '1 Month'), (3, '3 Months'), (6, '6 Months'), (12, '12 Months')]

    code = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=200)
    gift_plan = models.CharField(max_length=20, choices=UserProfile.SUBSCRIPTION_PLANS)
    duration_months = models.IntegerField(choices=DURATION_CHOICES)
    max_uses = models.PositiveIntegerField(default=1)
    current_uses = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Promo Code'
        verbose_name_plural = 'Promo Codes'

    def __str__(self):
        return f"{self.code} - {self.get_gift_plan_display()} for {self.get_duration_months_display()}"

    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False, "This promo code is not active"
        if now < self.valid_from:
            return False, "This promo code is not yet valid"
        if now > self.valid_until:
            return False, "This promo code has expired"
        if self.max_uses > 0 and self.current_uses >= self.max_uses:
            return False, "This promo code has reached its usage limit"
        return True, "Valid promo code"

    def can_be_used(self):
        valid, _ = self.is_valid()
        return valid

    def use_code(self):
        self.current_uses += 1
        self.save()


class PromoCodeUsage(models.Model):
    promo_code = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='promo_code_usages')
    used_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        unique_together = ('promo_code', 'user')
        ordering = ['-used_at']

    def __str__(self):
        return f"{self.user.username} used {self.promo_code.code}"


# ---------------------------------------------------------------------------
# Translations (new)
# ---------------------------------------------------------------------------

TRANSLATION_LANGUAGE_CHOICES = [
    ('eng', 'English'), ('it', 'Italian'), ('de', 'German'), ('fr', 'French'),
]


class PropertyTranslation(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=3, choices=TRANSLATION_LANGUAGE_CHOICES)
    title = models.CharField(max_length=60, blank=True)
    description = models.TextField(blank=True)
    ai_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('property', 'language')
        ordering = ['language']

    def __str__(self):
        return f"{self.property.name} - {self.get_language_display()}"


class InstructionTranslation(models.Model):
    instruction = models.ForeignKey(Instruction, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=3, choices=TRANSLATION_LANGUAGE_CHOICES)
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('instruction', 'language')
        ordering = ['language']

    def __str__(self):
        return f"{self.instruction.title} - {self.get_language_display()}"


class ExperienceTranslation(models.Model):
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=3, choices=TRANSLATION_LANGUAGE_CHOICES)
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    ai_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('experience', 'language')
        ordering = ['language']

    def __str__(self):
        return f"{self.experience.title} - {self.get_language_display()}"


# ---------------------------------------------------------------------------
# Daily Views (new)
# ---------------------------------------------------------------------------

class DailyView(models.Model):
    CONTENT_TYPE_CHOICES = [('property', 'Property'), ('experience', 'Experience')]

    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES)
    object_id = models.PositiveIntegerField()
    date = models.DateField()
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('content_type', 'object_id', 'date')
        ordering = ['-date']
        verbose_name = 'Daily View'
        verbose_name_plural = 'Daily Views'
        indexes = [
            models.Index(fields=['content_type', 'date']),
            models.Index(fields=['object_id', 'date']),
        ]

    def __str__(self):
        return f"{self.content_type} #{self.object_id} - {self.date}: {self.view_count} views"

    @classmethod
    def increment_daily_view(cls, content_type, object_id, date=None):
        if date is None:
            date = timezone.now().date()
        daily_view, created = cls.objects.get_or_create(
            content_type=content_type, object_id=object_id, date=date,
            defaults={'view_count': 0},
        )
        cls.objects.filter(pk=daily_view.pk).update(view_count=F('view_count') + 1)
        return daily_view


# ---------------------------------------------------------------------------
# Signal Handlers
# ---------------------------------------------------------------------------

from django.contrib.auth import get_user_model  # noqa: E402

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        UserProfile.objects.filter(user=instance).update(bio=instance.profile.bio)
    else:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=PropertyImage)
def compress_property_image(sender, instance, created, **kwargs):
    if created and instance.image:
        try:
            from .utils import compress_image
            from threading import Thread
            Thread(target=compress_image, args=(instance.image.path, 300, 85)).start()
        except Exception as e:
            print(f"Error compressing property image: {e}")


@receiver(post_save, sender=ExperienceImage)
def compress_experience_image(sender, instance, created, **kwargs):
    if created and instance.image:
        try:
            from .utils import compress_image
            from threading import Thread
            Thread(target=compress_image, args=(instance.image.path, 300, 85)).start()
        except Exception as e:
            print(f"Error compressing experience image: {e}")


@receiver(post_save, sender=InstructionImage)
def compress_instruction_image(sender, instance, created, **kwargs):
    if created and instance.image:
        try:
            from .utils import compress_image
            from threading import Thread
            Thread(target=compress_image, args=(instance.image.path, 300, 85)).start()
        except Exception as e:
            print(f"Error compressing instruction image: {e}")


@receiver(post_save, sender=UserProfile)
def compress_profile_image(sender, instance, created, **kwargs):
    if instance.photo:
        try:
            from .utils import compress_image
            from threading import Thread
            Thread(target=compress_image, args=(instance.photo.path, 300, 85)).start()
        except Exception as e:
            print(f"Error compressing profile photo: {e}")


@receiver(post_save, sender=UserProfile)
def handle_user_ban(sender, instance, **kwargs):
    if instance.is_banned:
        Property.objects.filter(owner=instance.user).update(is_active=False)
        Experience.objects.filter(owner=instance.user).update(is_active=False)


@receiver(post_save, sender=Property)
def generate_property_summary(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return
    if instance.description and (created or not instance.ai_summary):
        import threading

        def generate_summary_task():
            try:
                from .utils import generate_ai_summary
                property_data = {
                    'title': instance.name,
                    'description': instance.description,
                    'property_type': instance.property_type,
                    'room_type': instance.room_type,
                    'capacity': instance.capacity,
                    'address': instance.address,
                    'city': instance.city,
                }
                summary = generate_ai_summary(property_data, 'property')
                if summary:
                    Property.objects.filter(pk=instance.pk).update(ai_summary=summary)
            except Exception as e:
                print(f"Error generating AI summary: {e}")

        thread = threading.Thread(target=generate_summary_task)
        thread.daemon = True
        thread.start()


@receiver(post_save, sender=Experience)
def generate_experience_summary(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return
    if instance.description and (created or not instance.ai_summary):
        import threading

        def generate_summary_task():
            try:
                from .utils import generate_ai_summary
                experience_data = {
                    'title': instance.title,
                    'description': instance.description,
                    'category': instance.category,
                    'price': float(instance.price) if instance.price else None,
                }
                summary = generate_ai_summary(experience_data, 'experience')
                if summary:
                    Experience.objects.filter(pk=instance.pk).update(ai_summary=summary)
            except Exception as e:
                print(f"Error generating AI summary: {e}")

        thread = threading.Thread(target=generate_summary_task)
        thread.daemon = True
        thread.start()


@receiver(post_save, sender=PropertyImage)
def detect_duplicate_property_image(sender, instance, created, **kwargs):
    if created and instance.image:
        try:
            from .utils import detect_and_remove_duplicate_images
            from threading import Thread
            Thread(target=detect_and_remove_duplicate_images, args=(instance, created)).start()
        except Exception as e:
            print(f"Error in duplicate detection: {e}")


@receiver(post_save, sender=ExperienceImage)
def detect_duplicate_experience_image(sender, instance, created, **kwargs):
    if created and instance.image:
        try:
            from .utils import detect_and_remove_duplicate_images
            from threading import Thread
            Thread(target=detect_and_remove_duplicate_images, args=(instance, created)).start()
        except Exception as e:
            print(f"Error in duplicate detection: {e}")


@receiver(post_save, sender=InstructionImage)
def detect_duplicate_instruction_image(sender, instance, created, **kwargs):
    if created and instance.image:
        try:
            from .utils import detect_and_remove_duplicate_images
            from threading import Thread
            Thread(target=detect_and_remove_duplicate_images, args=(instance, created)).start()
        except Exception as e:
            print(f"Error in duplicate detection: {e}")

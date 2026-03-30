from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from geopy.geocoders import Nominatim
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
import os
import random
import string
from django.utils.text import slugify
import uuid
import datetime
from django.db.models import F

def generate_random_password(length=8):
    """Generate a random password for property instructions"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(length))

def profile_photo_path(instance, filename):
    """Generate a path for profile photos"""
    ext = filename.split('.')[-1]
    filename = f"{instance.user.username}_{instance.id}.{ext}"
    return os.path.join('profile_photos', filename)

def property_image_path(instance, filename):
    """
    Function to determine where property images should be stored.
    Format: property_images/property_{id}/{filename}
    """
    # Get the property id 
    property_id = instance.property.id
    # Generate a unique filename
    ext = filename.split('.')[-1]
    new_filename = f"{property_id}_{uuid.uuid4().hex}.{ext}"
    return os.path.join('property_images', str(property_id), new_filename)

class UserProfile(models.Model):
    SUBSCRIPTION_PLANS = [
        ('free', 'Free'),
        ('casual_renter', 'Casual Renter'),
        ('property_manager', 'Property Manager'),
        ('big_boss', 'Big Boss'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, max_length=500)
    photo = models.ImageField(upload_to=profile_photo_path, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True)
    instagram = models.CharField(max_length=100, blank=True)
    subscription_plan = models.CharField(max_length=20, choices=SUBSCRIPTION_PLANS, default='free')
    is_banned = models.BooleanField(default=False, help_text="Banned users cannot access their content and must contact support")
    
    # Stripe integration fields
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, help_text="Stripe customer ID")
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True, help_text="Stripe subscription ID")
    subscription_status = models.CharField(max_length=50, blank=True, null=True, help_text="Stripe subscription status")
    subscription_end_date = models.DateTimeField(blank=True, null=True, help_text="When the current subscription period ends")
    
    # Gift tracking
    is_gifted = models.BooleanField(default=False, help_text="True if subscription was manually gifted (not paid through Stripe)")
    gift_plan = models.CharField(max_length=20, choices=SUBSCRIPTION_PLANS, blank=True, null=True, help_text="Plan type for gifted subscriptions")
    gift_expiry_date = models.DateTimeField(blank=True, null=True, help_text="When the gifted subscription expires")
    
    # Subscription management fields
    used_trial = models.BooleanField(default=False, help_text="True if user has ever used a trial period")
    
    # Facebook Pixel tracking
    pending_fb_purchase_event = models.JSONField(blank=True, null=True, help_text="Temporary storage for Facebook Pixel purchase event data")
    
    # Language preference - only supported languages
    LANGUAGE_CHOICES = [
        ('original', 'Original'),
        ('eng', 'English'),
        ('it', 'Italian'),
        ('de', 'German'),
        ('fr', 'French'),
    ]
    preferred_language = models.CharField(max_length=8, choices=LANGUAGE_CHOICES, default='original', help_text="Preferred language for automatic page translation")
    
    def __str__(self):
        return f"{self.user.username}'s profile"
        
    @property
    def email(self):
        """Return the email from the associated user model"""
        return self.user.email

class Property(models.Model):
    # Property types
    PROPERTY_TYPES = [
        ('apartment', 'Apartment'),
        ('house', 'House'),
        ('villa', 'Villa'),
        ('condo', 'Condominium'),
        ('cabin', 'Cabin'),
        ('cottage', 'Cottage'),
        ('other', 'Other')
    ]
    
    # Room types
    ROOM_TYPES = [
        ('entire_place', 'Entire Place'),
        ('private_room', 'Private Room'),
        ('shared_room', 'Shared Room')
    ]
    
    # Pool options
    POOL_OPTIONS = [
        ('none', 'No Pool'),
        ('private', 'Private Pool'),
        ('shared', 'Shared Pool')
    ]
    
    # Cancellation policy
    CANCELLATION_POLICIES = [
        ('flexible', 'Flexible'),
        ('moderate', 'Moderate'),
        ('strict', 'Strict')
    ]
    
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='properties')
    title = models.CharField(max_length=60)
    nickname = models.SlugField(max_length=100, unique=True, blank=True, null=True, help_text="Unique URL-friendly name for the property (auto-generated if blank)")
    email = models.EmailField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    property_manager_name = models.CharField(max_length=100, blank=True, help_text="Property manager name (if different from owner)")
    property_manager_phone = models.CharField(max_length=30, blank=True, help_text="Property manager contact phone")
    description = models.TextField()
    ai_summary = models.TextField(blank=True, help_text="AI-generated summary of the property")
    is_active = models.BooleanField(default=True, help_text="Inactive properties are hidden when subscription limits are exceeded")
    is_featured = models.BooleanField(default=False, help_text="Featured properties are shown on the home and dashboard pages")
    
    # 🏠 Property Details
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES, default='apartment', blank=True)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='entire_place', blank=True)
    capacity = models.PositiveIntegerField(default=2, help_text="Maximum number of guests", blank=True)
    bedrooms = models.PositiveIntegerField(blank=True, null=True)
    beds = models.PositiveIntegerField(default=1, blank=True)
    bathrooms = models.PositiveIntegerField(blank=True, null=True)
    size = models.PositiveIntegerField(blank=True, null=True, help_text="Size in square meters")
    
    # 📍 Location
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100, blank=True)
    neighborhood = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True, default=None)
    longitude = models.FloatField(null=True, blank=True, default=None)
    manual_geolocalization = models.BooleanField(default=False, help_text="True if coordinates were set using manual geolocalization")
    
    # 🛋️ Key Amenities
    has_wifi = models.BooleanField(default=False)
    has_air_conditioning = models.BooleanField(default=False)
    has_heating = models.BooleanField(default=False)
    has_kitchen = models.BooleanField(default=False)
    has_washer = models.BooleanField(default=False)
    has_netflix = models.BooleanField(default=False)
    has_barbecue = models.BooleanField(default=False)
    
    # Parking Options
    PARKING_CHOICES = [
        ('none', 'No Parking'),
        ('free', 'Free Parking'),
        ('paid', 'Paid Parking'),
    ]
    parking = models.CharField(max_length=10, choices=PARKING_CHOICES, default='none', blank=True, help_text="Parking availability")
    parking_price = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, help_text="Price per day in euros (only for paid parking)")
    
    # 🌿 Outdoor and Special Features
    pool = models.CharField(max_length=20, choices=POOL_OPTIONS, default='none', blank=True)
    has_garden = models.BooleanField(default=False)
    has_balcony = models.BooleanField(default=False)
    
    # 📅 Booking and Rules
    check_in_time = models.TimeField(default=datetime.time(16, 0), blank=True, null=True)  # Default: 16:00 (4 PM)
    check_out_time = models.TimeField(default=datetime.time(11, 0), blank=True, null=True)  # Default: 11:00 AM
    minimum_stay = models.PositiveIntegerField(default=1, help_text="Minimum number of nights required to book", blank=True)
    cancellation_policy = models.CharField(max_length=20, choices=CANCELLATION_POLICIES, default='moderate', blank=True)
    pets_allowed = models.BooleanField(default=False)
    smoking_allowed = models.BooleanField(default=False)
    parties_allowed = models.BooleanField(default=False)
    
    # Luggage Storage Options
    LUGGAGE_STORAGE_CHOICES = [
        ('none', 'No Luggage Storage'),
        ('free', 'Free Luggage Storage'),
        ('paid', 'Paid Luggage Storage'),
    ]
    luggage_storage = models.CharField(max_length=10, choices=LUGGAGE_STORAGE_CHOICES, default='none', blank=True, help_text="Luggage storage availability")
    luggage_storage_price = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, help_text="Price per day in euros (only for paid storage)")
    
    price_range = models.CharField(max_length=100, blank=True, help_text="Price range per night in euros (e.g. '100€ to 300€')")
    ical_url = models.URLField(max_length=500, blank=True, help_text="Airbnb/calendar iCal URL to show availability")
    
    # Instructions password
    instruction_password = models.CharField(max_length=20, default=generate_random_password, blank=True)
    
    # Chat settings
    welcome_message = models.CharField(max_length=200, default="Hello! How can I help you with this property today?", blank=True, help_text="Custom welcome message for the chat")
    
    # View tracking
    view_count = models.PositiveIntegerField(default=0, help_text="Number of times this property page has been viewed")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def get_property_type_display(self):
        return dict(self.PROPERTY_TYPES).get(self.property_type, 'Not specified')

    def get_room_type_display(self):
        return dict(self.ROOM_TYPES).get(self.room_type, 'Not specified')

    def get_pool_display(self):
        return dict(self.POOL_OPTIONS).get(self.pool, 'No Pool')

    def get_cancellation_policy_display(self):
        """Get human-readable cancellation policy"""
        return dict(self.CANCELLATION_POLICIES).get(self.cancellation_policy, self.cancellation_policy)

    def get_luggage_storage_display(self):
        """Get human-readable luggage storage information"""
        if self.luggage_storage == 'none':
            return "No Luggage Storage"
        elif self.luggage_storage == 'free':
            return "Free Luggage Storage"
        elif self.luggage_storage == 'paid' and self.luggage_storage_price:
            return f"Luggage Storage: €{self.luggage_storage_price}/day"
        elif self.luggage_storage == 'paid':
            return "Paid Luggage Storage"
        else:
            return "Luggage Storage Available"

    def get_parking_display(self):
        """Get human-readable parking information"""
        if self.parking == 'none':
            return "No Parking"
        elif self.parking == 'free':
            return "Free Parking"
        elif self.parking == 'paid' and self.parking_price:
            return f"Parking: €{self.parking_price}/day"
        elif self.parking == 'paid':
            return "Paid Parking"
        else:
            return "Parking Available"

    def get_main_image(self):
        """Get the main image for the property, returning None if no images exist"""
        # Use the first ordered image if available
        first_image = self.images.order_by('order').first()
        if first_image:
            return first_image.image
        return None

    def get_gallery_images(self):
        """Get all property images for gallery display"""
        return self.images.order_by('order').all()

    def get_total_beds(self):
        """Calculate total number of beds from PropertyBed instances"""
        total = sum(bed.quantity for bed in self.property_beds.all())
        return total if total > 0 else self.beds  # fallback to old field if no detailed beds
    
    def get_total_bathrooms(self):
        """Calculate total number of bathrooms from PropertyBathroom instances"""
        total = self.property_bathrooms.count()
        return total if total > 0 else self.bathrooms  # fallback to old field if no detailed bathrooms
    
    def get_bed_details(self):
        """Get detailed bed information grouped by room"""
        beds_by_room = {}
        for bed in self.property_beds.all():
            room = bed.room_name or "Unspecified Room"
            if room not in beds_by_room:
                beds_by_room[room] = []
            beds_by_room[room].append(bed)
        return beds_by_room
    
    def get_bathroom_details(self):
        """Get detailed bathroom information"""
        return self.property_bathrooms.all()

    def increment_view_count(self):
        """Increment the view count for this property"""
        # Use F() to avoid race conditions and update directly in the database
        Property.objects.filter(pk=self.pk).update(view_count=F('view_count') + 1)
        # Refresh the instance to get the updated value
        self.refresh_from_db(fields=['view_count'])
        
        # Also track daily views
        from .models import DailyView
        DailyView.increment_daily_view('property', self.pk)

    def save(self, *args, **kwargs):
        # Generate a nickname if one is not provided
        if not self.nickname and self.title:
            base_nickname = slugify(self.title)
            nickname = base_nickname
            suffix = 1
            
            # Check if this nickname exists, if so, add numeric suffix
            while Property.objects.filter(nickname=nickname).exists():
                nickname = f"{base_nickname}-{suffix}"
                suffix += 1
            
            self.nickname = nickname
            
        # Only geocode if we have an address but no coordinates
        if self.address and (self.latitude is None or self.longitude is None):
            try:
                latitude, longitude = geocode_address(self.address)
                if latitude and longitude:
                    self.latitude = latitude
                    self.longitude = longitude
            except Exception as e:
                print(f"Error geocoding address: {e}")
        super().save(*args, **kwargs)
        
    def get_display_preferences(self):
        """
        Return a default display preferences dictionary
        This is used for styling the property detail page
        """
        return {
            'font_family': 'Poppins, sans-serif',
            'font_size': '16px',
            'primary_color': '#D4AF37',
            'secondary_color': '#aaaaaa',
            'accent_color': '#D4AF37'
        }

    def can_edit(self, user):
        """Check if a user can edit this property (owner or co-host)"""
        if not user.is_authenticated:
            return False
        if self.owner == user:
            return True
        return self.co_hosts.filter(co_host=user).exists()
    
    def can_delete(self, user):
        """Check if a user can delete this property (only owner)"""
        if not user.is_authenticated:
            return False
        return self.owner == user
    
    def is_co_host(self, user):
        """Check if a user is a co-host of this property"""
        if not user.is_authenticated:
            return False
        return self.co_hosts.filter(co_host=user).exists()

class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=property_image_path)
    caption = models.CharField(max_length=200, blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.property.title}"
        
    class Meta:
        ordering = ['order']

class PropertyBed(models.Model):
    BED_TYPES = [
        ('single', 'Single Bed'),
        ('single_plus', '1.5 Bed'),
        ('double', 'Double Bed'),
        ('queen', 'Queen Bed'),
        ('king', 'King Bed'),
        ('sofa_bed', 'Sofa Bed'),
        ('bunk_bed', 'Bunk Bed'),
    ]
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_beds')
    bed_type = models.CharField(max_length=20, choices=BED_TYPES)
    room_name = models.CharField(max_length=100, blank=True, help_text="e.g., 'Master Bedroom', 'Living Room', 'Guest Room'")
    quantity = models.PositiveIntegerField(default=1, help_text="Number of this type of bed in this room")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        room_part = f" in {self.room_name}" if self.room_name else ""
        quantity_part = f"{self.quantity}x " if self.quantity > 1 else ""
        return f"{quantity_part}{self.get_bed_type_display()}{room_part} - {self.property.title}"
        
    class Meta:
        ordering = ['room_name', 'bed_type']

class PropertyBathroom(models.Model):
    BATHROOM_TYPES = [
        ('service', 'Service/Half Bath'),  # toilet + sink
        ('full', 'Full Bathroom'),        # toilet + sink + shower/tub
        ('royal', 'Royal/Luxury Bath'),   # full bath with premium features
    ]
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_bathrooms')
    bathroom_type = models.CharField(max_length=20, choices=BATHROOM_TYPES)
    location = models.CharField(max_length=100, blank=True, help_text="e.g., 'En-suite Master', 'Ground Floor', 'Shared'")
    has_bidet = models.BooleanField(default=False)
    has_bathtub = models.BooleanField(default=False)
    has_shower = models.BooleanField(default=True)
    has_hairdryer = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        location_part = f" ({self.location})" if self.location else ""
        return f"{self.get_bathroom_type_display()}{location_part} - {self.property.title}"
        
    class Meta:
        ordering = ['bathroom_type', 'location']

class Instruction(models.Model):
    INSTRUCTION_TYPES = [
        ('reaching_property', 'Reaching Property'),
        ('public_transport', 'Public Transport'),
        ('parking', 'Parking'),
        ('checkin', 'Check-in'),
        ('checkout', 'Check-out'),
        ('garbage', 'Garbage'),
        ('wifi', 'WiFi'),
        ('house_rules', 'House Rules'),
        ('appliances', 'Technology'),
        ('useful_contacts', 'Useful Contacts'),
        ('emergency', 'Emergency Information'),
        ('taxes', 'Taxes'),
        ('burocracy', 'Burocracy'),
        ('other', 'Other'),
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
        return f"{self.get_instruction_type_display()} - {self.property.title}"
    
    def get_main_image(self):
        """Get the main image for this instruction"""
        image = self.images.filter(is_main=True).first()
        if not image:
            image = self.images.first()
        return image

# New model for instruction images
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
        # If this is marked as main, ensure no other image is main
        if self.is_main:
            InstructionImage.objects.filter(
                instruction=self.instruction, is_main=True
            ).exclude(pk=self.pk).update(is_main=False)
        super().save(*args, **kwargs)

class Experience(models.Model):
    CATEGORY_CHOICES = [
        ('food', 'Food'),
        ('nature', 'Nature'),
        ('experiences', 'Experiences'),
        ('services', 'Services'),
    ]
    
    GROUP_SIZE_CHOICES = [
        ('any_size', 'Any Size'),
        ('1-2', '1-2 People'),
        ('3-5', '3-5 People'),
        ('6-10', '6-10 People'),
        ('11-20', '11-20 People'),
        ('20+', '20+ People'),
    ]
    
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='experiences')
    title = models.CharField(max_length=200)
    description = models.TextField()
    ai_summary = models.TextField(blank=True, help_text="AI-generated summary of the experience")
    duration = models.IntegerField(help_text="Duration in minutes", blank=True, null=True)
    is_active = models.BooleanField(default=True, help_text="Inactive experiences are hidden when subscription limits are exceeded")
    is_featured = models.BooleanField(default=False, help_text="Featured experiences are shown on the home and dashboard pages")
    address = models.CharField(max_length=200, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    manual_geolocalization = models.BooleanField(default=False, help_text="True if coordinates were set using manual geolocalization")
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    group_size = models.CharField(max_length=20, choices=GROUP_SIZE_CHOICES, default='any_size', help_text="Maximum group size for this experience")
    # Calendar and booking information
    ical_url = models.URLField(max_length=500, blank=True, help_text="Calendar iCal URL to show availability")
    booking_method = models.TextField(blank=True, help_text="Instructions on how to book this experience")
    booking_phone = models.CharField(max_length=30, blank=True, help_text="Phone number for booking this experience")
    booking_link = models.URLField(max_length=500, blank=True, help_text="Direct link for booking this experience")
    referral_code = models.CharField(max_length=50, blank=True, help_text="Referral code for guests to receive discounts or rewards")
    
    # View tracking
    view_count = models.PositiveIntegerField(default=0, help_text="Number of times this experience page has been viewed")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title

    def get_main_image(self):
        """Get the main image for the experience, returning None if no images exist"""
        # Use the first ordered image if available
        first_image = self.images.order_by('order').first()
        if first_image:
            return first_image.image
        return None

    def increment_view_count(self):
        """Increment the view count for this experience"""
        from django.db.models import F
        Experience.objects.filter(pk=self.pk).update(view_count=F('view_count') + 1)
        # Refresh the instance to get the updated view_count
        self.refresh_from_db(fields=['view_count'])
        
        # Also track daily views
        from .models import DailyView
        DailyView.increment_daily_view('experience', self.pk)

    def save(self, *args, **kwargs):
        # Automatically geocode the address if it's provided and coordinates are missing or zero
        if self.address and (not self.latitude or not self.longitude or self.latitude == 0 or self.longitude == 0):
            try:
                from .utils import geocode_address
                latitude, longitude = geocode_address(self.address)
                if latitude and longitude:
                    self.latitude = latitude
                    self.longitude = longitude
            except Exception as e:
                print(f"Error geocoding address: {e}")
        super().save(*args, **kwargs)

class ExperienceImage(models.Model):
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='experience_images/')
    caption = models.CharField(max_length=200, blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.experience.title}"
        
    class Meta:
        ordering = ['order']

class PropertyExperience(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_experiences')
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name='property_experiences')
    distance = models.DecimalField(max_digits=5, decimal_places=2, help_text="Distance in kilometers")
    count = models.PositiveIntegerField(default=1, help_text="Number of times this experience has been associated with this property")
    
    class Meta:
        unique_together = ('property', 'experience')
    
    def __str__(self):
        return f"{self.property.title} - {self.experience.title} (Count: {self.count})"
    
    def save(self, *args, **kwargs):
        # Calculate the distance between property and experience
        if self.property.latitude and self.property.longitude and \
           self.experience.latitude and self.experience.longitude:
            from .utils import calculate_distance
            
            self.distance = calculate_distance(
                self.property.latitude, self.property.longitude,
                self.experience.latitude, self.experience.longitude
            )
        
        # Check if there's an existing entry and increment its count instead of creating a new one
        if not self.pk:  # Only for new objects
            existing = PropertyExperience.objects.filter(
                property=self.property,
                experience=self.experience
            ).first()
            
            if existing:
                existing.count += 1
                existing.save()
                # Return without saving this instance since we updated the existing one
                return
            
        super().save(*args, **kwargs)

class ExternalLink(models.Model):
    LINK_TYPES = [
        ('social', 'Social Media'),
        ('website', 'Official Website'),
        ('other', 'Other'),
    ]
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='external_links')
    title = models.CharField(max_length=100)
    url = models.URLField()
    description = models.TextField(blank=True)
    link_type = models.CharField(max_length=20, choices=LINK_TYPES)
    
    def __str__(self):
        return f"{self.title} - {self.property.title}"

def geocode_address(address):
    geolocator = Nominatim(user_agent="geoapiExercises")
    location = geolocator.geocode(address)
    if location:
        return location.latitude, location.longitude
    else:
        return None, None

# Signal to create a UserProfile when a User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        # Use update instead of save to prevent recursion
        UserProfile.objects.filter(user=instance).update(bio=instance.profile.bio)
    else:
        UserProfile.objects.create(user=instance)

# Image compression signal handlers
@receiver(post_save, sender=PropertyImage)
def compress_property_image(sender, instance, created, **kwargs):
    """Compress property images after upload if they're too large"""
    if created and instance.image:
        from .utils import compress_image
        try:
            # Run in a separate thread to not block the request
            from threading import Thread
            image_path = instance.image.path
            Thread(target=compress_image, args=(image_path, 300, 85)).start()
        except Exception as e:
            print(f"Error starting image compression for property image: {str(e)}")

@receiver(post_save, sender=ExperienceImage)
def compress_experience_image(sender, instance, created, **kwargs):
    """Compress experience images after upload if they're too large"""
    if created and instance.image:
        from .utils import compress_image
        try:
            # Run in a separate thread to not block the request
            from threading import Thread
            image_path = instance.image.path
            Thread(target=compress_image, args=(image_path, 300, 85)).start()
        except Exception as e:
            print(f"Error starting image compression for experience image: {str(e)}")

@receiver(post_save, sender=InstructionImage)
def compress_instruction_image(sender, instance, created, **kwargs):
    """Compress instruction images after upload if they're too large"""
    if created and instance.image:
        from .utils import compress_image
        try:
            # Run in a separate thread to not block the request
            from threading import Thread
            image_path = instance.image.path
            Thread(target=compress_image, args=(image_path, 300, 85)).start()
        except Exception as e:
            print(f"Error starting image compression for instruction image: {str(e)}")

@receiver(post_save, sender=UserProfile)
def compress_profile_image(sender, instance, created, **kwargs):
    """Compress user profile photos after upload if they're too large"""
    if instance.photo:
        from .utils import compress_image
        try:
            # Run in a separate thread to not block the request
            from threading import Thread
            image_path = instance.photo.path
            Thread(target=compress_image, args=(image_path, 300, 85)).start()
        except Exception as e:
            print(f"Error starting image compression for profile photo: {str(e)}")

@receiver(post_save, sender=UserProfile)
def handle_user_ban(sender, instance, **kwargs):
    """Deactivate all content when a user is banned"""
    if instance.is_banned:
        # Deactivate all properties
        Property.objects.filter(owner=instance.user).update(is_active=False)
        
        # Deactivate all experiences
        Experience.objects.filter(owner=instance.user).update(is_active=False)

@receiver(post_save, sender=Property)
def generate_property_summary(sender, instance, created, **kwargs):
    """Generate AI summary for property when it's created or description is updated"""
    from .utils import generate_ai_summary
    import threading
    
    # Don't run this during migrations or fixtures loading
    if kwargs.get('raw', False):
        return
        
    # Check if the property has a description and needs a summary
    # Generate if: newly created, no existing summary, or if forced regeneration is requested
    if instance.description and (created or not instance.ai_summary or getattr(instance, '_force_ai_summary', False)):
        # Run in a separate thread to not block the request
        def generate_summary_task():
            try:
                # Create a targeted JSON with only core property fields
                property_data = {
                    'title': instance.title,
                    'description': instance.description,
                    'property_type': instance.property_type,
                    'room_type': instance.room_type,
                    'capacity': instance.capacity,
                    'bedrooms': instance.bedrooms,
                    'beds': instance.beds,
                    'bathrooms': instance.bathrooms,
                    'size': instance.size,
                    'address': instance.address,
                    'city': instance.city,
                    'neighborhood': instance.neighborhood,
                    'has_wifi': instance.has_wifi,
                    'has_air_conditioning': instance.has_air_conditioning,
                    'has_heating': instance.has_heating,
                    'has_kitchen': instance.has_kitchen,
                    'has_washer': instance.has_washer,
                    'parking': instance.parking,
                    'has_netflix': instance.has_netflix,
                    'has_barbecue': instance.has_barbecue,
                    'pool': instance.pool,
                    'has_garden': instance.has_garden,
                    'has_balcony': instance.has_balcony,
                    'luggage_storage': instance.luggage_storage,
                    'check_in_time': instance.check_in_time.strftime('%H:%M') if instance.check_in_time else None,
                    'check_out_time': instance.check_out_time.strftime('%H:%M') if instance.check_out_time else None,
                    'minimum_stay': instance.minimum_stay,
                    'cancellation_policy': instance.cancellation_policy,
                    'pets_allowed': instance.pets_allowed,
                    'smoking_allowed': instance.smoking_allowed,
                    'parties_allowed': instance.parties_allowed,
                    'price_range': instance.price_range,
                }
                
                # Add computed properties
                property_data['property_type_display'] = instance.get_property_type_display()
                property_data['room_type_display'] = instance.get_room_type_display()
                property_data['pool_display'] = instance.get_pool_display()
                property_data['cancellation_policy_display'] = instance.get_cancellation_policy_display()
                property_data['parking_display'] = instance.get_parking_display()
                property_data['luggage_storage_display'] = instance.get_luggage_storage_display()
                
                # Generate summary
                summary = generate_ai_summary(property_data, 'property')
                
                if summary:
                    Property.objects.filter(pk=instance.pk).update(ai_summary=summary)
                    print(f"Generated AI summary for property: {instance.title}")
            except Exception as e:
                print(f"Error generating AI summary for property {instance.id}: {str(e)}")
        
        # Run the task in a separate thread
        thread = threading.Thread(target=generate_summary_task)
        thread.daemon = True
        thread.start()

@receiver(post_save, sender=Experience)
def generate_experience_summary(sender, instance, created, **kwargs):
    """Generate AI summary for experience when it's created or description is updated"""
    from .utils import generate_ai_summary
    import threading
    
    # Don't run this during migrations or fixtures loading
    if kwargs.get('raw', False):
        return
        
    # Check if the experience has a description but no summary or if it's being updated
    if instance.description and (created or not instance.ai_summary):
        # Run in a separate thread to not block the request
        def generate_summary_task():
            try:
                # Create a targeted JSON with only core experience fields
                experience_data = {
                    'title': instance.title,
                    'description': instance.description,
                    'duration': instance.duration,
                    'address': instance.address,
                    'category': instance.category,
                    'price': float(instance.price) if instance.price else None,
                    'booking_method': instance.booking_method,
                    'booking_phone': instance.booking_phone,
                }
                
                # Add computed properties
                experience_data['category_display'] = instance.get_category_display()
                
                # Generate summary
                summary = generate_ai_summary(experience_data, 'experience')
                
                if summary:
                    Experience.objects.filter(pk=instance.pk).update(ai_summary=summary)
                    print(f"Generated AI summary for experience: {instance.title}")
            except Exception as e:
                print(f"Error generating AI summary for experience {instance.id}: {str(e)}")
        
        # Run the task in a separate thread
        thread = threading.Thread(target=generate_summary_task)
        thread.daemon = True
        thread.start()

# Add these new models after the Property model
class PropertyCoHost(models.Model):
    """Model to represent co-host relationships for properties"""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='co_hosts')
    co_host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='co_hosted_properties')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('property', 'co_host')
    
    def __str__(self):
        return f"{self.co_host.username} co-hosts {self.property.title}"

class CoHostRequest(models.Model):
    """Model to handle co-host invitations"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='cohost_requests')
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_cohost_requests')
    co_host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_cohost_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True, help_text="Optional message from the host")
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('property', 'co_host')
    
    def __str__(self):
        return f"Co-host request for {self.property.title} to {self.co_host.username} ({self.status})"

# Duplicate image detection signal handlers
@receiver(post_save, sender=PropertyImage)
def detect_duplicate_property_image(sender, instance, created, **kwargs):
    """Detect and remove duplicate property images after upload"""
    print(f"🔔 PropertyImage signal: ID={instance.id}, created={created}")
    if created and instance.image:
        from .utils import detect_and_remove_duplicate_images
        try:
            print(f"🚀 Starting duplicate detection for PropertyImage ID={instance.id}")
            # Run in a separate thread to not block the request
            from threading import Thread
            Thread(target=detect_and_remove_duplicate_images, args=(instance, created)).start()
        except Exception as e:
            print(f"❌ Error in PropertyImage duplicate detection: {e}")

@receiver(post_save, sender=ExperienceImage)
def detect_duplicate_experience_image(sender, instance, created, **kwargs):
    """Detect and remove duplicate experience images after upload"""
    print(f"🔔 ExperienceImage signal: ID={instance.id}, created={created}")
    if created and instance.image:
        from .utils import detect_and_remove_duplicate_images
        try:
            print(f"🚀 Starting duplicate detection for ExperienceImage ID={instance.id}")
            # Run in a separate thread to not block the request
            from threading import Thread
            Thread(target=detect_and_remove_duplicate_images, args=(instance, created)).start()
        except Exception as e:
            print(f"❌ Error in ExperienceImage duplicate detection: {e}")

@receiver(post_save, sender=InstructionImage)
def detect_duplicate_instruction_image(sender, instance, created, **kwargs):
    """Detect and remove duplicate instruction images after upload"""
    print(f"🔔 InstructionImage signal: ID={instance.id}, created={created}")
    if created and instance.image:
        from .utils import detect_and_remove_duplicate_images
        try:
            print(f"🚀 Starting duplicate detection for InstructionImage ID={instance.id}")
            # Run in a separate thread to not block the request
            from threading import Thread
            Thread(target=detect_and_remove_duplicate_images, args=(instance, created)).start()
        except Exception as e:
            print(f"❌ Error in InstructionImage duplicate detection: {e}")

# Only add this if ArticleImage model exists
try:
    from .models import ArticleImage
    @receiver(post_save, sender=ArticleImage)
    def detect_duplicate_article_image(sender, instance, created, **kwargs):
        """Detect and remove duplicate article images after upload"""
        print(f"🔔 ArticleImage signal: ID={instance.id}, created={created}")
        if created and instance.image:
            from .utils import detect_and_remove_duplicate_images
            try:
                print(f"🚀 Starting duplicate detection for ArticleImage ID={instance.id}")
                # Run in a separate thread to not block the request
                from threading import Thread
                Thread(target=detect_and_remove_duplicate_images, args=(instance, created)).start()
            except Exception as e:
                print(f"❌ Error in ArticleImage duplicate detection: {e}")
except ImportError:
    pass  # ArticleImage doesn't exist

class Feedback(models.Model):
    """Model to collect user feedback about gr8.guide"""
    RATING_CHOICES = [
        (1, '1 - Very Poor'),
        (2, '2 - Poor'),
        (3, '3 - Average'),
        (4, '4 - Good'),
        (5, '5 - Excellent'),
    ]
    
    FEEDBACK_TYPES = [
        ('general', 'General Feedback'),
        ('bug_report', 'Bug Report'),
        ('feature_request', 'Feature Request'),
        ('user_experience', 'User Experience'),
        ('property_related', 'Property Related'),
        ('other', 'Other'),
    ]
    
    # User information (optional - can be anonymous)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, help_text="User who submitted feedback (optional)")
    name = models.CharField(max_length=100, blank=True, help_text="Name (optional)")
    email = models.EmailField(blank=True, help_text="Email for follow-up (optional)")
    
    # Feedback content
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES, default='general')
    subject = models.CharField(max_length=200, help_text="Brief subject/title for the feedback")
    message = models.TextField(help_text="Detailed feedback message")
    rating = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True, help_text="Overall rating (optional)")
    
    # Technical information
    user_agent = models.TextField(blank=True, help_text="Browser/device information")
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="IP address of submitter")
    
    # Status tracking
    is_read = models.BooleanField(default=False, help_text="Has this feedback been reviewed?")
    admin_notes = models.TextField(blank=True, help_text="Internal notes from admin")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Feedback'
        verbose_name_plural = 'Feedback'
    
    def __str__(self):
        user_info = self.user.username if self.user else (self.name or 'Anonymous')
        return f"Feedback from {user_info}: {self.subject[:50]}"
    
    def get_feedback_type_display(self):
        return dict(self.FEEDBACK_TYPES).get(self.feedback_type, self.feedback_type)
    
    def get_rating_display(self):
        if self.rating:
            return dict(self.RATING_CHOICES).get(self.rating, str(self.rating))
        return "No rating"

class ChatLog(models.Model):
    """Model to log chat interactions for admin review"""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='chat_logs', help_text="Property the chat was about")
    user_question = models.TextField(help_text="The question asked by the user")
    ai_response = models.TextField(help_text="The AI's response to the question")
    
    # Session information
    session_key = models.CharField(max_length=255, blank=True, null=True, help_text="Session identifier for grouping related chats")
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="IP address of the user")
    user_agent = models.TextField(blank=True, help_text="Browser/device information")
    
    # Authentication context
    is_authenticated = models.BooleanField(default=False, help_text="Was the user authenticated when asking?")
    has_password_access = models.BooleanField(default=False, help_text="Did the user have password access to the property?")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, help_text="User who asked (if authenticated)")
    
    # Timestamp
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
        return f"Chat for {self.property.title} at {self.created_at.strftime('%Y-%m-%d %H:%M')}: {self.user_question[:50]}..."
    
    def get_user_display(self):
        if self.user:
            return f"{self.user.username} (authenticated)"
        elif self.session_key:
            return f"Anonymous ({self.session_key[:8]}...)"
        else:
            return "Anonymous"


class PromoCode(models.Model):
    """Model to manage promotional codes for gifted subscriptions"""
    
    DURATION_CHOICES = [
        (1, '1 Month'),
        (3, '3 Months'),
        (6, '6 Months'),
        (12, '12 Months'),
    ]
    
    code = models.CharField(max_length=50, unique=True, help_text="Promotional code (e.g., SUMMER2024)")
    description = models.CharField(max_length=200, help_text="Description of the promotion")
    gift_plan = models.CharField(max_length=20, choices=UserProfile.SUBSCRIPTION_PLANS, help_text="Plan to gift when code is used")
    duration_months = models.IntegerField(choices=DURATION_CHOICES, help_text="Duration of the gift in months")
    
    # Usage tracking
    max_uses = models.PositiveIntegerField(default=1, help_text="Maximum number of times this code can be used (0 = unlimited)")
    current_uses = models.PositiveIntegerField(default=0, help_text="Number of times this code has been used")
    
    # Validity period
    valid_from = models.DateTimeField(help_text="When this code becomes valid")
    valid_until = models.DateTimeField(help_text="When this code expires")
    
    # Status
    is_active = models.BooleanField(default=True, help_text="Whether this code is currently active")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, help_text="Admin who created this code")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Promo Code'
        verbose_name_plural = 'Promo Codes'
    
    def __str__(self):
        return f"{self.code} - {self.get_gift_plan_display()} for {self.get_duration_months_display()}"
    
    def is_valid(self):
        """Check if the promo code is currently valid"""
        from django.utils import timezone
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
        """Check if the code can be used (same as is_valid but returns boolean)"""
        is_valid, _ = self.is_valid()
        return is_valid
    
    def use_code(self):
        """Mark this code as used (increment usage counter)"""
        self.current_uses += 1
        self.save()


class PromoCodeUsage(models.Model):
    """Track individual uses of promo codes"""
    promo_code = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='promo_code_usages')
    used_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        unique_together = ('promo_code', 'user')
        ordering = ['-used_at']
    
    def __str__(self):
        return f"{self.user.username} used {self.promo_code.code}"


# =============================================================================
# TRANSLATION MODELS - Sistema Ibrido per Traduzioni Automatiche
# =============================================================================

class PropertyTranslation(models.Model):
    """Traduzioni automatiche per Property"""
    LANGUAGE_CHOICES = [
        ('eng', 'English'),
        ('it', 'Italian'),
        ('de', 'German'),
        ('fr', 'French'),
    ]
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=3, choices=LANGUAGE_CHOICES)
    title = models.CharField(max_length=60, blank=True)
    description = models.TextField(blank=True)
    ai_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('property', 'language')
        ordering = ['language']
    
    def __str__(self):
        return f"{self.property.title} - {self.get_language_display()}"


class InstructionTranslation(models.Model):
    """Traduzioni automatiche per Instruction"""
    LANGUAGE_CHOICES = [
        ('eng', 'English'),
        ('it', 'Italian'),
        ('de', 'German'),
        ('fr', 'French'),
    ]
    
    instruction = models.ForeignKey(Instruction, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=3, choices=LANGUAGE_CHOICES)
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
    """Traduzioni automatiche per Experience"""
    LANGUAGE_CHOICES = [
        ('eng', 'English'),
        ('it', 'Italian'),
        ('de', 'German'),
        ('fr', 'French'),
    ]
    
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=3, choices=LANGUAGE_CHOICES)
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

class DailyView(models.Model):
    """Track daily view counts for Properties and Experiences"""
    # Content type tracking
    CONTENT_TYPE_CHOICES = [
        ('property', 'Property'),
        ('experience', 'Experience'),
    ]
    
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES)
    object_id = models.PositiveIntegerField()
    date = models.DateField()
    view_count = models.PositiveIntegerField(default=0)
    
    # Timestamps
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
        """Increment daily view count for a specific content object"""
        if date is None:
            from django.utils import timezone
            date = timezone.now().date()
        
        daily_view, created = cls.objects.get_or_create(
            content_type=content_type,
            object_id=object_id,
            date=date,
            defaults={'view_count': 0}
        )
        
        from django.db.models import F
        cls.objects.filter(pk=daily_view.pk).update(view_count=F('view_count') + 1)
        return daily_view
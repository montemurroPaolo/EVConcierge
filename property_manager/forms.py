"""
Forms for the property_manager app.
"""

from django import forms
from django.utils import timezone

from .models import (
    Booking,
    Category,
    ChatMessage,
    Experience,
    GuestDocument,
    Instruction,
    Order,
    Property,
    PropertyPhoto,
    PushNotification,
    ServiceItem,
    Special,
)


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            "name", "address", "city", "neighborhood", "description",
            "property_type", "room_type", "capacity", "bedrooms", "beds", "bathrooms", "size",
            "has_wifi", "has_air_conditioning", "has_heating", "has_kitchen",
            "has_washer", "has_netflix", "has_barbecue",
            "parking", "parking_price", "pool", "has_garden", "has_balcony",
            "check_in_time", "check_out_time", "minimum_stay",
            "cancellation_policy", "pets_allowed", "smoking_allowed", "parties_allowed",
            "luggage_storage", "luggage_storage_price", "price_range",
            "house_rules", "wifi_network", "wifi_password",
            "emergency_contacts", "is_active", "is_featured",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Property name"}),
            "address": forms.TextInput(attrs={"class": "form-input", "placeholder": "Full address"}),
            "city": forms.TextInput(attrs={"class": "form-input", "placeholder": "City"}),
            "neighborhood": forms.TextInput(attrs={"class": "form-input", "placeholder": "Neighborhood"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 4, "placeholder": "Description for guests"}),
            "property_type": forms.Select(attrs={"class": "form-input"}),
            "room_type": forms.Select(attrs={"class": "form-input"}),
            "capacity": forms.NumberInput(attrs={"class": "form-input", "style": "width:100px"}),
            "bedrooms": forms.NumberInput(attrs={"class": "form-input", "style": "width:100px"}),
            "beds": forms.NumberInput(attrs={"class": "form-input", "style": "width:100px"}),
            "bathrooms": forms.NumberInput(attrs={"class": "form-input", "style": "width:100px"}),
            "size": forms.NumberInput(attrs={"class": "form-input", "placeholder": "m²", "style": "width:100px"}),
            "parking": forms.Select(attrs={"class": "form-input"}),
            "parking_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "€/day"}),
            "pool": forms.Select(attrs={"class": "form-input"}),
            "check_in_time": forms.TimeInput(attrs={"class": "form-input", "type": "time"}),
            "check_out_time": forms.TimeInput(attrs={"class": "form-input", "type": "time"}),
            "minimum_stay": forms.NumberInput(attrs={"class": "form-input", "style": "width:100px"}),
            "cancellation_policy": forms.Select(attrs={"class": "form-input"}),
            "luggage_storage": forms.Select(attrs={"class": "form-input"}),
            "luggage_storage_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "€/day"}),
            "price_range": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 100€ to 300€"}),
            "house_rules": forms.Textarea(attrs={"class": "form-input", "rows": 4, "placeholder": "House rules"}),
            "wifi_network": forms.TextInput(attrs={"class": "form-input", "placeholder": "WiFi network name"}),
            "wifi_password": forms.TextInput(attrs={"class": "form-input", "placeholder": "WiFi password"}),
            "emergency_contacts": forms.Textarea(attrs={"class": "form-input", "rows": 3, "placeholder": "One contact per line"}),
        }


class PropertyPhotoForm(forms.ModelForm):
    class Meta:
        model = PropertyPhoto
        fields = ["image", "caption", "order"]
        widgets = {
            "caption": forms.TextInput(attrs={"class": "form-input", "placeholder": "Photo caption"}),
            "order": forms.NumberInput(attrs={"class": "form-input", "style": "width:80px"}),
        }


PropertyPhotoFormSet = forms.inlineformset_factory(
    Property, PropertyPhoto,
    form=PropertyPhotoForm,
    extra=1,
    can_delete=True,
)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "icon", "description", "order", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Category name"}),
            "icon": forms.TextInput(attrs={"class": "form-input", "placeholder": "🍽️", "style": "width:80px"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 2}),
            "order": forms.NumberInput(attrs={"class": "form-input", "style": "width:80px"}),
        }


class ServiceItemForm(forms.ModelForm):
    class Meta:
        model = ServiceItem
        fields = ["name", "description", "photo", "price", "is_available", "is_special", "order"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Item name"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 2}),
            "price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "0.00"}),
            "order": forms.NumberInput(attrs={"class": "form-input", "style": "width:80px"}),
        }


ServiceItemFormSet = forms.inlineformset_factory(
    Category, ServiceItem,
    form=ServiceItemForm,
    extra=1,
    can_delete=True,
)


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = [
            "property", "guest_name", "guest_email", "guest_phone",
            "check_in_date", "check_out_date",
            "language_preference", "notes", "is_active",
        ]
        widgets = {
            "guest_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Guest name"}),
            "guest_email": forms.EmailInput(attrs={"class": "form-input", "placeholder": "email@example.com"}),
            "guest_phone": forms.TextInput(attrs={"class": "form-input", "placeholder": "+39 ..."}),
            "check_in_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "check_out_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "language_preference": forms.Select(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "property": forms.Select(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["property"].queryset = Property.objects.filter(owner=user)


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["status", "notes"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 2, "placeholder": "Manager notes"}),
        }


class PushNotificationForm(forms.ModelForm):
    class Meta:
        model = PushNotification
        fields = [
            "property", "title", "body",
            "target_type", "target_booking", "linked_item",
            "scheduled_at", "recurring_rule",
        ]
        widgets = {
            "property": forms.Select(attrs={"class": "form-input"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "Notification title"}),
            "body": forms.Textarea(attrs={"class": "form-input", "rows": 3, "placeholder": "Message body"}),
            "target_type": forms.Select(attrs={"class": "form-input"}),
            "target_booking": forms.Select(attrs={"class": "form-input"}),
            "linked_item": forms.Select(attrs={"class": "form-input"}),
            "scheduled_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "recurring_rule": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. every Tuesday at 17:00"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            properties = Property.objects.filter(owner=user)
            self.fields["property"].queryset = properties
            self.fields["target_booking"].queryset = Booking.objects.filter(property__in=properties)
            self.fields["linked_item"].queryset = ServiceItem.objects.filter(category__property__in=properties)
        self.fields["target_booking"].required = False
        self.fields["linked_item"].required = False
        self.fields["scheduled_at"].required = False


class ChatReplyForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            "class": "form-input",
            "rows": 3,
            "placeholder": "Type your reply…",
        }),
    )


class SpecialForm(forms.ModelForm):
    class Meta:
        model = Special
        fields = ["property", "service_item", "title", "start_date", "end_date", "is_active", "linked_notification"]
        widgets = {
            "property": forms.Select(attrs={"class": "form-input"}),
            "service_item": forms.Select(attrs={"class": "form-input"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "Override title (optional)"}),
            "start_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "end_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "linked_notification": forms.Select(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            properties = Property.objects.filter(owner=user)
            self.fields["property"].queryset = properties
            self.fields["service_item"].queryset = ServiceItem.objects.filter(category__property__in=properties)
            self.fields["linked_notification"].queryset = PushNotification.objects.filter(property__in=properties)
        self.fields["linked_notification"].required = False
        self.fields["title"].required = False


class InstructionForm(forms.ModelForm):
    class Meta:
        model = Instruction
        fields = [
            "title", "instruction_type", "content", "video", "order",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "Instruction title"}),
            "instruction_type": forms.Select(attrs={"class": "form-input"}),
            "content": forms.Textarea(attrs={"class": "form-input", "rows": 6, "placeholder": "Detailed instructions…"}),
            "video": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://youtube.com/..."}),
            "order": forms.NumberInput(attrs={"class": "form-input", "style": "width:100px"}),
        }


class ExperienceForm(forms.ModelForm):
    class Meta:
        model = Experience
        fields = [
            "title", "description", "category", "price",
            "duration", "group_size", "address",
            "booking_method", "booking_phone", "booking_link",
            "referral_code", "ical_url",
            "is_active", "is_featured",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "Experience title"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 4, "placeholder": "Describe the experience…"}),
            "category": forms.Select(attrs={"class": "form-input"}),
            "price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "0.00"}),
            "duration": forms.NumberInput(attrs={"class": "form-input", "placeholder": "Minutes"}),
            "group_size": forms.Select(attrs={"class": "form-input"}),
            "address": forms.TextInput(attrs={"class": "form-input", "placeholder": "Experience location"}),
            "booking_method": forms.Textarea(attrs={"class": "form-input", "rows": 2, "placeholder": "How to book"}),
            "booking_phone": forms.TextInput(attrs={"class": "form-input", "placeholder": "+39 ..."}),
            "booking_link": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://..."}),
            "referral_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "Referral code"}),
            "ical_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "iCal URL"}),
        }

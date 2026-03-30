"""
Django admin configuration for the property_manager app.

Provides rich admin interfaces with inlines, filters, and bulk actions
for managing the entire property management workflow.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Booking,
    Category,
    ChatConversation,
    ChatLog,
    ChatMessage,
    CoHostRequest,
    DailyView,
    Experience,
    ExperienceImage,
    ExperienceTranslation,
    ExternalLink,
    Feedback,
    GuestDocument,
    Instruction,
    InstructionImage,
    InstructionTranslation,
    Order,
    OrderItem,
    PromoCode,
    PromoCodeUsage,
    Property,
    PropertyBathroom,
    PropertyBed,
    PropertyCoHost,
    PropertyExperience,
    PropertyImage,
    PropertyPhoto,
    PropertyTranslation,
    PushNotification,
    ServiceItem,
    Special,
    UserProfile,
)


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class PropertyPhotoInline(admin.TabularInline):
    model = PropertyPhoto
    extra = 1
    fields = ("image", "caption", "order")


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ("image", "caption", "order")


class PropertyBedInline(admin.TabularInline):
    model = PropertyBed
    extra = 0
    fields = ("bed_type", "room_name", "quantity")


class PropertyBathroomInline(admin.TabularInline):
    model = PropertyBathroom
    extra = 0
    fields = ("bathroom_type", "location", "has_bidet", "has_bathtub", "has_shower", "has_hairdryer")


class CategoryInline(admin.TabularInline):
    model = Category
    extra = 0
    fields = ("name", "icon", "order", "is_active")
    show_change_link = True


class ServiceItemInline(admin.TabularInline):
    model = ServiceItem
    extra = 1
    fields = ("name", "price", "is_available", "is_special", "order")
    show_change_link = True


class GuestDocumentInline(admin.TabularInline):
    model = GuestDocument
    extra = 0
    fields = ("document_type", "image", "uploaded_at")
    readonly_fields = ("uploaded_at",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    fields = ("service_item", "name", "quantity", "unit_price", "subtotal")
    readonly_fields = ("subtotal",)


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    fields = ("sender_type", "content", "created_at")
    readonly_fields = ("created_at",)


class InstructionImageInline(admin.TabularInline):
    model = InstructionImage
    extra = 1
    fields = ("image", "caption", "is_main", "order")


class ExperienceImageInline(admin.TabularInline):
    model = ExperienceImage
    extra = 1
    fields = ("image", "caption", "order")


class PropertyCoHostInline(admin.TabularInline):
    model = PropertyCoHost
    extra = 0
    fields = ("co_host", "created_at")
    readonly_fields = ("created_at",)


class ExternalLinkInline(admin.TabularInline):
    model = ExternalLink
    extra = 0
    fields = ("title", "url", "link_type")


# ---------------------------------------------------------------------------
# Model Admins
# ---------------------------------------------------------------------------

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "subscription_plan", "is_banned", "preferred_language")
    list_filter = ("subscription_plan", "is_banned")
    search_fields = ("user__username", "user__email")


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "city", "property_type", "is_active", "is_featured", "active_bookings_count")
    list_filter = ("is_active", "is_featured", "property_type", "owner")
    search_fields = ("name", "address", "city", "description")
    inlines = [PropertyPhotoInline, PropertyImageInline, PropertyBedInline,
               PropertyBathroomInline, PropertyCoHostInline, ExternalLinkInline, CategoryInline]
    fieldsets = (
        (None, {
            "fields": ("owner", "name", "nickname", "email", "phone", "description", "ai_summary",
                        "is_active", "is_featured"),
        }),
        ("Property Details", {
            "fields": ("property_type", "room_type", "capacity", "bedrooms", "beds", "bathrooms", "size"),
        }),
        ("Location", {
            "fields": ("address", "city", "neighborhood", "latitude", "longitude", "manual_geolocalization"),
        }),
        ("Amenities", {
            "fields": ("has_wifi", "has_air_conditioning", "has_heating", "has_kitchen",
                        "has_washer", "has_netflix", "has_barbecue", "parking", "parking_price",
                        "pool", "has_garden", "has_balcony"),
        }),
        ("Guest Information (Legacy)", {
            "classes": ("collapse",),
            "fields": ("house_rules", "wifi_network", "wifi_password", "emergency_contacts"),
        }),
        ("Booking & Rules", {
            "fields": ("check_in_time", "check_out_time", "minimum_stay", "cancellation_policy",
                        "pets_allowed", "smoking_allowed", "parties_allowed",
                        "luggage_storage", "luggage_storage_price", "price_range", "ical_url"),
        }),
        ("Other", {
            "fields": ("property_manager_name", "property_manager_phone",
                        "instruction_password", "welcome_message", "view_count"),
        }),
    )

    @admin.display(description="Active Bookings")
    def active_bookings_count(self, obj):
        return obj.active_bookings.count()


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "property", "icon", "order", "items_count", "is_active")
    list_filter = ("property", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("name",)
    inlines = [ServiceItemInline]

    @admin.display(description="Items")
    def items_count(self, obj):
        return obj.items.count()


@admin.register(ServiceItem)
class ServiceItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price_display", "is_available", "is_special")
    list_filter = ("category__property", "category", "is_available", "is_special")
    list_editable = ("is_available", "is_special")
    search_fields = ("name", "description")

    @admin.display(description="Price")
    def price_display(self, obj):
        return f"€{obj.price}"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("guest_name", "property", "check_in_date", "check_out_date", "status_badge", "is_active")
    list_filter = ("property", "is_active", "check_in_date")
    search_fields = ("guest_name", "guest_email", "guest_phone")
    readonly_fields = ("access_code", "created_at")
    inlines = [GuestDocumentInline]

    @admin.display(description="Status")
    def status_badge(self, obj):
        if obj.is_current:
            return format_html(
                '<span style="background:#22c55e;color:#fff;padding:2px 8px;'
                'border-radius:8px;font-size:11px">● Current</span>'
            )
        return format_html(
            '<span style="background:#94a3b8;color:#fff;padding:2px 8px;'
            'border-radius:8px;font-size:11px">Upcoming/Past</span>'
        )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "guest_name", "property_name", "status", "total_display", "created_at")
    list_filter = ("status", "booking__property")
    list_editable = ("status",)
    search_fields = ("booking__guest_name",)
    inlines = [OrderItemInline]
    actions = ["mark_confirmed", "mark_fulfilled", "mark_declined"]

    @admin.display(description="Guest")
    def guest_name(self, obj):
        return obj.booking.guest_name

    @admin.display(description="Property")
    def property_name(self, obj):
        return obj.booking.property.name

    @admin.display(description="Total")
    def total_display(self, obj):
        return f"€{obj.total}"

    @admin.action(description="Mark selected orders as Confirmed")
    def mark_confirmed(self, request, queryset):
        queryset.update(status="confirmed")

    @admin.action(description="Mark selected orders as Fulfilled")
    def mark_fulfilled(self, request, queryset):
        queryset.update(status="fulfilled")

    @admin.action(description="Mark selected orders as Declined")
    def mark_declined(self, request, queryset):
        queryset.update(status="declined")


@admin.register(Instruction)
class InstructionAdmin(admin.ModelAdmin):
    list_display = ("title", "property", "instruction_type", "order")
    list_filter = ("property", "instruction_type")
    search_fields = ("title", "content")
    inlines = [InstructionImageInline]


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "category", "price", "is_active", "is_featured")
    list_filter = ("category", "is_active", "is_featured")
    search_fields = ("title", "description")
    inlines = [ExperienceImageInline]


@admin.register(PushNotification)
class PushNotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "property", "target_type", "scheduled_at", "is_sent")
    list_filter = ("property", "is_sent", "target_type")
    search_fields = ("title", "body")


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ("booking", "is_escalated", "last_message_preview", "created_at")
    list_filter = ("is_escalated", "booking__property")
    inlines = [ChatMessageInline]

    @admin.display(description="Last Message")
    def last_message_preview(self, obj):
        msg = obj.last_message
        if msg:
            return f"[{msg.sender_type}] {msg.content[:50]}"
        return "—"


@admin.register(ChatLog)
class ChatLogAdmin(admin.ModelAdmin):
    list_display = ("property", "user_question_short", "is_authenticated", "created_at")
    list_filter = ("property", "is_authenticated")
    search_fields = ("user_question", "ai_response")

    @admin.display(description="Question")
    def user_question_short(self, obj):
        return obj.user_question[:80]


@admin.register(Special)
class SpecialAdmin(admin.ModelAdmin):
    list_display = ("display_title", "property", "service_item", "start_date", "end_date", "is_active")
    list_filter = ("property", "is_active")
    search_fields = ("title", "service_item__name")

    @admin.display(description="Title")
    def display_title(self, obj):
        return obj.title or obj.service_item.name


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("subject", "feedback_type", "rating", "is_read", "created_at")
    list_filter = ("feedback_type", "is_read", "rating")
    search_fields = ("subject", "message")


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "gift_plan", "duration_months", "current_uses", "max_uses", "is_active")
    list_filter = ("is_active", "gift_plan")
    search_fields = ("code", "description")


# Register remaining models without custom admin
admin.site.register(PropertyPhoto)
admin.site.register(PropertyImage)
admin.site.register(PropertyBed)
admin.site.register(PropertyBathroom)
admin.site.register(GuestDocument)
admin.site.register(OrderItem)
admin.site.register(ChatMessage)
admin.site.register(InstructionImage)
admin.site.register(ExperienceImage)
admin.site.register(PropertyExperience)
admin.site.register(ExternalLink)
admin.site.register(PropertyCoHost)
admin.site.register(CoHostRequest)
admin.site.register(PromoCodeUsage)
admin.site.register(PropertyTranslation)
admin.site.register(InstructionTranslation)
admin.site.register(ExperienceTranslation)
admin.site.register(DailyView)

# Customize admin site header
admin.site.site_header = "EV Concierge — Property Manager"
admin.site.site_title = "EV Concierge Admin"
admin.site.index_title = "Management Dashboard"

from django.contrib import admin
from django.utils.html import format_html
from .models import User, ConferenceRoom, Booking, BookingHistory


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'phone', 'department', 'is_active',
                    'date_joined']
    list_filter = ['role', 'is_active', 'department']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone']
    fieldsets = (
        ('Основная информация', {
            'fields': ('username', 'password', 'email', 'first_name', 'last_name')
        }),
        ('Контактная информация', {
            'fields': ('phone', 'department')
        }),
        ('Роли и права', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Важные даты', {
            'fields': ('last_login', 'date_joined')
        }),
    )


@admin.register(ConferenceRoom)
class ConferenceRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'capacity', 'location', 'is_active', 'room_image', 'has_projector', 'has_video_conference',
                    'has_whiteboard']
    list_filter = ['is_active', 'has_projector', 'has_video_conference', 'has_whiteboard']
    search_fields = ['name', 'location', 'description']
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'capacity', 'location', 'description')
        }),
        ('Оснащение', {
            'fields': ('has_projector', 'has_video_conference', 'has_whiteboard')
        }),
        ('Изображение и статус', {
            'fields': ('image', 'is_active')
        }),
    )

    def room_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;"/>', obj.image.url)
        return "Нет фото"

    room_image.short_description = "Фото"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['title', 'room', 'requester', 'start_time', 'end_time', 'status', 'participants_count',
                    'created_at']
    list_filter = ['status', 'room', 'created_at', 'start_time']
    search_fields = ['title', 'description', 'requester__username', 'requester__email']
    date_hierarchy = 'start_time'
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'room', 'requester')
        }),
        ('Время бронирования', {
            'fields': ('start_time', 'end_time'),
            'description': 'Рабочее время: с 7:00 до 16:30'
        }),
        ('Участники', {
            'fields': ('participants_count',)
        }),
        ('Статус и модерация', {
            'fields': ('status', 'moderated_by', 'moderation_comment')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # Если создается новое бронирование через админку
            if not obj.requester:
                obj.requester = request.user
        super().save_model(request, obj, form, change)


@admin.register(BookingHistory)
class BookingHistoryAdmin(admin.ModelAdmin):
    list_display = ['booking', 'user', 'action', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['booking__title', 'user__username']
    readonly_fields = ['booking', 'user', 'action', 'timestamp', 'details']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta


class User(AbstractUser):
    """Расширенная модель пользователя"""
    ROLE_CHOICES = (
        ('moderator', 'Модератор'),
        ('requester', 'Заявитель'),
        ('employee', 'Сотрудник'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee', verbose_name="Роль")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    department = models.CharField(max_length=100, blank=True, verbose_name="Отдел")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Аватар")

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return None

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"


class ConferenceRoom(models.Model):
    """Модель конференц-зала"""
    name = models.CharField(max_length=100, verbose_name="Название")
    capacity = models.PositiveIntegerField(verbose_name="Вместимость")
    location = models.CharField(max_length=200, verbose_name="Местоположение")
    description = models.TextField(blank=True, verbose_name="Описание")
    has_projector = models.BooleanField(default=False, verbose_name="Проектор")
    has_video_conference = models.BooleanField(default=False, verbose_name="Видеоконференция")
    has_whiteboard = models.BooleanField(default=False, verbose_name="Доска")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    image = models.ImageField(upload_to='rooms/', blank=True, null=True, verbose_name="Изображение")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def __str__(self):
        return self.name

    def get_equipment_list(self):
        equipment = []
        if self.has_projector:
            equipment.append("Проектор")
        if self.has_video_conference:
            equipment.append("Видеоконференция")
        if self.has_whiteboard:
            equipment.append("Доска")
        return equipment

    class Meta:
        verbose_name = "Конференц-зал"
        verbose_name_plural = "Конференц-залы"
        ordering = ['name']


class Booking(models.Model):
    """Модель бронирования"""
    STATUS_CHOICES = (
        ('pending', 'Ожидает подтверждения'),
        ('approved', 'Подтверждено'),
        ('rejected', 'Отклонено'),
        ('cancelled', 'Отменено'),
    )

    room = models.ForeignKey(ConferenceRoom, on_delete=models.CASCADE, verbose_name="Зал", related_name='bookings')
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings', verbose_name="Заявитель")
    title = models.CharField(max_length=200, verbose_name="Название мероприятия")
    description = models.TextField(verbose_name="Описание")
    start_time = models.DateTimeField(verbose_name="Начало")
    end_time = models.DateTimeField(verbose_name="Окончание")
    participants_count = models.PositiveIntegerField(verbose_name="Количество участников")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")
    moderated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='moderated_bookings', verbose_name="Модератор")
    moderation_comment = models.TextField(blank=True, verbose_name="Комментарий модератора")

    def __str__(self):
        return f"{self.title} - {self.room.name} ({self.get_status_display()})"

    def duration(self):
        delta = self.end_time - self.start_time
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        if hours > 0:
            return f"{hours} ч {minutes} мин"
        return f"{minutes} мин"

    def duration_in_minutes(self):
        delta = self.end_time - self.start_time
        return delta.seconds // 60

    def is_conflicting(self):
        conflicting = Booking.objects.filter(
            room=self.room,
            status__in=['pending', 'approved'],
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).exclude(pk=self.pk)
        return conflicting.exists()

    def is_within_working_hours(self):
        start_hour = self.start_time.hour
        end_hour = self.end_time.hour
        end_minute = self.end_time.minute

        if start_hour < 7:
            return False
        if end_hour > 16:
            return False
        if end_hour == 16 and end_minute > 30:
            return False
        return True

    def can_cancel(self):
        if self.status not in ['pending', 'approved']:
            return False
        if self.status == 'approved':
            if self.start_time < timezone.now() + timedelta(hours=2):
                return False
        return True

    class Meta:
        verbose_name = "Бронирование"
        verbose_name_plural = "Бронирования"
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['start_time', 'end_time']),
            models.Index(fields=['status']),
            models.Index(fields=['room', 'status']),
        ]


class BookingHistory(models.Model):
    """История изменений бронирований"""
    ACTION_CHOICES = (
        ('created', 'Создано'),
        ('updated', 'Обновлено'),
        ('approved', 'Подтверждено'),
        ('rejected', 'Отклонено'),
        ('cancelled', 'Отменено'),
    )

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='history', verbose_name="Бронирование")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Пользователь")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Действие")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Время")
    details = models.JSONField(default=dict, verbose_name="Детали")

    def __str__(self):
        return f"{self.booking.title} - {self.get_action_display()} - {self.timestamp}"

    class Meta:
        verbose_name = "История бронирования"
        verbose_name_plural = "История бронирований"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['booking', 'timestamp']),
            models.Index(fields=['action']),
        ]
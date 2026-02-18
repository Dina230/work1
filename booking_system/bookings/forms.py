from django import forms
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from .models import Booking, ConferenceRoom, User
from datetime import timedelta, datetime


class LoginForm(AuthenticationForm):
    """Форма входа"""
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Имя пользователя'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Пароль'})
    )


class UserRegistrationForm(forms.ModelForm):
    """Форма регистрации пользователя"""
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password_confirm = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'department', 'role']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Придумайте имя пользователя'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Имя'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Фамилия'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (999) 123-45-67'}),
            'department': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Отдел'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'username': 'Имя пользователя',
            'email': 'Email',
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'phone': 'Телефон',
            'department': 'Отдел',
            'role': 'Роль',
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Пароли не совпадают")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    """Форма редактирования пользователя"""

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'department', 'role', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BookingForm(forms.ModelForm):
    """Форма создания бронирования с проверкой рабочего времени 7:00 - 16:30"""

    class Meta:
        model = Booking
        fields = ['room', 'title', 'description', 'start_time', 'end_time', 'participants_count']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control',
                'min': timezone.now().strftime('%Y-%m-%dT%H:%M')
            }),
            'end_time': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control',
                'min': timezone.now().strftime('%Y-%m-%dT%H:%M')
            }),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название мероприятия'}),
            'participants_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'room': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'room': 'Конференц-зал',
            'title': 'Название мероприятия',
            'description': 'Описание',
            'start_time': 'Дата и время начала',
            'end_time': 'Дата и время окончания',
            'participants_count': 'Количество участников',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['room'].queryset = ConferenceRoom.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        room = cleaned_data.get('room')

        if start_time and end_time:
            # Проверка, что время начала меньше времени окончания
            if start_time >= end_time:
                raise forms.ValidationError("Время окончания должно быть позже времени начала")

            # Проверка, что бронирование не в прошлом
            if start_time < timezone.now():
                raise forms.ValidationError("Нельзя создать бронирование в прошлом")

            # Проверка минимальной длительности (30 минут)
            if (end_time - start_time).total_seconds() < 1800:
                raise forms.ValidationError("Минимальная длительность бронирования - 30 минут")

            # Проверка максимальной длительности (8 часов)
            if (end_time - start_time).total_seconds() > 28800:
                raise forms.ValidationError("Максимальная длительность бронирования - 8 часов")

            # Проверка рабочего времени (с 7:00 до 16:30)
            start_hour = start_time.hour
            start_minute = start_time.minute
            end_hour = end_time.hour
            end_minute = end_time.minute

            # Проверка начала рабочего дня
            if start_hour < 7 or (start_hour == 7 and start_minute < 0):
                raise forms.ValidationError("Бронирование возможно только с 7:00")

            # Проверка окончания рабочего дня
            if end_hour > 16 or (end_hour == 16 and end_minute > 30):
                raise forms.ValidationError("Бронирование возможно только до 16:30")

            if end_hour < start_hour:
                raise forms.ValidationError("Время окончания не может быть раньше времени начала")

            # Проверка на пересечение с другими бронированиями
            if room:
                conflicting = Booking.objects.filter(
                    room=room,
                    status__in=['pending', 'approved'],
                    start_time__lt=end_time,
                    end_time__gt=start_time
                )
                if conflicting.exists():
                    raise forms.ValidationError("Это время уже занято")

        return cleaned_data


class ModerationForm(forms.Form):
    """Форма для модерации заявки"""
    ACTION_CHOICES = (
        ('approve', '✅ Подтвердить'),
        ('reject', '❌ Отклонить'),
    )
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label="Действие"
    )
    comment = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False,
        label="Комментарий",
        help_text="Укажите причину при отклонении заявки"
    )


class RoomForm(forms.ModelForm):
    """Форма для создания/редактирования конференц-зала"""

    class Meta:
        model = ConferenceRoom
        fields = ['name', 'capacity', 'location', 'description', 'has_projector',
                  'has_video_conference', 'has_whiteboard', 'is_active', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Этаж, номер кабинета'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'has_projector': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_video_conference': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_whiteboard': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }
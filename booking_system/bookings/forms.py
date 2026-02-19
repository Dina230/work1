from django import forms
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import authenticate
from .models import User, Booking, ConferenceRoom
from datetime import timedelta, datetime


class LoginForm(forms.Form):
    """Форма входа"""
    username = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите имя пользователя'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise forms.ValidationError("Неверное имя пользователя или пароль")
            if not user.is_active:
                raise forms.ValidationError("Пользователь деактивирован")
        return cleaned_data


class UserRegistrationForm(forms.ModelForm):
    """Форма регистрации пользователя с аватаром"""
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль'
        })
    )
    password_confirm = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Подтвердите пароль'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'department', 'role', 'avatar']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Придумайте имя пользователя'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your@email.com'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите имя'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите фамилию'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+7 (999) 123-45-67'
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите отдел'
            }),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'avatar': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Пароли не совпадают")

        username = cleaned_data.get('username')
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError("Пользователь с таким именем уже существует")

        email = cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.is_active = True
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    """Форма редактирования пользователя с аватаром"""

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'department', 'role', 'is_active', 'avatar']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'avatar': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }


class BookingForm(forms.ModelForm):
    """Форма создания бронирования"""

    class Meta:
        model = Booking
        fields = ['room', 'title', 'description', 'start_time', 'end_time', 'participants_count']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control',
            }),
            'end_time': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control',
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Опишите мероприятие'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название мероприятия'
            }),
            'participants_count': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'room': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['room'].queryset = ConferenceRoom.objects.filter(is_active=True)

        now = timezone.now()
        min_date = now.strftime('%Y-%m-%dT%H:%M')
        self.fields['start_time'].widget.attrs['min'] = min_date
        self.fields['end_time'].widget.attrs['min'] = min_date

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        room = cleaned_data.get('room')

        current_time = timezone.now()

        if start_time and end_time:
            if start_time < current_time:
                raise forms.ValidationError("Нельзя создать бронирование на прошедшую дату")

            if start_time >= end_time:
                raise forms.ValidationError("Время окончания должно быть позже времени начала")

            min_duration = timedelta(minutes=settings.BOOKING_SETTINGS['MIN_BOOKING_DURATION'])
            if (end_time - start_time) < min_duration:
                raise forms.ValidationError(
                    f"Минимальная длительность - {settings.BOOKING_SETTINGS['MIN_BOOKING_DURATION']} минут")

            max_duration = timedelta(minutes=settings.BOOKING_SETTINGS['MAX_BOOKING_DURATION'])
            if (end_time - start_time) > max_duration:
                raise forms.ValidationError(
                    f"Максимальная длительность - {settings.BOOKING_SETTINGS['MAX_BOOKING_DURATION'] // 60} часов")

            if start_time.hour < settings.BOOKING_SETTINGS['BOOKING_START_HOUR']:
                raise forms.ValidationError(
                    f"Бронирование только с {settings.BOOKING_SETTINGS['BOOKING_START_HOUR']}:00")

            if (end_time.hour > settings.BOOKING_SETTINGS['BOOKING_END_HOUR'] or
                    (end_time.hour == settings.BOOKING_SETTINGS['BOOKING_END_HOUR'] and
                     end_time.minute > settings.BOOKING_SETTINGS['BOOKING_END_MINUTE'])):
                raise forms.ValidationError(
                    f"Бронирование только до {settings.BOOKING_SETTINGS['BOOKING_END_HOUR']}:{settings.BOOKING_SETTINGS['BOOKING_END_MINUTE']}")

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
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Введите комментарий...'
        }),
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
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название зала'
            }),
            'capacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Этаж, номер кабинета'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Описание зала'
            }),
            'has_projector': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_video_conference': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_whiteboard': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }
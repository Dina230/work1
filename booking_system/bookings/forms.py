from django import forms
from django.contrib.auth import authenticate
from .models import User, Booking, ConferenceRoom

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
    """Форма регистрации пользователя"""
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
        fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'department', 'role']
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

        # Проверка совпадения паролей
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Пароли не совпадают")

        # Проверка уникальности username
        username = cleaned_data.get('username')
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError("Пользователь с таким именем уже существует")

        # Проверка уникальности email
        email = cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.is_active = True  # Активируем пользователя сразу
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
    """Форма создания бронирования"""
    class Meta:
        model = Booking
        fields = ['room', 'title', 'description', 'start_time', 'end_time', 'participants_count']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'end_time': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
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
            if start_time >= end_time:
                raise forms.ValidationError("Время окончания должно быть позже времени начала")

            # Проверка рабочего времени (7:00 - 16:30)
            if start_time.hour < 7:
                raise forms.ValidationError("Бронирование возможно только с 7:00")
            if end_time.hour > 16 or (end_time.hour == 16 and end_time.minute > 30):
                raise forms.ValidationError("Бронирование возможно только до 16:30")

            # Проверка на конфликты
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
        labels = {
            'name': 'Название',
            'capacity': 'Вместимость (человек)',
            'location': 'Местоположение',
            'description': 'Описание',
            'has_projector': 'Проектор',
            'has_video_conference': 'Видеоконференцсвязь',
            'has_whiteboard': 'Магнитно-маркерная доска',
            'is_active': 'Зал активен',
            'image': 'Изображение',
        }
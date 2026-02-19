from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import datetime, timedelta, date
import csv
import logging
from .models import Booking, ConferenceRoom, User, BookingHistory
from .forms import (
    BookingForm, ModerationForm, RoomForm, UserRegistrationForm,
    UserEditForm, LoginForm
)
from .decorators import moderator_required, requester_required, employee_required, any_role_required

# Настройка логирования
logger = logging.getLogger(__name__)


# ==================== АУТЕНТИФИКАЦИЯ ====================

def login_view(request):
    """Страница входа"""
    if request.user.is_authenticated:
        return redirect('bookings:index')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')

            user = authenticate(request, username=username, password=password)

            if user is not None:
                if user.is_active:
                    login(request, user)
                    messages.success(request, f"Добро пожаловать, {user.get_full_name() or user.username}!")

                    if user.role == 'moderator':
                        return redirect('bookings:moderator_dashboard')
                    elif user.role == 'requester':
                        return redirect('bookings:my_bookings')
                    else:
                        return redirect('bookings:schedule')
                else:
                    messages.error(request, "Ваш аккаунт деактивирован. Обратитесь к администратору.")
            else:
                messages.error(request, "Неверное имя пользователя или пароль")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = LoginForm()

    return render(request, 'bookings/login.html', {'form': form})


def logout_view(request):
    """Выход из системы"""
    logout(request)
    messages.info(request, "Вы успешно вышли из системы")
    return redirect('bookings:login')


def register_view(request):
    """Регистрация нового пользователя"""
    if request.user.is_authenticated:
        return redirect('bookings:index')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                login(request, user)
                messages.success(request, "Регистрация прошла успешно! Добро пожаловать!")

                if user.role == 'requester':
                    return redirect('bookings:create_booking')
                else:
                    return redirect('bookings:schedule')
            except Exception as e:
                messages.error(request, f"Ошибка при регистрации: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = UserRegistrationForm()

    return render(request, 'bookings/register.html', {'form': form})


# ==================== ОБЩИЕ СТРАНИЦЫ ====================

@any_role_required
def index(request):
    """Главная страница"""
    rooms = ConferenceRoom.objects.filter(is_active=True)

    context = {
        'rooms': rooms,
        'total_rooms': rooms.count(),
        'booking_settings': settings.BOOKING_SETTINGS,
        'now': timezone.now(),
    }

    if request.user.is_authenticated:
        if request.user.role == 'requester':
            context['my_pending_bookings'] = Booking.objects.filter(
                requester=request.user,
                status='pending'
            ).count()
            context['my_approved_bookings'] = Booking.objects.filter(
                requester=request.user,
                status='approved'
            ).count()
        elif request.user.role == 'moderator':
            context['pending_bookings_count'] = Booking.objects.filter(status='pending').count()
            context['total_users'] = User.objects.filter(is_active=True).count()
        elif request.user.role == 'employee':
            today = timezone.now().date()
            context['today_bookings'] = Booking.objects.filter(
                status='approved',
                start_time__date=today
            ).count()

    return render(request, 'bookings/index.html', context)


@any_role_required
def booking_detail(request, booking_id):
    """Детальная информация о бронировании"""
    booking = get_object_or_404(Booking, id=booking_id)

    if request.user.role != 'moderator' and booking.requester != request.user:
        messages.error(request, "У вас нет прав для просмотра этого бронирования")
        return redirect('bookings:index')

    history = booking.history.all()[:10]

    return render(request, 'bookings/booking_detail.html', {
        'booking': booking,
        'history': history,
        'now': timezone.now(),
    })


@any_role_required
def check_availability(request):
    """API для проверки доступности зала с проверкой на прошедшие даты"""
    if request.method == 'GET':
        room_id = request.GET.get('room_id')
        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')

        if not all([room_id, start_time, end_time]):
            return JsonResponse({'error': 'Missing parameters'}, status=400)

        try:
            room = ConferenceRoom.objects.get(id=room_id, is_active=True)
            start = datetime.fromisoformat(start_time)
            end = datetime.fromisoformat(end_time)

            # Делаем start и end timezone-aware если они наивные
            if timezone.is_naive(start):
                start = timezone.make_aware(start)
            if timezone.is_naive(end):
                end = timezone.make_aware(end)

            now = timezone.now()

            # Проверка на прошедшие даты
            if start < now:
                return JsonResponse({
                    'available': False,
                    'time_valid': False,
                    'time_message': 'Нельзя выбрать прошедшую дату и время',
                    'conflicting': False,
                    'room_name': room.name,
                    'capacity': room.capacity
                })

            # Проверка рабочего времени
            time_valid = True
            time_message = ""

            if start.hour < settings.BOOKING_SETTINGS['BOOKING_START_HOUR']:
                time_valid = False
                time_message = f"Бронирование возможно только с {settings.BOOKING_SETTINGS['BOOKING_START_HOUR']}:00"
            elif (end.hour > settings.BOOKING_SETTINGS['BOOKING_END_HOUR'] or
                  (end.hour == settings.BOOKING_SETTINGS['BOOKING_END_HOUR'] and
                   end.minute > settings.BOOKING_SETTINGS['BOOKING_END_MINUTE'])):
                time_valid = False
                time_message = f"Бронирование возможно только до {settings.BOOKING_SETTINGS['BOOKING_END_HOUR']}:{settings.BOOKING_SETTINGS['BOOKING_END_MINUTE']}"

            # Проверка минимальной длительности
            min_duration = timedelta(minutes=settings.BOOKING_SETTINGS['MIN_BOOKING_DURATION'])
            if (end - start) < min_duration:
                time_valid = False
                time_message = f"Минимальная длительность бронирования {settings.BOOKING_SETTINGS['MIN_BOOKING_DURATION']} минут"

            # Проверка максимальной длительности
            max_duration = timedelta(minutes=settings.BOOKING_SETTINGS['MAX_BOOKING_DURATION'])
            if (end - start) > max_duration:
                time_valid = False
                time_message = f"Максимальная длительность бронирования {settings.BOOKING_SETTINGS['MAX_BOOKING_DURATION'] // 60} часов"

            # Проверка конфликтов - только с подтвержденными бронированиями
            conflicting = Booking.objects.filter(
                room=room,
                status='approved',
                start_time__lt=end,
                end_time__gt=start
            ).exists()

            return JsonResponse({
                'available': not conflicting and time_valid,
                'time_valid': time_valid,
                'time_message': time_message,
                'conflicting': conflicting,
                'room_name': room.name,
                'capacity': room.capacity
            })

        except (ConferenceRoom.DoesNotExist, ValueError) as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ==================== ДЛЯ ЗАЯВИТЕЛЯ ====================

@requester_required
def create_booking(request):
    """Создание новой заявки на бронирование с проверкой на прошедшие даты"""
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.requester = request.user

            # Дополнительная проверка на прошедшую дату
            if booking.start_time < timezone.now():
                messages.error(request, "Ошибка: Нельзя создать бронирование на прошедшую дату")
                return render(request, 'bookings/create_booking.html', {
                    'form': form,
                    'rooms': ConferenceRoom.objects.filter(is_active=True),
                    'booking_settings': settings.BOOKING_SETTINGS,
                })

            # Проверка, что дата не слишком далеко в будущем
            max_advance = timezone.now() + timedelta(days=settings.BOOKING_SETTINGS['MAX_ADVANCE_BOOKING_DAYS'])
            if booking.start_time > max_advance:
                messages.error(request,
                               f"Нельзя забронировать более чем на {settings.BOOKING_SETTINGS['MAX_ADVANCE_BOOKING_DAYS']} дней вперед")
                return render(request, 'bookings/create_booking.html', {
                    'form': form,
                    'rooms': ConferenceRoom.objects.filter(is_active=True),
                    'booking_settings': settings.BOOKING_SETTINGS,
                })

            booking.save()

            BookingHistory.objects.create(
                booking=booking,
                user=request.user,
                action='created',
                details={'title': booking.title, 'room': booking.room.name}
            )

            messages.success(
                request,
                f"Заявка на бронирование '{booking.title}' успешно создана и отправлена на модерацию"
            )
            return redirect('bookings:booking_detail', booking_id=booking.id)
        else:
            # Если форма невалидна, показываем ошибки
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        initial_data = {}
        room_id = request.GET.get('room')
        if room_id:
            try:
                room = ConferenceRoom.objects.get(id=room_id, is_active=True)
                initial_data['room'] = room
            except ConferenceRoom.DoesNotExist:
                pass

        date_param = request.GET.get('date')
        start_time = request.GET.get('start')
        if date_param and start_time:
            try:
                initial_data['start_time'] = f"{date_param}T{start_time}"
            except:
                pass

        form = BookingForm(initial=initial_data)

    rooms = ConferenceRoom.objects.filter(is_active=True)

    return render(request, 'bookings/create_booking.html', {
        'form': form,
        'rooms': rooms,
        'booking_settings': settings.BOOKING_SETTINGS,
    })


@requester_required
def my_bookings(request):
    """Список бронирований текущего пользователя"""
    status_filter = request.GET.get('status', 'all')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    bookings = Booking.objects.filter(requester=request.user)

    if status_filter != 'all':
        bookings = bookings.filter(status=status_filter)

    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            bookings = bookings.filter(start_time__date__gte=date_from)
        except ValueError:
            pass

    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            bookings = bookings.filter(end_time__date__lte=date_to)
        except ValueError:
            pass

    bookings = bookings.order_by('-created_at')

    stats = {
        'total': bookings.count(),
        'pending': bookings.filter(status='pending').count(),
        'approved': bookings.filter(status='approved').count(),
        'rejected': bookings.filter(status='rejected').count(),
        'cancelled': bookings.filter(status='cancelled').count(),
    }

    return render(request, 'bookings/booking_list.html', {
        'bookings': bookings,
        'stats': stats,
        'status_filter': status_filter,
        'now': timezone.now(),
    })


@requester_required
def cancel_booking(request, booking_id):
    """Отмена бронирования"""
    booking = get_object_or_404(Booking, id=booking_id, requester=request.user)

    if booking.status not in ['pending', 'approved']:
        messages.error(request, "Это бронирование нельзя отменить")
        return redirect('bookings:booking_detail', booking_id=booking.id)

    if booking.status == 'approved' and booking.start_time < timezone.now() + timedelta(
            hours=settings.BOOKING_SETTINGS['CANCELLATION_DEADLINE_HOURS']):
        messages.error(request,
                       f"Нельзя отменить бронирование менее чем за {settings.BOOKING_SETTINGS['CANCELLATION_DEADLINE_HOURS']} часа до начала")
        return redirect('bookings:booking_detail', booking_id=booking.id)

    if request.method == 'POST':
        old_status = booking.status
        booking.status = 'cancelled'
        booking.save()

        BookingHistory.objects.create(
            booking=booking,
            user=request.user,
            action='cancelled',
            details={'old_status': old_status}
        )

        messages.success(request, f"Бронирование '{booking.title}' отменено")
        return redirect('bookings:my_bookings')

    return render(request, 'bookings/cancel_booking.html', {'booking': booking})


# ==================== ДЛЯ МОДЕРАТОРА ====================

@moderator_required
def moderator_dashboard(request):
    """Панель модератора"""
    today = timezone.now().date()
    week_ago = timezone.now() - timedelta(days=7)

    stats = {
        'total_pending': Booking.objects.filter(status='pending').count(),
        'total_approved_today': Booking.objects.filter(
            status='approved',
            start_time__date=today
        ).count(),
        'total_rooms': ConferenceRoom.objects.count(),
        'total_users': User.objects.filter(is_active=True).count(),
        'bookings_this_week': Booking.objects.filter(
            created_at__gte=week_ago
        ).count(),
    }

    pending_bookings = Booking.objects.filter(status='pending').order_by('start_time')
    approved_bookings = Booking.objects.filter(status='approved').order_by('-start_time')[:10]
    rejected_bookings = Booking.objects.filter(status='rejected').order_by('-start_time')[:10]

    upcoming_bookings = Booking.objects.filter(
        status='approved',
        start_time__gte=timezone.now(),
        start_time__lte=timezone.now() + timedelta(days=3)
    ).order_by('start_time')[:10]

    recent_users = User.objects.order_by('-date_joined')[:5]

    context = {
        'stats': stats,
        'pending_bookings': pending_bookings,
        'approved_bookings': approved_bookings,
        'rejected_bookings': rejected_bookings,
        'upcoming_bookings': upcoming_bookings,
        'recent_users': recent_users,
        'booking_settings': settings.BOOKING_SETTINGS,
        'now': timezone.now(),
    }
    return render(request, 'bookings/moderator_dashboard.html', context)


@moderator_required
def moderate_booking(request, booking_id):
    """Модерация конкретной заявки"""
    booking = get_object_or_404(Booking, id=booking_id, status='pending')

    if request.method == 'POST':
        form = ModerationForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            comment = form.cleaned_data['comment']

            if action == 'approve':
                # Проверка на конфликты - только с подтвержденными бронированиями
                conflicting = Booking.objects.filter(
                    room=booking.room,
                    status='approved',
                    start_time__lt=booking.end_time,
                    end_time__gt=booking.start_time
                ).exists()

                if conflicting:
                    messages.error(
                        request,
                        "Обнаружен конфликт с подтвержденным бронированием. Подтверждение невозможно."
                    )
                    conflicts = Booking.objects.filter(
                        room=booking.room,
                        status='approved',
                        start_time__lt=booking.end_time,
                        end_time__gt=booking.start_time
                    ).exclude(id=booking.id)
                    return render(
                        request,
                        'bookings/moderate_booking.html',
                        {'booking': booking, 'form': form, 'conflicts': conflicts}
                    )

                # Проверка на прошедшую дату
                if booking.start_time < timezone.now():
                    messages.error(
                        request,
                        "Нельзя подтвердить бронирование на прошедшую дату."
                    )
                    return render(
                        request,
                        'bookings/moderate_booking.html',
                        {'booking': booking, 'form': form}
                    )

                booking.status = 'approved'
                messages.success(request, f"Заявка '{booking.title}' подтверждена")
            else:
                if not comment:
                    messages.error(request, "При отклонении необходимо указать комментарий")
                    return render(
                        request,
                        'bookings/moderate_booking.html',
                        {'booking': booking, 'form': form}
                    )

                booking.status = 'rejected'
                messages.warning(request, f"Заявка '{booking.title}' отклонена")

            booking.moderated_by = request.user
            booking.moderation_comment = comment
            booking.save()

            BookingHistory.objects.create(
                booking=booking,
                user=request.user,
                action=action,
                details={'comment': comment}
            )

            return redirect('bookings:moderator_dashboard')
    else:
        form = ModerationForm()

    # Находим конфликтующие подтвержденные бронирования
    conflicts = Booking.objects.filter(
        room=booking.room,
        status='approved',
        start_time__lt=booking.end_time,
        end_time__gt=booking.start_time
    ).exclude(id=booking.id)

    return render(request, 'bookings/moderate_booking.html', {
        'booking': booking,
        'form': form,
        'conflicts': conflicts
    })


@moderator_required
def room_management(request):
    """Управление конференц-залами"""
    rooms = ConferenceRoom.objects.all()
    today = timezone.now().date()

    for room in rooms:
        room.today_bookings = Booking.objects.filter(
            room=room,
            status='approved',
            start_time__date=today
        ).count()
        room.upcoming_bookings = Booking.objects.filter(
            room=room,
            status='approved',
            start_time__gte=timezone.now()
        ).count()

    return render(request, 'bookings/room_management.html', {'rooms': rooms})


@moderator_required
def create_room(request):
    """Создание нового конференц-зала"""
    if request.method == 'POST':
        form = RoomForm(request.POST, request.FILES)
        if form.is_valid():
            room = form.save()
            messages.success(request, f"Зал '{room.name}' успешно создан")
            return redirect('bookings:room_management')
    else:
        form = RoomForm()

    return render(request, 'bookings/room_form.html', {
        'form': form,
        'title': 'Создание нового зала'
    })


@moderator_required
def edit_room(request, room_id):
    """Редактирование конференц-зала"""
    room = get_object_or_404(ConferenceRoom, id=room_id)

    if request.method == 'POST':
        form = RoomForm(request.POST, request.FILES, instance=room)
        if form.is_valid():
            room = form.save()
            messages.success(request, f"Зал '{room.name}' обновлен")
            return redirect('bookings:room_management')
    else:
        form = RoomForm(instance=room)

    return render(request, 'bookings/room_form.html', {
        'form': form,
        'title': f'Редактирование зала: {room.name}'
    })


@moderator_required
def delete_room(request, room_id):
    """Удаление конференц-зала"""
    room = get_object_or_404(ConferenceRoom, id=room_id)

    has_future_bookings = Booking.objects.filter(
        room=room,
        status='approved',
        start_time__gte=timezone.now()
    ).exists()

    if request.method == 'POST':
        if has_future_bookings:
            messages.error(
                request,
                f"Нельзя удалить зал '{room.name}', так как у него есть будущие бронирования"
            )
        else:
            room.delete()
            messages.success(request, f"Зал '{room.name}' удален")
        return redirect('bookings:room_management')

    return render(request, 'bookings/room_confirm_delete.html', {
        'room': room,
        'has_future_bookings': has_future_bookings
    })


@moderator_required
def user_management(request):
    """Управление пользователями"""
    users = User.objects.all().order_by('-date_joined')

    role_filter = request.GET.get('role', 'all')
    active_filter = request.GET.get('active', 'all')

    if role_filter != 'all':
        users = users.filter(role=role_filter)

    if active_filter == 'active':
        users = users.filter(is_active=True)
    elif active_filter == 'inactive':
        users = users.filter(is_active=False)

    # Пагинация
    page = request.GET.get('page', 1)
    paginator = Paginator(users, 20)

    try:
        users = paginator.page(page)
    except PageNotAnInteger:
        users = paginator.page(1)
    except EmptyPage:
        users = paginator.page(paginator.num_pages)

    today = timezone.now().date()
    stats = {
        'total': User.objects.count(),
        'moderators': User.objects.filter(role='moderator').count(),
        'requesters': User.objects.filter(role='requester').count(),
        'employees': User.objects.filter(role='employee').count(),
        'active': User.objects.filter(is_active=True).count(),
        'new_today': User.objects.filter(date_joined__date=today).count(),
    }

    return render(request, 'bookings/user_management.html', {
        'users': users,
        'stats': stats,
        'role_filter': role_filter,
        'active_filter': active_filter
    })


@moderator_required
def create_user(request):
    """Создание нового пользователя модератором"""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                messages.success(request, f"Пользователь {user.username} успешно создан")
                return redirect('bookings:user_management')
            except Exception as e:
                messages.error(request, f"Ошибка при создании пользователя: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = UserRegistrationForm()

    return render(request, 'bookings/user_create.html', {
        'form': form,
        'title': 'Создание нового пользователя'
    })


@moderator_required
def edit_user(request, user_id):
    """Редактирование пользователя"""
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Данные пользователя {user.username} обновлены")
            return redirect('bookings:user_management')
    else:
        form = UserEditForm(instance=user)

    user_stats = {
        'total_bookings': Booking.objects.filter(requester=user).count(),
        'approved_bookings': Booking.objects.filter(requester=user, status='approved').count(),
        'pending_bookings': Booking.objects.filter(requester=user, status='pending').count(),
        'rejected_bookings': Booking.objects.filter(requester=user, status='rejected').count(),
    }

    return render(request, 'bookings/user_form.html', {
        'form': form,
        'edit_user': user,
        'stats': user_stats
    })


@moderator_required
def toggle_user_active(request, user_id):
    """Активация/деактивация пользователя"""
    user = get_object_or_404(User, id=user_id)

    if user == request.user:
        messages.error(request, "Вы не можете деактивировать свой собственный аккаунт")
        return redirect('bookings:user_management')

    if request.method == 'POST':
        user.is_active = not user.is_active
        user.save()
        status = "активирован" if user.is_active else "деактивирован"
        messages.success(request, f"Пользователь {user.username} {status}")

    return redirect('bookings:user_management')


# ==================== ДЛЯ ВСЕХ ПОЛЬЗОВАТЕЛЕЙ (КАЛЕНДАРЬ) ====================

@any_role_required
def schedule(request):
    """Просмотр расписания - только подтвержденные бронирования с корректным отображением времени"""
    selected_date_param = request.GET.get('date')
    room_id = request.GET.get('room')

    if selected_date_param:
        try:
            selected_date_obj = datetime.strptime(selected_date_param, '%Y-%m-%d').date()
        except ValueError:
            selected_date_obj = timezone.now().date()
    else:
        selected_date_obj = timezone.now().date()

    # Создаем временные границы дня в UTC
    day_start = timezone.make_aware(datetime.combine(selected_date_obj, datetime.min.time()))
    day_end = timezone.make_aware(datetime.combine(selected_date_obj, datetime.max.time()))

    # Получаем ТОЛЬКО ПОДТВЕРЖДЕННЫЕ бронирования на выбранную дату
    bookings = Booking.objects.filter(
        status='approved',
        start_time__gte=day_start,
        start_time__lte=day_end
    ).select_related('room', 'requester').order_by('start_time')

    if room_id:
        bookings = bookings.filter(room_id=room_id)

    rooms = ConferenceRoom.objects.filter(is_active=True)

    # Создаем структуру данных для календаря
    timeline = []

    # Часы с 7 до 16 (по локальному времени)
    for hour in range(7, 17):
        label = f"{hour:02d}:00"
        hour_data = []

        for room in rooms:
            room_bookings = []
            for booking in bookings:
                if booking.room.id == room.id:
                    # 🔥 КОНВЕРТИРУЕМ В ЛОКАЛЬНОЕ ВРЕМЯ перед сравнением
                    local_start = timezone.localtime(booking.start_time)
                    local_end = timezone.localtime(booking.end_time)

                    # Проверяем, что бронирование начинается в этот локальный час
                    if local_start.hour == hour:
                        # Добавляем локальное время для отображения в шаблоне
                        room_bookings.append({
                            'booking': booking,
                            'local_start': local_start,
                            'local_end': local_end,
                        })

            hour_data.append({
                'room': room,
                'bookings': room_bookings
            })

        timeline.append({
            'hour': hour,
            'label': label,
            'data': hour_data
        })

    # Даты для навигации
    dates = []
    for i in range(-3, 4):
        d = timezone.now().date() + timedelta(days=i)
        dates.append({
            'date': d,
            'display': d.strftime('%d.%m'),
            'is_today': d == timezone.now().date(),
            'is_selected': d == selected_date_obj
        })

    context = {
        'rooms': rooms,
        'selected_date': selected_date_obj,
        'timeline': timeline,
        'room_id': int(room_id) if room_id else None,
        'dates': dates,
        'prev_date': selected_date_obj - timedelta(days=1),
        'next_date': selected_date_obj + timedelta(days=1),
        'booking_settings': settings.BOOKING_SETTINGS,
        'now': timezone.now(),
        'user_role': request.user.role,
        'total_bookings': bookings.count(),
    }

    return render(request, 'bookings/schedule.html', context)


@any_role_required
def room_schedule(request, room_id):
    """Расписание для конкретного зала"""
    room = get_object_or_404(ConferenceRoom, id=room_id, is_active=True)

    selected_date_param = request.GET.get('date')
    if selected_date_param:
        try:
            selected_date_obj = datetime.strptime(selected_date_param, '%Y-%m-%d').date()
        except ValueError:
            selected_date_obj = timezone.now().date()
    else:
        selected_date_obj = timezone.now().date()

    day_start = timezone.make_aware(datetime.combine(selected_date_obj, datetime.min.time()))
    day_end = timezone.make_aware(datetime.combine(selected_date_obj, datetime.max.time()))

    # Получаем только подтвержденные бронирования для конкретного зала
    bookings = Booking.objects.filter(
        room=room,
        status='approved',
        start_time__gte=day_start,
        start_time__lte=day_end
    ).order_by('start_time')

    # Конвертируем время в локальное для отображения
    bookings_data = []
    for booking in bookings:
        bookings_data.append({
            'booking': booking,
            'local_start': timezone.localtime(booking.start_time),
            'local_end': timezone.localtime(booking.end_time),
        })

    return render(request, 'bookings/room_schedule.html', {
        'room': room,
        'bookings': bookings_data,
        'selected_date': selected_date_obj,
        'booking_settings': settings.BOOKING_SETTINGS,
        'now': timezone.now(),
        'user_role': request.user.role,
    })


@any_role_required
def export_schedule(request):
    """Экспорт расписания в CSV (только подтвержденные бронирования)"""
    selected_date_param = request.GET.get('date')

    if selected_date_param:
        try:
            selected_date_obj = datetime.strptime(selected_date_param, '%Y-%m-%d').date()
        except ValueError:
            selected_date_obj = timezone.now().date()
    else:
        selected_date_obj = timezone.now().date()

    day_start = timezone.make_aware(datetime.combine(selected_date_obj, datetime.min.time()))
    day_end = timezone.make_aware(datetime.combine(selected_date_obj, datetime.max.time()))

    # Экспортируем только подтвержденные бронирования
    bookings = Booking.objects.filter(
        status='approved',
        start_time__gte=day_start,
        start_time__lte=day_end
    ).select_related('room', 'requester').order_by('room__name', 'start_time')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="schedule_{selected_date_obj.strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Зал', 'Мероприятие', 'Организатор', 'Начало', 'Окончание', 'Количество участников'])

    for booking in bookings:
        # Используем localtime для корректного времени в экспорте
        local_start = timezone.localtime(booking.start_time)
        local_end = timezone.localtime(booking.end_time)
        writer.writerow([
            booking.room.name,
            booking.title,
            booking.requester.get_full_name() or booking.requester.username,
            local_start.strftime('%H:%M'),
            local_end.strftime('%H:%M'),
            booking.participants_count
        ])

    return response
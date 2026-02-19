from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    # Аутентификация
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Главная и профиль
    path('', views.index, name='index'),
    path('profile/', views.profile, name='profile'),

    # Для заявителя
    path('create-booking/', views.create_booking, name='create_booking'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('booking/<int:booking_id>/', views.booking_detail, name='booking_detail'),
    path('booking/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),

    # Для модератора
    path('moderator/dashboard/', views.moderator_dashboard, name='moderator_dashboard'),
    path('moderator/moderate/<int:booking_id>/', views.moderate_booking, name='moderate_booking'),
    path('moderator/rooms/', views.room_management, name='room_management'),
    path('moderator/rooms/create/', views.create_room, name='create_room'),
    path('moderator/rooms/<int:room_id>/edit/', views.edit_room, name='edit_room'),
    path('moderator/rooms/<int:room_id>/delete/', views.delete_room, name='delete_room'),
    path('moderator/users/', views.user_management, name='user_management'),
    path('moderator/users/create/', views.create_user, name='create_user'),
    path('moderator/users/<int:user_id>/edit/', views.edit_user, name='edit_user'),
    path('moderator/users/<int:user_id>/toggle-active/', views.toggle_user_active, name='toggle_user_active'),

    # Для сотрудника и всех
    path('schedule/', views.schedule, name='schedule'),
    path('schedule/room/<int:room_id>/', views.room_schedule, name='room_schedule'),
    path('schedule/export/', views.export_schedule, name='export_schedule'),

    # API
    path('api/check-availability/', views.check_availability, name='check_availability'),
]
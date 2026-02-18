from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def moderator_required(view_func):
    """Декоратор для проверки прав модератора"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == 'moderator':
            return view_func(request, *args, **kwargs)
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('bookings:index')
    return _wrapped_view

def requester_required(view_func):
    """Декоратор для проверки прав заявителя"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == 'requester':
            return view_func(request, *args, **kwargs)
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('bookings:index')
    return _wrapped_view

def employee_required(view_func):
    """Декоратор для проверки прав сотрудника"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == 'employee':
            return view_func(request, *args, **kwargs)
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('bookings:index')
    return _wrapped_view

def any_role_required(view_func):
    """Декоратор для любой авторизованной роли"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        messages.error(request, "Пожалуйста, войдите в систему")
        return redirect('bookings:login')  # Исправлено: добавлен namespace
    return _wrapped_view
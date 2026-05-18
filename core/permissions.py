from rest_framework import permissions

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'Admin'

class IsManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['Admin', 'Manager']

class IsAttendant(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['Admin', 'Manager', 'Attendant']

class IsCustomer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

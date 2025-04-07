from django.urls import path
from . import views



urlpatterns = [
    # Authentication
    path('register/', views.register, name='register'),
    path('', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
     path('profile/complete/', views.profile_complete, name='profile_complete'),
    path('api/departments/', views.load_departments, name='load_departments'),
    # Location APIs
    path('update-location/', views.update_location, name='update_location'),
    path('location-history/', views.location_history, name='location_history'),
    
    # Geofencing
    path('geofence-violations/', views.geofence_violations, name='geofence_violations'),
    
    # Intern Management
    path('interns/', views.intern_list, name='intern_list'),
    path('interns/<int:pk>/', views.intern_detail, name='intern_detail'),
]
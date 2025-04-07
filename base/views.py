import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from geopy.geocoders import Nominatim
from .models import User, Organization, InternProfile, LocationLog, Department
from .forms import InternRegistrationForm, OrganizationForm, CustomAuthenticationForm
from datetime import datetime, timedelta
from django.contrib.auth import logout, authenticate, login



# Utility Functions
def get_address_from_coords(lat, lng):
    """Reverse geocode coordinates to get address"""
    geolocator = Nominatim(user_agent="intern_tracker")
    location = geolocator.reverse(f"{lat}, {lng}")
    return location.address if location else "Unknown location"

def check_geofence(point, organization):
    """Check if point is within organization's geofence"""
    return organization.location.distance(point) * 100000 <= organization.geofence_radius

# Authentication Views
def register(request):
    if request.method == 'POST':
        form = InternRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = InternRegistrationForm()
    
    return render(request, 'register.html', {'form': form})

def load_departments(request):
    """AJAX endpoint for loading departments"""
    org_id = request.GET.get('organization')
    departments = Department.objects.filter(
        organization_id=org_id,
        is_active=True
    ).order_by('name')
    return render(request, 'departments_dropdown.html', {'departments': departments})

def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.first_name}!")
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'login.html', {'form': form})

# Dashboard Views
@login_required
def dashboard(request):
    if not hasattr(request.user, 'internprofile'):
        return redirect('profile_complete')
    
    intern = request.user.internprofile
    org = intern.organization
    today = datetime.now().date()
    
    # Get today's locations
    locations = LocationLog.objects.filter(
        intern=intern,
        timestamp__date=today
    ).order_by('-timestamp')[:10]
    
    # Geofence violation count
    violations_today = LocationLog.objects.filter(
        intern=intern,
        is_inside_geofence=False,
        timestamp__date=today
    ).count()
    
    context = {
        'intern': intern,
        'organization': org,
        'locations': locations,
        'violations_today': violations_today,
        'mapbox_access_token': 'your_mapbox_access_token',
    }
    return render(request, 'dashboard.html', context)
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Department

@require_GET
def get_departments(request):
    """API endpoint for fetching departments by organization"""
    org_id = request.GET.get('organization')
    
    if not org_id:
        return JsonResponse([], safe=False)
    
    departments = Department.objects.filter(
        organization_id=org_id,
        is_active=True
    ).order_by('name').values('id', 'name')
    
    return JsonResponse(list(departments), safe=False)

def profile_complete(request):
    if hasattr(request.user, 'internprofile'):
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = ProfileCompletionForm(request.POST, user=request.user)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            return redirect('dashboard')
    else:
        form = ProfileCompletionForm(user=request.user)
    
    # Get initial departments if user already has an organization selected
    departments = []
    if hasattr(request.user, 'internprofile') and request.user.internprofile.organization:
        departments = Department.objects.filter(
            organization=request.user.internprofile.organization,
            is_active=True
        ).order_by('name')
    
    return render(request, 'profile_complete.html', {
        'form': form,
        'departments': departments
    })

# Location Tracking API
@csrf_exempt
@login_required
def update_location(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat = float(data['latitude'])
            lng = float(data['longitude'])
            point = Point(lng, lat, srid=4326)
            
            intern = request.user.internprofile
            org = intern.organization
            
            # Check geofence status
            is_inside = check_geofence(point, org)
            address = get_address_from_coords(lat, lng)
            
            # Save location
            LocationLog.objects.create(
                intern=intern,
                point=point,
                accuracy=data.get('accuracy'),
                address=address,
                is_inside_geofence=is_inside
            )
            
            return JsonResponse({
                'status': 'success',
                'is_inside': is_inside,
                'address': address
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=405)

# Intern Management
@login_required
def intern_list(request):
    if not request.user.is_supervisor:
        messages.error(request, "You don't have permission to view this page")
        return redirect('dashboard')
    
    organization = request.user.supervisorprofile.organization
    interns = InternProfile.objects.filter(organization=organization)
    
    return render(request, 'list.html', {
        'interns': interns,
        'organization': organization
    })

@login_required
def intern_detail(request, pk):
    intern = get_object_or_404(InternProfile, pk=pk)
    
    # Verify supervisor has access to this intern
    if (request.user.is_supervisor and 
        request.user.supervisorprofile.organization != intern.organization):
        messages.error(request, "You don't have permission to view this intern")
        return redirect('intern_list')
    
    # Get time filter from query params
    time_filter = request.GET.get('time', 'today')
    
    if time_filter == 'week':
        date_filter = datetime.now() - timedelta(days=7)
    elif time_filter == 'month':
        date_filter = datetime.now() - timedelta(days=30)
    else:  # today
        date_filter = datetime.now() - timedelta(days=1)
    
    locations = LocationLog.objects.filter(
        intern=intern,
        timestamp__gte=date_filter
    ).order_by('-timestamp')
    
    violations = locations.filter(is_inside_geofence=False)
    
    return render(request, 'detail.html', {
        'intern': intern,
        'locations': locations[:50],  # Limit to 50 most recent
        'violations': violations.count(),
        'time_filter': time_filter
    })

# Organization Management
@login_required
def organization_dashboard(request):
    if not request.user.is_supervisor:
        messages.error(request, "Access denied")
        return redirect('dashboard')
    
    org = request.user.supervisorprofile.organization
    interns = InternProfile.objects.filter(organization=org)
    
    # Stats for dashboard
    active_interns = interns.filter(is_active=True).count()
    violations_today = LocationLog.objects.filter(
        intern__organization=org,
        is_inside_geofence=False,
        timestamp__date=datetime.now().date()
    ).count()
    
    return render(request, 'dashboard.html', {
        'organization': org,
        'active_interns': active_interns,
        'violations_today': violations_today,
        'mapbox_access_token': 'your_mapbox_access_token'
    })

@login_required
def edit_organization(request):
    if not request.user.is_supervisor:
        messages.error(request, "Access denied")
        return redirect('dashboard')
    
    org = request.user.supervisorprofile.organization
    
    if request.method == 'POST':
        form = OrganizationForm(request.POST, instance=org)
        if form.is_valid():
            form.save()
            messages.success(request, "Organization updated successfully")
            return redirect('organization_dashboard')
    else:
        form = OrganizationForm(instance=org)
    
    return render(request, 'edit.html', {'form': form})

# Reporting Views
@login_required
def location_history(request):
    intern = request.user.internprofile
    time_filter = request.GET.get('time', 'today')
    
    if time_filter == 'week':
        date_filter = datetime.now() - timedelta(days=7)
    elif time_filter == 'month':
        date_filter = datetime.now() - timedelta(days=30)
    else:  # today
        date_filter = datetime.now() - timedelta(days=1)
    
    locations = LocationLog.objects.filter(
        intern=intern,
        timestamp__gte=date_filter
    ).order_by('-timestamp')
    
    return render(request, 'location_history.html', {
        'locations': locations,
        'time_filter': time_filter
    })

@login_required
def geofence_violations(request):
    if request.user.is_intern:
        intern = request.user.internprofile
        violations = LocationLog.objects.filter(
            intern=intern,
            is_inside_geofence=False
        ).order_by('-timestamp')
    else:  # supervisor
        org = request.user.supervisorprofile.organization
        violations = LocationLog.objects.filter(
            intern__organization=org,
            is_inside_geofence=False
        ).order_by('-timestamp')
    
    return render(request, 'geofence_violations.html', {
        'violations': violations
    })

def user_logout(request):
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('login')  
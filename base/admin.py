from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.contrib.auth.admin import UserAdmin
from .models import User, Organization, InternProfile, LocationLog, Department
from django.contrib.gis.geos import Point
from geopy.geocoders import Nominatim
from django.db.models import Count
from django.utils.html import format_html

from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.contrib import messages





class DepartmentInline(admin.TabularInline):
    model = Department
    extra = 1



@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'organization', 'is_active')
    list_filter = ('organization', 'is_active')
    search_fields = ('name', 'code')






# Custom User Admin
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 
                   'is_intern', 'is_supervisor', 'is_staff')
    list_filter = ('is_intern', 'is_supervisor', 'is_staff', 'is_superuser')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 
                      'is_intern', 'is_supervisor', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    actions = ['mark_as_intern', 'mark_as_supervisor']

    def mark_as_intern(self, request, queryset):
        queryset.update(is_intern=True)
    mark_as_intern.short_description = "Mark selected users as interns"

    def mark_as_supervisor(self, request, queryset):
        queryset.update(is_supervisor=True)
    mark_as_supervisor.short_description = "Mark selected users as supervisors"

# Organization Admin with Auto-Location
# @admin.register(Organization)
# class OrganizationAdmin(GISModelAdmin):
#     list_display = ('name', 'location_preview', 'geofence_radius', 
#                    'intern_count', 'location_source')
#     list_editable = ('geofence_radius',)
#     search_fields = ('name', 'address')
#     actions = ['geocode_addresses', 'calculate_optimal_radius']
#     readonly_fields = ('location_source',)
#     fieldsets = (
#         (None, {
#             'fields': ('name', 'address', 'location_source')
#         }),
#         ('Location Settings', {
#             'fields': ('location', 'geofence_radius'),
#             'classes': ('collapse',)
#         }),
#     )

#     def location_preview(self, obj):
#         if obj.location:
#             return format_html(
#                 '<a href="https://maps.google.com/?q={},{}" target="_blank">📍 View on Map</a>',
#                 obj.location.y, obj.location.x
#             )
#         return "Not set"
#     location_preview.short_description = "Location"

#     def intern_count(self, obj):
#         return obj.internprofile_set.count()
#     intern_count.short_description = "Interns"

#     def geocode_addresses(self, request, queryset):
#         geolocator = Nominatim(user_agent="org_locator")
#         for org in queryset:
#             if org.address and not org.location:
#                 try:
#                     location = geolocator.geocode(org.address)
#                     if location:
#                         org.location = Point(location.longitude, location.latitude)
#                         org.location_source = 'geocode'
#                         org.save()
#                         self.message_user(request, f"Geocoded {org.name}")
#                 except Exception as e:
#                     self.message_user(request, f"Failed to geocode {org.name}: {str(e)}", level='error')
#     geocode_addresses.short_description = "Geocode addresses"

#     def calculate_optimal_radius(self, request, queryset):
#         from django.contrib.gis.db.models.functions import Distance
#         for org in queryset:
#             if org.location:
#                 checkins = LocationLog.objects.filter(
#                     intern__organization=org
#                 ).annotate(
#                     distance=Distance('point', org.location)
#                 ).order_by('-distance')
                
#                 if checkins.exists():
#                     index = int(len(checkins) * 0.95)  # Cover 95% of checkins
#                     org.geofence_radius = checkins[index].distance.m
#                     org.save()
#                     self.message_user(request, f"Updated radius for {org.name}")
#     calculate_optimal_radius.short_description = "Calculate optimal radius"

#     def save_model(self, request, obj, form, change):
#         if not obj.location_source:
#             if obj.location:
#                 obj.location_source = 'manual'
#             elif obj.address:
#                 obj.location_source = 'geocode'
#             else:
#                 obj.location_source = 'pending'
#         super().save_model(request, obj, form, change)






@admin.register(Organization)
class OrganizationAdmin(GISModelAdmin):
    list_display = ('name', 'location_status', 'geofence_radius', 'get_intern_count')
    list_editable = ('geofence_radius',)
    actions = ['geocode_selected']
    fieldsets = (
        (None, {
            'fields': ('name', 'address')
        }),
        ('Location Settings', {
            'fields': ('location', 'geofence_radius', 'location_source'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('location_source',)

    def location_status(self, obj):
        if obj.location:
            return format_html(
                '<a href="https://maps.google.com/?q={},{}" target="_blank">📍 View Map</a>',
                obj.location.y, obj.location.x
            )
        return "❌ Not located" if obj.address else "—"
    location_status.short_description = "Location"

    def get_intern_count(self, obj):
        return obj.internprofile_set.count()
    get_intern_count.short_description = "Interns"

    def geocode_selected(self, request, queryset):
        for org in queryset:
            if org.address and not org.location:
                if org.geocode_from_address():
                    org.save()
                    self.message_user(
                        request, 
                        f"Successfully geocoded {org.name}", 
                        messages.SUCCESS
                    )
                else:
                    self.message_user(
                        request,
                        f"Failed to geocode {org.name}",
                        messages.ERROR
                    )
    geocode_selected.short_description = "Geocode selected organizations"

    def save_model(self, request, obj, form, change):
        if not obj.location and obj.address:
            obj.location_source = 'geocode'
        super().save_model(request, obj, form, change)




# Intern Profile Admin
@admin.register(InternProfile)
class InternProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'department', 'phone_number', 'is_active')
    list_filter = ('organization', 'department', 'is_active')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone_number')
    raw_id_fields = ('user',)
    list_editable = ('is_active',)
    actions = ['activate_profiles', 'deactivate_profiles']

    def activate_profiles(self, request, queryset):
        queryset.update(is_active=True)
    activate_profiles.short_description = "Activate selected profiles"

    def deactivate_profiles(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_profiles.short_description = "Deactivate selected profiles"

# Location Log Admin
@admin.register(LocationLog)
class LocationLogAdmin(GISModelAdmin):
    list_display = ('intern', 'timestamp', 'status', 'address_short', 'accuracy')
    list_filter = ('is_inside_geofence', 'intern__organization', 'timestamp')
    search_fields = ('intern__user__username', 'address')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'

    def status(self, obj):
        color = 'green' if obj.is_inside_geofence else 'red'
        text = 'Inside' if obj.is_inside_geofence else 'Outside'
        return format_html(
            '<span style="color: {};">{}</span>',
            color, text
        )
    status.short_description = "Geofence Status"

    def address_short(self, obj):
        return obj.address[:50] + '...' if obj.address else ''
    address_short.short_description = "Address"

    def save_model(self, request, obj, form, change):
        # Auto-set organization location if not set
        if not obj.intern.organization.location:
            obj.intern.organization.location = obj.point
            obj.intern.organization.location_source = 'first_checkin'
            obj.intern.organization.save()
        super().save_model(request, obj, form, change)
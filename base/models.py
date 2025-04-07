from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point
from django.conf import settings
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import logging
from django.core.validators import MinLengthValidator

class User(AbstractUser):
    is_intern = models.BooleanField(default=False)
    is_supervisor = models.BooleanField(default=False)


    class Meta:
        # Add this to avoid clashes
        swappable = 'AUTH_USER_MODEL'
    
    # Specify unique related_names
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='base_user_set',  # Changed from 'user_set'
        related_query_name='user'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='base_user_set',  # Changed from 'user_set'
        related_query_name='user'
    )








logger = logging.getLogger(__name__)




class Department(models.Model):
    organization = models.ForeignKey(
        'Organization', 
        on_delete=models.CASCADE,
        related_name='departments'
    )
    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=10,
        validators=[MinLengthValidator(2)],
        unique=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        unique_together = ('organization', 'name')

    def __str__(self):
        return f"{self.name} ({self.organization})"

class Organization(models.Model):
    name = models.CharField(max_length=255)
    location = gis_models.PointField(null=True, blank=True)
    geofence_radius = models.PositiveIntegerField(
        default=100,  # Default 100m radius
        help_text="Radius in meters"
    )
    address = models.TextField(blank=True)
    
    LOCATION_SOURCE_CHOICES = [
        ('manual', 'Manual Entry'),
        ('geocode', 'Geocode from Address'),
        ('first_checkin', 'Derive from First Intern Check-in'),
        ('pending', 'Pending Automatic Detection')
    ]
    location_source = models.CharField(
        max_length=20,
        choices=LOCATION_SOURCE_CHOICES,
        default='pending'
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.location_source == 'geocode' and self.address and not self.location:
            self.geocode_from_address()
        super().save(*args, **kwargs)
    
    def geocode_from_address(self):
        try:
            geolocator = Nominatim(user_agent="your_app_name")
            location = geolocator.geocode(self.address)
            if location:
                self.location = Point(location.longitude, location.latitude)
                self.location_source = 'geocode'
                return True
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.error(f"Geocoding failed for {self.name}: {str(e)}")
        return False

    class Meta:
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"




# class Organization(models.Model):
#     name = models.CharField(max_length=255)
#     location = gis_models.PointField(null=True, blank=True)
#     geofence_radius = models.PositiveIntegerField(
#         default=100,  # Default 100m radius
#         help_text="Radius in meters"
#     )
#     address = models.TextField(blank=True)
    
#     AUTO_LOCATION_CHOICES = [
#         ('manual', 'Manual Entry'),
#         ('geocode', 'Geocode from Address'),
#         ('first_checkin', 'Derive from First Intern Check-in')
#     ]
#     location_source = models.CharField(
#         max_length=20,
#         choices=AUTO_LOCATION_CHOICES,
#         default='first_checkin'
#     )

#     def save(self, *args, **kwargs):
#         if self.location_source == 'geocode' and self.address:
#             self.geocode_from_address()
#         super().save(*args, **kwargs)
    
#     def geocode_from_address(self):
#         geolocator = Nominatim(user_agent="org_locator")
#         location = geolocator.geocode(self.address)
#         if location:
#             self.location = Point(location.longitude, location.latitude)

class InternProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,related_name='intern_profile')
    department = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.department})"

    

class LocationLog(models.Model):
    intern = models.ForeignKey(InternProfile, on_delete=models.CASCADE)
    point = gis_models.PointField()
    timestamp = models.DateTimeField(auto_now_add=True)
    accuracy = models.FloatField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    is_inside_geofence = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        status = "Inside" if self.is_inside_geofence else "Outside"
        return f"{self.intern} at {self.point} ({status})"
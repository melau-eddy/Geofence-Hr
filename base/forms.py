# base/forms.py
# from django import forms
# from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
# from .models import User, Organization, InternProfile
# from django.contrib.auth import get_user_model

# class InternRegistrationForm(UserCreationForm):
#     phone_number = forms.CharField(max_length=20)
#     department = forms.CharField(max_length=100)
#     organization = forms.ModelChoiceField(queryset=Organization.objects.all())
    
#     class Meta(UserCreationForm.Meta):
#         fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email')
    
#     def save(self, commit=True):
#         user = super().save(commit=False)
#         if commit:
#             user.save()
#             InternProfile.objects.create(
#                 user=user,
#                 phone_number=self.cleaned_data['phone_number'],
#                 department=self.cleaned_data['department'],
#                 organization=self.cleaned_data['organization']
#             )
#         return user

# class OrganizationForm(forms.ModelForm):
#     class Meta:
#         model = Organization
#         fields = ['name', 'location', 'geofence_radius', 'address']
#         widgets = {
#             'location': forms.HiddenInput()  # We'll handle this via Leaflet
#         }


# User = get_user_model()

# class CustomAuthenticationForm(AuthenticationForm):
#     username = forms.CharField(
#         widget=forms.TextInput(attrs={
#             'class': 'form-control',
#             'placeholder': 'Username',
#             'autofocus': True
#         })
#     )
#     password = forms.CharField(
#         widget=forms.PasswordInput(attrs={
#             'class': 'form-control',
#             'placeholder': 'Password'
#         })
#     )

# class InternRegistrationForm(UserCreationForm):
#     class Meta(UserCreationForm.Meta):
#         fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email')


# class ProfileCompletionForm(forms.ModelForm):
#     class Meta:
#         model = InternProfile
#         fields = ['department', 'phone_number', 'organization']
#         widgets = {
#             'organization': forms.Select(attrs={'class': 'form-control'}),
#         }



from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model
from .models import Organization, InternProfile, Department
from django.contrib.gis.geos import Point
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Department, Organization

class InternRegistrationForm(UserCreationForm):
    phone_number = forms.CharField(max_length=20, required=True)
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        required=True
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.none(),  # Will be populated in __init__
        required=True
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + (
            'first_name', 'last_name', 'email', 
            'phone_number', 'organization', 'department'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If organization is already selected (form re-display), show its departments
        if 'organization' in self.data:
            try:
                org_id = int(self.data.get('organization'))
                self.fields['department'].queryset = Department.objects.filter(
                    organization_id=org_id,
                    is_active=True
                ).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and hasattr(self.instance, 'internprofile'):
            self.fields['department'].queryset = self.instance.internprofile.organization.departments.all()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_intern = True
        
        if commit:
            user.save()
            # Create intern profile with all additional fields
            InternProfile.objects.create(
                user=user,
                phone_number=self.cleaned_data['phone_number'],
                organization=self.cleaned_data['organization'],
                department=self.cleaned_data['department']
            )
        return user
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_intern = True  # Automatically set as intern
        
        if commit:
            user.save()
        return user


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['name', 'address', 'geofence_radius']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'geofence_radius': forms.NumberInput(attrs={'min': 10}),
        }
    
    def clean_geofence_radius(self):
        radius = self.cleaned_data['geofence_radius']
        if radius < 10:
            raise forms.ValidationError("Geofence radius must be at least 10 meters")
        return radius
    
    def save(self, commit=True):
        organization = super().save(commit=False)
        if organization.location_source == 'geocode' and organization.address:
            try:
                geolocator = Nominatim(user_agent="org_locator")
                location = geolocator.geocode(organization.address)
                if location:
                    organization.location = Point(location.longitude, location.latitude)
            except (GeocoderTimedOut, GeocoderServiceError) as e:
                logger.error(f"Geocoding failed: {str(e)}")
                # You might want to handle this differently
        
        if commit:
            organization.save()
        return organization
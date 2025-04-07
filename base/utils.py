from django.contrib.gis.geos import Point
from geopy.distance import geodesic

def check_geofence(lat, lng, org_point, radius_meters):
    """Check if a point is within the geofence radius"""
    org_coords = (org_point.y, org_point.x)
    point_coords = (lat, lng)
    distance = geodesic(org_coords, point_coords).meters
    return distance <= radius_meters
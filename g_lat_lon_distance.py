#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014 Patrick Moran for Verizon
#
# Distributes WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with the Iscan device.  If not, see <http://www.gnu.org/licenses/>.

import math
# from http://www.johndcook.com/python_longitude_latitude.html


def compute_resolution(distance):
    new_lat, new_lon = move_to_lat_lon(42., 74., distance, 0)
    difference = math.fabs(new_lat-42.0)
    resolution = int(math.ceil(math.fabs(math.log10(difference))))
    return resolution


def lat_lon_distance(lat1, long1, lat2, long2,  units='mi'):
    """
    distance = d(lat1, long1, lat2, long2,  units='mi')
        lat1, long1 : lat and lon of 1st point
        lat2, long2 : lat and lon of 2nd point
        units='mi' : units to use for returning distance (default is miles)
    """
    # Convert latitude and longitude to
    # spherical coordinates in radians.
    try:
        degrees_to_radians = math.pi/180.0

        # phi = 90 - latitude
        phi1 = (90.0 - lat1) * degrees_to_radians
        phi2 = (90.0 - lat2) * degrees_to_radians

        # theta = longitude
        theta1 = long1*degrees_to_radians
        theta2 = long2*degrees_to_radians

        # Compute spherical distance from spherical coordinates.

        # For two locations in spherical coordinates
        # (1, theta, phi) and (1, theta, phi)
        # cosine( arc length ) =
        #    sin phi sin phi' cos(theta-theta') + cos phi cos phi'
        # distance = rho * arc length

        this_cos = (math.sin(phi1) * math.sin(phi2) * math.cos(theta1 - theta2) + math.cos(phi1) * math.cos(phi2))
        arc = math.acos(this_cos)
    except ValueError:
        arc = 0.01

    # Remember to multiply arc by the radius of the earth
    # in your favorite set of units to get length.
    if units.lower().find('mi') >= 0:
        radius = 3956.0 # miles(at 48.46791 degrees north) see http://en.wikipedia.org/wiki/Earth_radius
    else:
        radius = 6366.0 # km
    return arc * radius


def move_to_lat_lon(lat_a, lon_a, distance, direction,  units='mi'):
    if units.lower().find('mi') >= 0:
        radius = 3956.0  # miles(at 48.46791 degrees north) see http://en.wikipedia.org/wiki/Earth_radius
    else:
        radius = 6366.0  # km
    bearing = math.radians(direction)
    lat1 = math.radians(lat_a)
    lon1 = math.radians(lon_a)
    lat_b = math.asin(
        math.sin(lat1) * math.cos(distance / radius) +
        math.cos(lat1) * math.sin(distance / radius) * math.cos(bearing)
    )
    lon_b = lon1 + math.atan2(math.sin(bearing) * math.sin(distance / radius) * math.cos(lat1),
                              math.cos(distance / radius) - math.sin(lat1) * math.sin(lat_b))
    lat2 = math.degrees(lat_b)
    lon2 = math.degrees(lon_b)
    return lat2, lon2

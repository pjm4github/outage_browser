#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014 Patrick Moran for Verizon
#
# Distributes WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License. If not, see <http://www.gnu.org/licenses/>.

import math
# from http://www.johndcook.com/python_longitude_latitude.html


def lat_lon_distance(lat1, long1, lat2, long2,  units='mi'):
    """
    distance = lat_lon_distance(lat1, long1, lat2, long2,  units='mi')
        lat1, long1 : lat and lon of 1st point
        lat2, long2 : lat and lon of 2nd point
        units='mi' : units to use for returning distance (default is miles)
    """
    # Convert latitude and longitude to
    # spherical coordinates in radians.
    degrees_to_radians = math.pi/180.0

    # phi = 90 - latitude
    phi1 = (90.0 - lat1)*degrees_to_radians
    phi2 = (90.0 - lat2)*degrees_to_radians

    # theta = longitude
    theta1 = long1*degrees_to_radians
    theta2 = long2*degrees_to_radians

    # Compute spherical distance from spherical coordinates.

    # For two locations in spherical coordinates
    # (1, theta, phi) and (1, theta, phi)
    # cosine( arc length ) =
    #    sin phi sin phi' cos(theta-theta') + cos phi cos phi'
    # distance = rho * arc length

    cosV = (math.sin(phi1)*math.sin(phi2)*math.cos(theta1 - theta2) +
           math.cos(phi1)*math.cos(phi2))
    arc = math.acos( cosV )

    # Remember to multiply arc by the radius of the earth
    # in your favorite set of units to get length.
    if units.lower().find('mi')>=0:
        R = 3956.0 # miles(at 48.46791 degrees north) see http://en.wikipedia.org/wiki/Earth_radius
    else:
        R = 6366.0 # km
    return arc * R

def distance_lat_lon(lati1, long1, distance, heading,  units='mi'):
    """
    (lat,lon) = distance_lat_lon(lati1, long1, distance, heading,  units='mi')
        lati1, long1 : lat and lon of 1st point
        distance : distance away from lat1, long1
        heading : direction of travel (in degrees) from north
        units='mi' : units to use for returning distance (default is miles)
    """
    # Convert latitude and longitude to
    # Remember to multiply arc by the radius of the earth
    # in your favorite set of units to get length.
    if units.lower().find('mi')>=0:
        R = 3956.0 # miles(at 48.46791 degrees north) see http://en.wikipedia.org/wiki/Earth_radius
    else:
        R = 6366.0 # km

    degrees_to_radians = math.pi/180.0

    # phi = 90 - latitude

    brng = (heading)*degrees_to_radians #Bearing in degrees converted to radians.
    d = distance #Distance in km or mi

    lat1 = math.radians(lati1) #Current lat point converted to radians
    lon1 = math.radians(long1) #Current long point converted to radians

    lat2 = math.asin( math.sin(lat1)*math.cos(d/R) +
         math.cos(lat1)*math.sin(d/R)*math.cos(brng))

    lon2 = lon1 + math.atan2(math.sin(brng)*math.sin(d/R)*math.cos(lat1),
                 math.cos(d/R)-math.sin(lat1)*math.sin(lat2))

    return ( math.degrees(lat2), math.degrees(lon2))


def distance_lat_lon_approx(lati1, long1, distance, heading,  units='mi'):
    a=math.radians(heading)

    c_a=math.cos(a) #cos(30 degrees) = cos(pi/6 radians) = Sqrt(3)/2 = 0.866025.
    s_a=math.sin(a) # sin(30 degrees) = sin(pi/6 radians) = 1/2 = 0.5.

    c_lat1=math.cos(math.radians(lati1)) # latitude) = cos(-0.31399 degrees) = cos(-0.00548016 radian) = 0.999984984.
    if units.lower().find('mi')>=0:
        r=distance*1609.34  # return meters
    else:
        r=distance*10000 # return meters
    #r = 100 meters.
    #r * cos(a) / 111111 degrees;
    north_displacement = r * c_a /111111 # 100 * 0.5 / 0.999984984 / 111111 = 0.000450007 degree.
    # r * sin(a) / cos(latitude) / 111111 degrees.
    east_displacement  = r * s_a /c_lat1 /111111 # 100 * 0.866025 / 111111 = 0.000779423 degree.
    # Whence, starting at (-78.4437, -0.31399), the new location is at (-78.4437 + 0.00045, -0.31399 + 0.0007794) = (-78.4432, -0.313211).
    lat2 = lati1 + north_displacement
    lon2 = long1 + east_displacement
    return (lat2, lon2)

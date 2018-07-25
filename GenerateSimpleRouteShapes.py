# Nick Ubels
# Based on the original version by Ben Kotrc, 1/26/2016 on https://github.com/kotrc/GTFS-route-shapes
#This script takes an expanded GTFS file and generates a new file,
#route_shapes.json, that contains one geojson MultiLineString for each
#entry in the GTFS routes.txt table. This represents the map shape for
#each route, including possible variations/line branches/etc, simplified
#using the Douglas-Peucker algorithm for a minimal resulting file size.

#Approach:
#For each route,
#1 - Get the set of shapes corresponding to the route;
#2 - Select the longest shape (with the most coordinate pairs);
#3 - Draw a buffer around this longest shape;
#4 - For each remaining shape,
#a - Remove points from the shape within the buffered area,
#b - Add the remaining shape to the longest shape as an additional
#    LineString in the MultiLineString

#Run this from within a directory containing the GTFS csv files.

#pandas lets us use data frames to load and store the GTFS tables
import pandas as pd
#geojson lets us construct and dump geojson objects
import geojson as gj
#shapely lets us manipulate geometric objects
import shapely.geometry as sh

print("Step 1: Starting to load data")

#Read relevant GTFS tables to pandas dataframes
#Load the shapes
shapes = pd.read_csv('shapes.txt')
# Load only the route_id, agency_id, route_short_name and route_long_name of the routes file
routes = pd.read_csv('routes.txt',usecols=['route_id','agency_id','route_short_name','route_long_name'])
# Load only the route_id and shape_id for the trips
trips = pd.read_csv('trips.txt'usecols=['route_id','shape_id'])

# Removing the duplicated trips before joining
print("Loading data finished. \n Step 2: Removing duplicate trips")
trips.drop_duplicates(inplace = True)

#Join routes table to trips table on route_id
print("Removing duplicates finished \n Step 3: Joining routes and trips")
routes_trips = pd.merge(routes, trips, on='route_id', how='inner')
#Join this table to shapes on shape_id
print("Joining routes and trips finished \n Step 4: Joining shapes to trips")
routes_trips_shapes = pd.merge(routes_trips, shapes, on='shape_id',
    how='inner')

#Since we've thrown out all the columns dealing with trips, there will be a lot
#of duplicate rows. Let's get rid of those.
routes_trips_shapes = routes_trips_shapes.drop_duplicates()

#Create a list to hold each route's shape to write them to file at the end:
route_shape_list = list()

#Go through each route
for route_id in routes_trips_shapes['route_id'].unique():
    #Get the set of shapes corresponding to this route_id
    shape_ids = set(routes_trips_shapes[routes_trips_shapes['route_id']
            == route_id]['shape_id'])
    #First, find the longest shape for this route
    #Call the first shape in this route the longest to start with
    longest = shape_ids.pop()
    shape_ids.add(longest)
    #Keep track of how many points the longest shape has
    longest_pt_num = shapes[shapes['shape_id']
        == longest]['shape_pt_sequence'].count()
    #Go through each shape in this route
    for shape_id in shape_ids:
        #If this shape has more points in this shape with the longest so far
        if shapes[shapes['shape_id']
            == shape_id]['shape_pt_sequence'].count() > longest_pt_num:
            #Designate this shape as the longest
            longest = shape_id
            #And keep track of the number of points
            longest_pt_num = shapes[shapes['shape_id']
            == shape_id]['shape_pt_sequence'].count()
    #End loop through each shape in this route
    #Now that we have the longest shape for the route, create a shapely
    #LineString for this route ID
    multiline = sh.LineString(zip(shapes[shapes['shape_id']
        == longest]['shape_pt_lon'].tolist(),
        shapes[shapes['shape_id'] == longest]['shape_pt_lat'].tolist()))
    #Now let's add the parts of the other shapes that don't overlap with this
    #longest shape to create a MultiLineString collection
    #First create an area within which we'll reject additional points
    #(this buffer--0.0001 deg--is about 30m, or about the width of Mass Ave)
    area = multiline.buffer(0.0001)
    #Get the set of shapes (other than the longest one) to loop over
    shorter_shape_ids = shape_ids
    shorter_shape_ids.remove(longest)
    #Now to go through them, and add only the points from each shape that
    #aren't in the area.
    for shape_id in shorter_shape_ids:
        #Get the current shape as a shapely shape
        this_shape = sh.LineString(zip(shapes[shapes['shape_id']
            == shape_id]['shape_pt_lon'].tolist(),
            shapes[shapes['shape_id'] == shape_id]['shape_pt_lat'].tolist()))
        #Is this shape entirely within the existing area?
        if not this_shape.within(area):
            #If there are points outside the area, add to the MultiLineString
            new_part = this_shape.difference(area)
            #Now add this new bit to the MultiLineString
            multiline = multiline.union(new_part)
            #Now update the testing area to include this new line
            area = multiline.buffer(0.0001)
    #Now we have a shapely MultiLineString object with the lines making
    #up shape of this route. Next, simplify that object:
    tolerance = 0.00005
    simplified_multiline = multiline.simplify(tolerance, preserve_topology=False)
    #Turn the MultiLine into a geoJSON feature object, and add it to the list
    #of features that'll be written to file as a featurecollection at the end
    route_shape_list.append(gj.Feature(geometry=simplified_multiline,
        properties={"route_id": route_id}))
    #End of loop through all routes

#Finally, write our collection of Features (one for each route) to file in
#geoJSON format, as a FeatureCollection:
with open('route_shapes.geojson', 'w') as outfile:
    gj.dump(gj.FeatureCollection(route_shape_list), outfile)


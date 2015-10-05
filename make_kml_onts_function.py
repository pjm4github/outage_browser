__author__ = 'patman'

import os
import kml_components
import lat_lon_distance
import arrow

def make_kml_utility_assets(data_header, data_dict, unique_file_name,
                            kml_output_file_dir=None, restrict_area=None):
    #   Asset ID, #, Address, Latitude, Longitude, CE Map, ONTs
    # These will be decorated as transformers, poles and house icons.
    # [u'TR301740671_42', u'', u'', u'41.191647', u'-73.755844', u'42', ....
    # [u'PS301419555', u'', u'', u'41.206979', u'-73.757151', u'7', ...
    # [u'PP301419702', u'', u'', u'41.206575', u'-73.748062', u'19A', ...
    header = data_header  # .split(',') if the data header is a comma separated string

    new_header = ['Asset', 'Address', 'Muni', 'State', 'ZipCode', 'CEMap', 'Longitude', 'Latitude']
    # The second item is the tuple must correspond to the header name

    templates = [('<Placemark>\n<name>{}</name>\n _INSERT_STYLE_HERE_  <description>\n    <![CDATA[\n','Asset'),
                 ('<b>Loc:</b> {} ',                                                                   'Address'),
                 (' {}, <br>',                                                                         'Muni'),
                 (' {}',                                                                               'State'),
                 (' {}<br><b>Generated from:</b>_INSERT_FILE_NAME_<br>\n',                             'ZipCode'),
                 (' <b>CE Map ID:</b> <span class="cemapid">{}<br></span>\n',                          'CEMap'),
                 ('   ]]>\n   </description>\n \n<Point>\n     <coordinates>{},',                      'Longitude'),
                 ('{}</coordinates>\n   </Point>\n_INSERT_PLACE_MARK_COLOR_HERE_\n</Placemark>\n',     'Latitude')]

    # lookup function for field values. leading and trailing whitespace will be removed
    value = lambda field, array, new_header: array[new_header.index(field)].lstrip().rstrip()

    if not kml_output_file_dir:
        kml_output_file_dir = os.getcwd() + os.sep + 'kml_files'
        try:
            os.mkdir(kml_output_file_dir)
        except WindowsError:
            print "Output directory %s exists, skipping mkdir!" % kml_output_file_dir

    kml_output_file = kml_output_file_dir + os.sep + unique_file_name
    kml_file = open(kml_output_file, "w")
    # open and add the file to the set of files
    print "Creating file '%s' for %s" % (kml_output_file, unique_file_name)
    # start output
    kml_file.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                   '<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document>\n%s' % kml_components.hidden_label)

    number_skipped = 0
    number_included = 0
    for j, row in enumerate(data_dict):
        # Insert values into xml
        # Here is where the KML file is written to along with the colorization selection.
        marker_style_define=''
        marker_style=''
        # Insert values into xml
        # Here is where the KML file is written to along with the colorization selection.
        if restrict_area:
            this_lat1 = float(row[header.index('Latitude')])
            this_long1 = float(row[header.index('Longitude')])
            this_lat2 = restrict_area['latitude']
            this_long2= restrict_area['longitude']
            if lat_lon_distance.lat_lon_distance(this_lat1, this_long1, this_lat2, this_long2,  units='mi') > \
                    restrict_area['radius']:
                print "Skipping asset %s at %s because it is outside ROI!" % (row[header.index('Asset ID')], row[header.index('Address')])
                number_skipped += 1
                continue
        number_included += 1
        new_row = [''] * len(new_header)
        new_row[new_header.index('Latitude')] = row[header.index('Latitude')]
        new_row[new_header.index('Longitude')] = row[header.index('Longitude')]
        new_row[new_header.index('Asset')] = row[header.index('Asset ID')]
        if (row[header.index('#')] != '') and (row[header.index('Address')] != ''):
            these_parts = (row[header.index('#')] + " "+ row[header.index('Address')]).split(',')
            try:
                new_row[new_header.index('Address')] = these_parts[0]
                new_row[new_header.index('Muni')] = these_parts[1]
                new_row[new_header.index('State')] = these_parts[2]
                new_row[new_header.index('ZipCode')] = these_parts[3]
            except Exception as e:
                print "There was a problem with the address string on row %d of input record, %s" % (j, e)
        else:
            new_row[new_header.index('Address')] = ''
            new_row[new_header.index('Muni')] = ''
            new_row[new_header.index('State')] = ''
            new_row[new_header.index('ZipCode')] = ''
        new_row[new_header.index('CEMap')] = row[header.index('CE Map')]

        # Select the appropriate ICON here
        asset_name = row[header.index('Asset ID')]
        if asset_name[0:2] == 'HS':
            # HOUSE
            icon_style = kml_components.orange_house
            place_mark = kml_components.place_mark_orange_house
        # Or else if its a primary then look to see if it has a transformer.
        elif asset_name[0:2] == 'TR':
            # primary transformer
            icon_style = kml_components.blue_xfmr_style
            place_mark = kml_components.place_mark_blue_xfmr
        elif asset_name[0:2] == 'TS':
            # secondary transformer
            icon_style = kml_components.orange_xfmr_style
            place_mark = kml_components.place_mark_orange_xfmr
        elif asset_name[0:2] == 'PP':
            # primary pole
            icon_style = kml_components.blue_pole_style
            place_mark = kml_components.place_mark_blue_pole
        elif asset_name[0:2] == 'PS':
            # secondary pole
            icon_style = kml_components.orange_pole_style
            place_mark = kml_components.place_mark_orange_pole

        for t, f in templates:
            the_str = t.format(value(f, new_row, new_header))
            the_str = the_str.replace('_INSERT_STYLE_HERE_', icon_style)
            the_str = the_str.replace('_INSERT_PLACE_MARK_COLOR_HERE_', place_mark)
            the_str = the_str.replace('_INSERT_FILE_NAME_',"%s, row %d" % ('Groomer browser', j))
            kml_file.write(the_str)

    print "Done creating utility Asset KML file, closing files."
    kml_file.write(' </Document>\n</kml>\n')
    kml_file.close()
    print "Number of assets skipped = %d, number included = %d" % (number_skipped, number_included)
    return kml_output_file


def make_kml_ont_eligibilities(data_header, data_dict, unique_file_name,
                               kml_output_file_dir=None, restrict_area=None):
    header = data_header  # .split(',') if the data header is a comma separated string

    # ONT, #, Address, Latitude, Longitude, Distance
    # These will be decorated as red FIOS icons.

    # This is the same as the header in the table in the UI
    new_header = ['ONT', 'Address', 'Muni', 'State', 'ZipCode', 'Distance', 'Longitude', 'Latitude']
    # The second item is the tuple must correspond to the header name
    templates = [('  <Placemark>\n<name>{}</name>\n _INSERT_STYLE_HERE_ <description>\n<![CDATA[\n\n', 'ONT'),
             ('<b>Loc:</b> {} ',                                        'Address'),
             (' {}, <br>',                                              'Muni'),
             (' {}',                                                    'State'),
             (' {}<br><b>Generated from:</b>_INSERT_FILE_NAME_<br>\n',  'ZipCode'),
             (' <b>Distance:</b> <span class="distance">{}<br></span>\n','Distance'),
             (' ]]>\n</description>\n   <Point>\n    <coordinates>{},', 'Longitude'),
             ('{}</coordinates>\n   </Point>\n_INSERT_PLACE_MARK_COLOR_HERE_\n  </Placemark>\n',         'Latitude')]
    # lookup function for field values. leading and trailing whitespace will be removed
    value = lambda field, array, new_header: array[new_header.index(field)].lstrip().rstrip()

    if not kml_output_file_dir:
        kml_output_file_dir = os.getcwd() + os.sep + 'kml_files'
        try:
            os.mkdir(kml_output_file_dir)
        except WindowsError:
            print "filename exists"

    kml_output_file = kml_output_file_dir + os.sep + unique_file_name
    kml_file = open(kml_output_file, "w")
    # open and add the file to the set of files
    print "Creating file '%s' for %s" % (kml_output_file, unique_file_name)
    # start output
    kml_file.write('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document>\n')

    for j, row in enumerate(data_dict):
        # Insert values into xml
        # Here is where the KML file is written to along with the colorization selection.
        if restrict_area:
            this_lat1 = float(row[header.index('Latitude')])
            this_long1 = float(row[header.index('Longitude')])
            this_lat2 = restrict_area['latitude']
            this_long2= restrict_area['longitude']
            if lat_lon_distance.lat_lon_distance(this_lat1, this_long1, this_lat2, this_long2,  units='mi') > \
                    restrict_area['radius']:
                continue
        new_row = [''] * len(new_header)
        new_row[new_header.index('ONT')] = row[header.index('ONT')]
        these_parts = (row[header.index('#')] + " "+ row[header.index('Address')]).split(',')
        try:
            new_row[new_header.index('Address')] = these_parts[0]
            new_row[new_header.index('Muni')] = these_parts[1]
            new_row[new_header.index('State')] = these_parts[2]
            new_row[new_header.index('ZipCode')] = these_parts[3]
        except Exception as e:
            print "There was a problem with the address string on row %d of input record, %s" % (j, e)

        new_row[new_header.index('Distance')] = row[header.index('Distance')]
        new_row[new_header.index('Latitude')] = row[header.index('Latitude')]
        new_row[new_header.index('Longitude')] = row[header.index('Longitude')]

        for t, f in templates:
            the_str = t.format(value(f, new_row, new_header))
            the_str = the_str.replace('_INSERT_STYLE_HERE_', kml_components.fios_style)
            the_str = the_str.replace('_INSERT_PLACE_MARK_COLOR_HERE_', kml_components.place_mark_fios)
            the_str = the_str.replace('_INSERT_FILE_NAME_',"%s, row %d" % ('Groomer browser', j))
            kml_file.write(the_str)

    print "closing files"
    kml_file.write(' </Document>\n</kml>\n')
    kml_file.close()
    return kml_output_file


def make_kml_outage_marker(unique_file_name, lat_lon,
                           street_address='',
                           outage_start='',
                           outage_end='',
                           kml_output_file_dir=None):
    if not kml_output_file_dir:
        kml_output_file_dir = os.getcwd() + os.sep + 'kml_files'
        try:
            os.mkdir(kml_output_file_dir)
        except WindowsError:
            print "filename exists"

    kml_output_file = kml_output_file_dir + os.sep + unique_file_name
    kml_file = open(kml_output_file, "w")
    outage_mark_data = kml_components.outage_location
    outage_mark_data = outage_mark_data.replace('__OUTAGE_NAME__', 'Utility Outage Event')
    outage_mark_data = outage_mark_data.replace('__COORDINATE_LOCATION_LAT_LON__', lat_lon)
    outage_mark_data = outage_mark_data.replace('__STREET_ADDRESS__', street_address)
    outage_mark_data = outage_mark_data.replace('__OUTAGE_START__', outage_start)
    outage_mark_data = outage_mark_data.replace('__OUTAGE_END__', outage_end)
    lat_lon_parts = lat_lon.strip().split(',')
    lon_lat = "%s,%s" % (lat_lon_parts[1],lat_lon_parts[0])
    outage_mark_data = outage_mark_data.replace('__COORDINATE_LOCATION__', lon_lat)


    kml_file.write(outage_mark_data)
    kml_file.close()


def make_kml(data_header, data_dict, unique_file_name, groomer_cutoff_time=5.0,
             kml_output_file_dir=None, restrict_area=None, restrict_time=None):
    """
    :param data_header: dictionary table of header items to match to the new_header array below.
    The array is position dependent.
    header = ['ONT','Start','End','Duration','#','Address','Latitude', 'Longitude', 'Matched Asset', 'Lat', 'Lon']

    :param data_dict:
    :param unique_file_name:
    :return:
    """
    # The new_header matches the template file below. It acts as a mapping between the header contents and the
    # names used in the template. For example if the first item in the data_header is 'ONT_SERIAL_NUM' then this
    # will point to ONT in the template file below.
    new_header = ['ONT', 'Address', 'Muni', 'State', 'ZipCode',
                  'Start', 'End', 'Duration',
                  'Matched Asset', 'Asset Lat', 'Asset Lon', 'Longitude', 'Latitude']

    header = data_header  # .split(',') if the data header is a comma separated string

    # ont_serial_number|error_code|latitude|longitude|aid|ont_address_string
    # 48937918|0.89|41.298195|-73.765633|YRTWNYYTOL1*LET-3*7*1*16|20 Arden Dr,Amawalk,NY,10501
    # See the specification "PON_EON_Solution_082714.docx"

    # TID        * Shelf * Slot * Port * Ont
    # YRTWNYYTOL1* LET-3 * 7    * 1    * 16
    # Address will be split into
    # Address,     Muni,    State, ZipCode
    # 20 Arden Dr, Amawalk, NY,    10501

    # The second item is the tuple must correspond to the header name
    templates = [('  <Placemark>\n<name>{}</name>\n _INSERT_STYLE_HERE_ <description>\n<![CDATA[\n\n', 'ONT'),
             ('<b>Loc:</b> {} ',                                                                          'Address'),
             (' {}, <br>',                                                                                'Muni'),
             (' {}',                                                                                      'State'),
             (' {}<br><b>Generated from:</b>_INSERT_FILE_NAME_<br>\n',                                    'ZipCode'),
             (' <b>Start:</b> <span class="outage_start">{}<br></span>\n',                                'Start'),
             (' <b>End:</b> <span class="outage_end">{}<br></span>\n',                                    'End'),
             (' <b>Duration:</b> <span class="outage_duration">{}<br></span>\n',                          'Duration'),
             (' <b>Matched Asset:</b> <span class="matched_asset">{}<br></span>\n',                   'Matched Asset'),
             (' <b>   Asset Lat:</b> <span class="asset_lat">{}<br></span>\n',                        'Asset Lat'),
             (' <b>   Asset Lon:</b> <span class="asset_lon">{}<br></span>\n',                            'Asset Lon'),
             (' ]]>\n</description>\n   <Point>\n    <coordinates>{},',                                  'Longitude'),
             ('{}</coordinates>\n   </Point>\n_INSERT_PLACE_MARK_COLOR_HERE_\n  </Placemark>\n',         'Latitude')]
    # lookup function for field values. leading and trailing whitespace will be removed
    value = lambda field, array, new_header: array[new_header.index(field)].lstrip().rstrip()

    if not kml_output_file_dir:
        kml_output_file_dir = os.getcwd() + os.sep + 'kml_files'
        try:
            os.mkdir(kml_output_file_dir)
        except WindowsError:
            print "filename exists"

    kml_output_file = kml_output_file_dir + os.sep + unique_file_name
    kml_file = open(kml_output_file, "w")
    # open and add the file to the set of files
    print "Creating file '%s' for %s" % (kml_output_file, unique_file_name)
    # start output
    kml_file.write('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document>\n')

    for j, row in enumerate(data_dict):
        # Insert values into xml
        # Here is where the KML file is written to along with the colorization selection.
        if restrict_area:
            this_lat1 = float(row[header.index('Latitude')])
            this_long1 = float(row[header.index('Longitude')])
            this_lat2 = restrict_area['latitude']
            this_long2= restrict_area['longitude']
            if lat_lon_distance.lat_lon_distance(this_lat1, this_long1, this_lat2, this_long2,  units='mi') > \
                    restrict_area['radius']:
                continue

        if restrict_time:
            # The time will be strings in this form: " 08/07/2015 11:31"
            try:
                target_start = arrow.get(restrict_time['received'], 'MM/DD/YYYY HH:mm').timestamp
            except arrow.parser.ParserError:
                try:
                    target_start = arrow.get(restrict_time['received'], 'M/DD/YYYY HH:mm').timestamp
                except Exception as e:
                    print "problem parsing received time value %s, %s" % (restrict_time['received'], e)
                    continue
            try:
                target_end = arrow.get(restrict_time['completed'], 'MM/DD/YYYY HH:mm').timestamp
            except arrow.parser.ParserError:
                try:
                    target_end = arrow.get(restrict_time['completed'], 'M/DD/YYYY HH:mm').timestamp
                except Exception as e:
                    print "problem parsing completion time value %s, %s" % (restrict_time['completed'], e)
                    continue
            try:
                actual_start = arrow.get(row[header.index('Start')], 'YYYY-MM-DD HH:mm:ss').timestamp # '2015-07-20 12:27:42'
            except arrow.parser.ParserError as e:
                print "problem parsing actual start time %s,  %s" % (row[header.index('Start')], e)
                continue
            try:
                actual_end = arrow.get(row[header.index('End')], 'YYYY-MM-DD HH:mm:ss').timestamp  # '2015-07-20 17:53:10'
            except arrow.parser.ParserError as e:
                print "problem parsing actual end time %s, %s" % (row[header.index('Start')], e)
                continue
            # The value 3600*10 is the number of seconds in an hour * 10 hours. So the window is +/- 10 hours
            time_margin = restrict_time['time_window'] * 3600  # 3600*10
            if actual_start < target_start - time_margin:
                print "Alarm start was %s, relative to the target alarm start time, dropping." % \
                      str((arrow.get(actual_start)-arrow.get(target_start)))
                continue
            else:
                print "Alarm start (%s), target (%s) passes. Difference is %s." % (row[header.index('Start')],
                                                                restrict_time['received'],
                                                                str((arrow.get(actual_start)-arrow.get(target_start))))
            if actual_end > target_end + time_margin:
                print "Alarm end was %s, relative to the target alarm end time, dropping." % \
                      str((arrow.get(actual_end)-arrow.get(target_end)))
                continue
            else:
                print "Alarm end (%s), target (%s) passes. Difference is %s. " % (row[header.index('End')],
                                                              restrict_time['completed'],
                                                              str((arrow.get(actual_end)-arrow.get(target_end))))

        new_row = [''] * len(new_header)
        new_row[new_header.index('ONT')] = row[header.index('ONT')]
        these_parts = (row[header.index('#')] + " "+ row[header.index('Address')]).split(',')
        try:
            new_row[new_header.index('Address')] = these_parts[0]
            new_row[new_header.index('Muni')] = these_parts[1]
            new_row[new_header.index('State')] = these_parts[2]
            new_row[new_header.index('ZipCode')] = these_parts[3]
        except Exception as e:
            print "There was a problem with the address string on row %d of input record. Address will not be included" \
                  "ONT = %s, %s" % (j, row[header.index('ONT')], e)

        new_row[new_header.index('Start')] = row[header.index('Start')]
        new_row[new_header.index('End')] = row[header.index('End')]
        new_row[new_header.index('Duration')] = row[header.index('Duration')]
        try:
            new_row[new_header.index('Matched Asset')] = row[header.index('Matched Asset')]
        except Exception as e:
            new_row[new_header.index('Matched Asset')] = ''
            print "Error in make_kml assigning Matched Asset(1) %s" % e
        try:
            new_row[new_header.index('Asset Lat')] = row[header.index('Asset Lat')]
        except Exception as e:
            new_row[new_header.index('Asset Lat')] = ''
            print "Error in make_kml assigning Asset Lat(2) %s" % e
        try:
            new_row[new_header.index('Asset Lon')] = row[header.index('Asset Lon')]
        except Exception as e:
            new_row[new_header.index('Asset Lon')] = ''
            print "Error in make_kml assigning Asset Lon(3) %s" % e
        new_row[new_header.index('Latitude')] = row[header.index('Latitude')]
        new_row[new_header.index('Longitude')] = row[header.index('Longitude')]

        for t, f in templates:
            the_str = t.format(value(f, new_row, new_header))
            if float(new_row[new_header.index('Duration')]) < 0.0:
                the_str = the_str.replace('_INSERT_STYLE_HERE_', kml_components.fios_style)
                the_str = the_str.replace('_INSERT_PLACE_MARK_COLOR_HERE_', kml_components.place_mark_fios)
            elif float(new_row[new_header.index('Duration')]) < groomer_cutoff_time:  # in minutes
                the_str = the_str.replace('_INSERT_STYLE_HERE_', kml_components.fios_groomed_style)
                the_str = the_str.replace('_INSERT_PLACE_MARK_COLOR_HERE_', kml_components.place_mark_fios_groomed)
            else:
                the_str = the_str.replace('_INSERT_STYLE_HERE_', kml_components.green_style)
                the_str = the_str.replace('_INSERT_PLACE_MARK_COLOR_HERE_', kml_components.place_green_fios)
            the_str = the_str.replace('_INSERT_FILE_NAME_',"%s, row %d" % ('Groomer browser', j))
            kml_file.write(the_str)

    print "closing files"
    kml_file.write(' </Document>\n</kml>\n')
    kml_file.close()
    return kml_output_file

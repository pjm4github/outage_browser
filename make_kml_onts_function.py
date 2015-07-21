__author__ = 'patman'

import csv
import arrow
import os


def make_kml(data_header, data_dict, unique_file_name, groomer_cutoff_time=5.0):
    """
    :param data_header: dictionary table of header items to match to the new_header array below.
    The array is position dependent.
    header = ['ONT','Start','End','Duration','#','Address','Latitude', 'Longitude', 'Matched Asset', 'Lat', 'Lon']

    :param data_dict:
    :param unique_file_name:
    :return:
    """
    new_header = ['ONT', 'Address', 'Muni', 'State', 'ZipCode',
                  'Start', 'End', 'Duration',
                  'Matched Asset', 'Asset Lat', 'Asset Lon', 'Longitude', 'Latitude']

    header = data_header  # .split(',') if the data header is a comma separated string
    place_mark_fios = '''<styleUrl>#msn_fios_icon</styleUrl>'''
    place_green_fios = '''<styleUrl>#msn_green_icon</styleUrl>'''

    place_mark_fios_groomed = '''<styleUrl>#msn_groomed_icon</styleUrl>'''
    fios_groomed_style = '''<StyleMap id="msn_groomed_icon">
            <Pair>
                <key>normal</key>
                <styleUrl>#sn_groomed_icon</styleUrl>
            </Pair>
            <Pair>
                <key>highlight</key>
                <styleUrl>#sh_groomed_icon</styleUrl>
            </Pair>
        </StyleMap>
        <Style id="sn_groomed_icon">
            <IconStyle>
                <scale>1.1</scale>
                <Icon>
                    <href>./files/vz_green_small_groomed_b7aa.png</href>
                </Icon>
                <hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>
            </IconStyle>
            <ListStyle>
            </ListStyle>
        </Style>
        <Style id="sh_groomed_icon">
            <IconStyle>
                <scale>1.3</scale>
                <Icon>
                    <href>./files/vz_green_small_groomed_b7aa.png</href>
                </Icon>
                <hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>
            </IconStyle>
            <ListStyle>
            </ListStyle>
        </Style>'''


    fios_style='''<StyleMap id="msn_fios_icon">
            <Pair>
                <key>normal</key>
                <styleUrl>#sn_fios_icon</styleUrl>
            </Pair>
            <Pair>
                <key>highlight</key>
                <styleUrl>#sh_fios_icon</styleUrl>
            </Pair>
        </StyleMap>
        <Style id="sn_fios_icon">
            <IconStyle>
                <scale>1.1</scale>
                <Icon>
                    <href>./files/vz_fios_small_icon09_b7aa.png</href>
                </Icon>
                <hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>
            </IconStyle>
            <ListStyle>
            </ListStyle>
        </Style>
        <Style id="sh_fios_icon">
            <IconStyle>
                <scale>1.3</scale>
                <Icon>
                    <href>./files/vz_fios_small_icon09_b7aa.png</href>
                </Icon>
                <hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>
            </IconStyle>
            <ListStyle>
            </ListStyle>
        </Style>'''

    green_style='''<StyleMap id="msn_green_icon">
            <Pair>
                <key>normal</key>
                <styleUrl>#sn_green_icon</styleUrl>
            </Pair>
            <Pair>
                <key>highlight</key>
                <styleUrl>#sh_green_icon</styleUrl>
            </Pair>
        </StyleMap>
        <Style id="sn_green_icon">
            <IconStyle>
                <scale>1.1</scale>
                <Icon>
                    <href>./files/vz_green_small_icon09_b7aa.png</href>
                </Icon>
                <hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>
            </IconStyle>
            <ListStyle>
            </ListStyle>
        </Style>
        <Style id="sh_green_icon">
            <IconStyle>
                <scale>1.3</scale>
                <Icon>
                    <href>./files/vz_green_small_icon09_b7aa.png</href>
                </Icon>
                <hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>
            </IconStyle>
            <ListStyle>
            </ListStyle>
        </Style>'''

    # ont_serial_number|error_code|latitude|longitude|aid|ont_address_string
    # 48937918|0.89|41.298195|-73.765633|YRTWNYYTOL1*LET-3*7*1*16|20 Arden Dr,Amawalk,NY,10501
    # See the specification "PON_EON_Solution_082714.docx"

    # TID        * Shelf * Slot * Port * Ont
    # YRTWNYYTOL1* LET-3 * 7    * 1    * 16
    # Address will be split into
    # Address,     Muni,    State, ZipCode
    # 20 Arden Dr, Amawalk, NY,    10501

    # The second item is the tuple must correspond to the header name
    templates = [('  <Placemark>\n   <name>{}</name>\n _INSERT_STYLE_HERE_ <description>\n<![CDATA[\n\n', 'ONT'),
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
        new_row = [''] * len(new_header)
        new_row[new_header.index('ONT')] = row[header.index('ONT')]
        these_parts = (row[header.index('#')] + " "+ row[header.index('Address')]).split(',')
        try:
            new_row[new_header.index('Address')] = these_parts[0]
            new_row[new_header.index('Muni')] = these_parts[1]
            new_row[new_header.index('State')] = these_parts[2]
            new_row[new_header.index('ZipCode')] = these_parts[3]
        except:
            print "There was a problem with the address string on row %d of input record" % j

        new_row[new_header.index('Start')] = row[header.index('Start')]
        new_row[new_header.index('End')] = row[header.index('End')]
        new_row[new_header.index('Duration')] = row[header.index('Duration')]
        try:
            new_row[new_header.index('Matched Asset')] = row[header.index('Matched Asset')]
        except:
            pass
        try:
            new_row[new_header.index('Asset Lat')] = row[header.index('Lat')]
        except:
            pass
        try:
            new_row[new_header.index('Asset Lon')] = row[header.index('Lon')]
        except:
            pass
        new_row[new_header.index('Latitude')] = row[header.index('Latitude')]
        new_row[new_header.index('Longitude')] = row[header.index('Longitude')]

        for t, f in templates:
            the_str = t.format(value(f, new_row, new_header))
            if float(new_row[new_header.index('Duration')]) < 0.0:
                the_str = the_str.replace('_INSERT_STYLE_HERE_', fios_style)
                the_str = the_str.replace('_INSERT_PLACE_MARK_COLOR_HERE_', place_mark_fios)
            elif float(new_row[new_header.index('Duration')]) < groomer_cutoff_time:
                the_str = the_str.replace('_INSERT_STYLE_HERE_', fios_groomed_style)
                the_str = the_str.replace('_INSERT_PLACE_MARK_COLOR_HERE_', place_mark_fios_groomed)
            else:
                the_str = the_str.replace('_INSERT_STYLE_HERE_', green_style)
                the_str = the_str.replace('_INSERT_PLACE_MARK_COLOR_HERE_', place_green_fios)
            the_str = the_str.replace('_INSERT_FILE_NAME_',"%s, row %d" % ('Groomer browser', j))
            kml_file.write(the_str)

    print "closing files"
    kml_file.write(' </Document>\n</kml>\n')
    kml_file.close()
    return kml_output_file
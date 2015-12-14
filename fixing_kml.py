import re
import os

def convert(filename, output_file):
    with open(filename, 'rb') as this_file:
        new_file = open(output_file,'wb')
        all_lines = this_file.read()
        named_capture = re.compile(r"<key>normal</key>[\n\r\s]*<styleUrl>#(?P<my_style_pattern>[0-9a-zA-Z_]*)</styleUrl>")
        new_lines = named_capture.sub(r"<key>normal</key>\r\n                <styleUrl>#hideLabel</styleUrl>", all_lines)  #, re.M)
        named_capture = re.compile(r'<StyleMap id="hideLabel">[\n\r\s]*<name>')
        new_lines = named_capture.sub(r'\r\n      <name>', new_lines)  # , re.M)
        named_capture = re.compile(r'</name></StyleMap>')
        new_lines = named_capture.sub(r'</name>', new_lines)  #, re.M)


#                           r"<BLAH>",
#                           all_lines,
#                           re.M)
        new_file.writelines(new_lines)
        # for row in this_file:
        #     if row.find('<StyleMap id="hideLabel">') >= 0:
        #         print "row was: %s" % row
        #         row = row.replace('<StyleMap id="hideLabel">','')
        #         print "row is now: %s " % row
        #     if row.find('</name></StyleMap>') >= 0:
        #         print "row was: %s" % row
        #         row = row.replace('</name></StyleMap>','</name>')
        #         print "row is now: %s " % row
        #     new_file.write(row)
        new_file.close()

if __name__ == '__main__':
    filename_in  = 'test_change.kml'
    output_file_temp = 'temp.kml'
    convert(filename_in, output_file_temp)
    os.rename(output_file_temp, filename_in)


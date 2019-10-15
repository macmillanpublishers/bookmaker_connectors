import sys
import os

zipdir_path = sys.argv[1]
zipfile_name = sys.argv[2]
files_to_zip = sys.argv[3:]

# load modules from sectionstart scripts_dir
import imp
zipDOCXpath = os.path.join(sys.path[0],'..','sectionstart_converter','xml_docx_stylechecks','shared_utils','zipDOCX.py')
zipDOCX = imp.load_source('zipDOCX', zipDOCXpath)

try:
    zipDOCX.zipDOCX(zipdir_path, zipfile_name, files_to_zip)
    # on success pass confirmation back to parent script
    print 'zipped'
except Exception as e:
    # on error pass errstring back to parent script
    print e

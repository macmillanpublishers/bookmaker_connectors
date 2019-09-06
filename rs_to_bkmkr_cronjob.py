# please run pip install pytz as needed

import os
import sys
import logging
import imp
from datetime import datetime
import dateutil.parser
import pytz
import ctypes
import platform
import sys


#---------------------  LOCAL DECLARATIONS
warning_age = 120   # seconds. Time past date_created which we send an alert.
stale_dir_threshold_seconds = 600
download_warning_age = 120 # seconds. Time past which we warn that a download is taking too long.
# currenttime = datetime.datetime.utcnow()#.isoformat('T')
# previous_time = (currenttime - datetime.timedelta(seconds=interval_seconds)).isoformat('T')
rs_to_bkmkr_dir = 'rsuite_to_bookmaker'
markers = {
    'rs_ready': 'bookmakerMetadata.json',
    'bkmkr_processing': 'bkmkr_begun_processing_this_folder',
    'unprocessed': 'this_folder_has_been_here_too_long'
}
# mimetypes?

#---------------------  IMPORT other custom python utils for functions below
# shared_utils & decorators are relative imports in googledrive_api.py. to get it to resolve from this script importing it here too.
pythonutils_path = os.path.join(sys.path[0], '..', 'utilities', 'python_utils')
shared_utils = imp.load_source('shared_utils', os.path.join(pythonutils_path,'shared_utils.py'))
decorators = imp.load_source('decorators', os.path.join(pythonutils_path,'decorators.py'))
drive_api = imp.load_source('drive_api', os.path.join(pythonutils_path,'googledrive_api.py'))

#---------------------  FUNCTIONS
# are we scrapping interval and just using marker?
# do we check sizes? probably a good idea. against available space on destination.
# 1st funciton:
# get list of directories in keyfolder and their ages
# check list of files in each folder
# if a folder is ready, return folder id, (sub funciton)and write a marker file
# any way to check for lost / noni=finishing jobs? checj date-created and if
# 2nd: function
# for each folder that was returned, proceed with:
#     do we check sizes? probably a good idea. against available space on destination.
#
#     download whole thing? or move files to right folders?

def findDirByName(service, dirname, parentname):
    # if service is not None:
    # get id of root subfolder
    maindir_arr = drive_api.driveQuery(service,
                            '"{}" in parents'.format(parentname),
                            mimeType='application/vnd.google-apps.folder',
                            name='{}'.format(dirname),
                            trashed=False)
    if len(maindir_arr) == 1:
        maindir_id = maindir_arr[0]['id']
        return maindir_id
    else:
        print 'uhoh'
        return ''

def returnAllSubdirs(service, dir_id):
    dirs_array = drive_api.driveQuery(service,
                            '"{}" in parents'.format(dir_id),
                            mimeType='application/vnd.google-apps.folder',
                            trashed=False)
    return dirs_array

def evalSubdirs(service, dirs_array, stale_dir_threshold_seconds, markers):
    newdirs, too_old_dirs = [],[]
    try:
        # cycle through any project_dirs looking for ready-to-process ones, or too-old ones
        for dir in dirs_array:
            # get all files in this project_dir
            file_array = drive_api.listObjectsInFolder(service, dir['id'])
            # scan file array for rs_ready_marker with absence of other markers (indicates new project_dir)
            if any(file['name'] == markers['rs_ready'] for file in file_array) \
                and not any(file['name'] == markers['bkmkr_processing'] for file in file_array) \
                and not any(file['name'] == markers['unprocessed'] for file in file_array):
                    # write a marker file so we don't pick this up again
                    drive_api.writeFile(service, dir['id'], markers['bkmkr_processing'])
                    # capture total size of files and add to dir_dict
                    dir['dir_bytes'] = sum(int(file['size']) for file in file_array)
                    # register new project_dir for return
                    newdirs.append(dir)
            elif not any(file['name'] == markers['rs_ready'] for file in file_array) \
                and not any(file['name'] == markers['unprocessed'] for file in file_array):
                # check dir age versus too_old threshold
                dir_age = datetime.now(pytz.utc) - dateutil.parser.parse(dir['createdTime'])
                if dir_age.total_seconds() > stale_dir_threshold_seconds:
                    # write a marker file so we don't pick this up again
                    drive_api.writeFile(service, dir['id'], markers['unprocessed'])
                    # capture total size of files and add to dir_dict
                    dir['dir_bytes'] = sum(int(file['size']) for file in file_array)
                    # register too-old project_dir for return
                    too_old_dirs.append(dir)
        return newdirs, too_old_dirs
    except Exception:
        logging.error("err running with Eval:", exc_info=True)
        return [],[]

def get_free_space_mb(dirname):
    #"""Return folder/drive free space (in megabytes)."""
    if platform.system() == 'Windows':
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(dirname), None, None, ctypes.pointer(free_bytes))
        return free_bytes.value / 1024 / 1024
    else:
        st = os.statvfs(dirname)
        return st.f_bavail * st.f_frsize / 1024 / 1024

#---------------------  MAIN
service = drive_api.getDriveServiceOauth2()

if service is not None:
    maindir_id = findDirByName(service, rs_to_bkmkr_dir, 'root')
#
# if service is not None:
#     # get id of rsuite_to_bookmaker folder
#     maindir_arr = drive_api.driveQuery(service,
#                             '"root" in parents',
#                             mimeType='application/vnd.google-apps.folder',
#                             name='rsuite_to_bookmaker')
#     if len(maindir_arr) == 1:
#         maindir_id = maindir_arr[0]['id']
#         print maindir_arr

    dirs_array = returnAllSubdirs(service, maindir_id)
    # new_dirs_array = drive_api.driveQuery(service,
    #                         '"{}" in parents'.format(maindir_id),
    #                         ['createdTime','<=',"'{}'".format(previous_time)],
    #                         mimeType='application/vnd.google-apps.folder',
    #                         trashed=False)
    newdirs, too_old_dirs = evalSubdirs(service, dirs_array, stale_dir_threshold_seconds, markers)

    freespace = get_free_space_mb('/')
    print freespace
    # TEST ON WINDOWS. SET DIRS FOR CHECKING (globally available is fine)

    #
    # print len(new_dirs_array)
    # for new_dir in new_dirs_array:
    #     print new_dir['name']
    #     file_array = drive_api.listObjectsInFolder(service, new_dir['id'])
    #     if any(file['name'] == rs_ready_marker for file in file_array) \
    #         and not any(file['name'] == bkmkr_processing_marker for file in file_array):
    #         print "GOOOT ONE"
                # if not any(file['name'] == bkmkr_processing_marker for file in file_array):
                #     print "STIIILLL"
                # else:
                #     print 'NOOOOT oNE'
            # for file in file_array:
            #         # if rsuite_throw_marker == file['name']
            #     print file['name']


        # new_jsons_array = drive_api.driveQuery(service,
        #                         '"{}" in parents'.format(maindir_id),
        #                         ['createdTime','<=',"'{}'".format(previous_time)],
        #                         mimeType='application/json',
        #                         trashed=False)
        # print len(new_jsons_array)
        # for new_jsons in new_jsons_array:
        #     print new_jsons['name']

        # print currenttime, previous_time

        # # create project dir
        # projectdir_id = drive_api.createRemoteFolder(service, "test", parentID = mainfolder_id)
        # print projectdir_id
        #
        # # upload file
        # file_id = drive_api.uploadFile(service, projectdir_id, file)
        # print file_id
        # is mimetype necessary? Do I need to do anything different to scope it ?
else:
    print "ERRRORRR with drive API"

# PLAN FOR OUTAGE - preserve files (done already. Add retry decorator?)

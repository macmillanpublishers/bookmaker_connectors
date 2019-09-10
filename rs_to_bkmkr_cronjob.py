
import os
import sys
import logging
import imp
from datetime import datetime
import dateutil.parser
import pytz
import ctypes
import platform
from textwrap import dedent
from socket import gethostname
import re
import subprocess
from getpass import getuser
# from multiprocessing import Pool
# from multiprocessing.dummy import Pool as ThreadPool
# from functools import partial



# # ---------------------  NOTES
# # This script is intended to be run as a cronjob,
# #     to regularly check for new project folders passed from RSuite to bookmaker via GoogleDrive,
# #     & download them for processing
# # Basic outline:
# #     1) Checks for new folders that are ready (determined via presence of metadata.json),
# #     2) writes a 'marker' file in said folder so it is not re-processed
# #     3) verifies that space is available to download contents
# #     4) * WAS going to download here. But now, looking at downloading directly to tmp folder via speshul .bat
# #         pass directory id to tmparchive? No... maybe it makes most sense to handle it here? MF
# #         because drive api is in python.
# #         ok. Looking at doing tmpdir creation & downloads here, then pass off to .bat straightaway
# # Alerts sent for following mishaps:
# #     a) a project folder without metadata.json and past a certain age is detected
# #     b) a folder is ready, but is too large to be downloaded
# #     c) a folder is taking too long to download
# #     d) any other errors are encountered along the way

# NOTES for future development: ideally we would multithread but that involves --- welll, actually ideally we would multithread!
#  Let's try it!

#---------------------  LOCAL DECLARATIONS
stale_dir_maxtime_seconds = 600
download_maxtime_seconds = 300
perjob_maxsize_KB = 2000000
min_free_disk_KB = 2000000
alert_emails_to = 'workflows@macmillan.com'
api_xfer_dir = 'rsuite_to_bookmaker'
markers = {
    'rs_ready': 'bookmakerMetadata.json',
    'bkmkr_processing': 'bkmkr_begun_processing_this_folder',
    'unprocessed': 'this_folder_has_been_here_too_long'
}
server = gethostname()
currentuser = getuser()
staging_filename = 'starging.txt'    ### DEBUG: misspelling: no staging folder setup in Drive yet
staging_file = os.path.join("C:", os.sep, staging_filename)
rs_to_bkmkr_name = 'rs_to_bkmkr'
bkmkr_dir = os.path.join("C:", os.sep, "Users", "padwoadmin", "Dropbox (Macmillan Publishers)", rs_to_bkmkr_name)
bkmkr_tmp_dir = os.path.join("S:", os.sep, "bookmaker_tmp", rs_to_bkmkr_name)
bkmkr_cmd = os.path.join("S:", os.sep, "resources", "bookmaker_scripts", "bookmaker_deploy", "{}.bat".format(rs_to_bkmkr_name))
logdir = os.path.join("C:", os.sep, "Users", "padwoadmin", "Dropbox (Macmillan Publishers)", "bookmaker_logs", rs_to_bkmkr_name)
if os.path.exists(staging_file):
    api_xfer_dir = '{}_stg'.format(api_xfer_dir)
    bkmkr_dir = os.path.join("C:", os.sep, "Users", "padwoadmin", "Dropbox (Macmillan Publishers)", "{}_stg".format(rs_to_bkmkr_name))
    logdir = os.path.join("C:", os.sep, "Users", "padwoadmin", "Dropbox (Macmillan Publishers)", "bookmaker_logs", "{}_stg".format(rs_to_bkmkr_name))

# edits to above ^ for Mac OS / UNIX
if platform.system() != 'Windows':  # for testing:
    staging_file = os.path.join(os.sep,"Users", currentuser, staging_filename)
    bkmkr_dir = os.path.join(os.sep, "Users", currentuser, "Dropbox (Macmillan Publishers)")
    bkmkr_tmp_dir = os.path.join(os.sep, 'Users', currentuser, 'bookmaker-dev', 'bookmaker_tmp', rs_to_bkmkr_name)
    bkmkr_cmd = os.path.join(os.sep,'Users', currentuser, 'bookmaker-dev', 'bookmaker_deploy', "{}.sh".format(rs_to_bkmkr_name))
    logdir = os.path.join(os.sep, "Users", currentuser, "Dropbox (Macmillan Publishers)", "bookmaker_logs", rs_to_bkmkr_name)
    if os.path.exists(staging_file):
        api_xfer_dir = '{}_stg'.format(api_xfer_dir)
        bkmkr_dir = os.path.join(os.sep, "Users", currentuser, "Dropbox (Macmillan Publishers)", "{}_stg".format(rs_to_bkmkr_name))
        logdir = os.path.join(os.sep, "Users", currentuser, "Dropbox (Macmillan Publishers)", "bookmaker_logs", "{}_stg".format(rs_to_bkmkr_name))


#---------------------  IMPORT other custom python utils for functions below
# shared_utils & decorators are relative imports in googledrive_api.py. to get it to resolve from this script importing it here too.
pythonutils_path = os.path.join(sys.path[0], '..', 'utilities', 'python_utils')
shared_utils = imp.load_source('shared_utils', os.path.join(pythonutils_path,'shared_utils.py'))
decorators = imp.load_source('decorators', os.path.join(pythonutils_path,'decorators.py'))
drive_api = imp.load_source('drive_api', os.path.join(pythonutils_path,'googledrive_api.py'))
sendmail = imp.load_source('sendmail', os.path.join(pythonutils_path,'sendmail.py'))


#---------------------  LOGGING - set up log to file
logfile = os.path.join(logdir, "rs_to_bkmk_cron-%s.log" % datetime.now().strftime("%y-%m"))
# create log dir if it does not exist
if not os.path.exists(logdir):
    shared_utils.mkDir(logdir)
logging.basicConfig(filename=logfile, level=logging.INFO)
logging.info("* * * * * * running 'rs_to_bkmkr_cronjob.py':  %s" % datetime.now().strftime("%y-%m-%d_%H:%M:%S"))


#---------------------  EMAIL MESSAGES
msg_header=dedent("""\
    Hello honored workflows personnel,
    """)
msg_footer=dedent("""
    Folder name: '{name}'
    Located in folder: '{parent_folder}'
    Folder size (KB): '{size}'
    Folder created (UTC): '{created}'
    """)

stalejob_subject = "ALERT: rsuite > bookmaker job not processed ({})".format(server)
stalejob_txt = msg_header + dedent("""
    A bookmaker job is languishing in transit from Rsuite to Bookmaker via Google Drive.
    It has aged beyond threshold time of '{elapsed}' seconds.
    """) + msg_footer

toolarge_subject = "ALERT: rsuite > bookmaker job too large to download ({})".format(server)
toolarge_txt  = msg_header + dedent("""
    A bookmaker job in transit from Rsuite to Bookmaker via Google Drive is too large to be downloaded to the server.
    Server destination is '{server}', permitted project_folder size: '{quota}' (KB).
    """) + msg_footer


#---------------------  FUNCTIONS
def evalSubdirs(service, dirs_array, stale_dir_maxtime_seconds, markers):
    ready_dirs, too_old_dirs = [],[]
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
                    dir['dir_kb'] = sum(int(file['size']) for file in file_array) / 1024
                    dir['files'] = file_array
                    # register new project_dir for return
                    ready_dirs.append(dir)
            elif not any(file['name'] == markers['rs_ready'] for file in file_array) \
                and not any(file['name'] == markers['unprocessed'] for file in file_array):
                # check dir age versus too_old threshold
                dir_age = datetime.now(pytz.utc) - dateutil.parser.parse(dir['createdTime'])
                if dir_age.total_seconds() > stale_dir_maxtime_seconds:
                    # write a marker file so we don't pick this up again
                    drive_api.writeFile(service, dir['id'], markers['unprocessed'])
                    # capture total size of files and add to dir_dict
                    dir['dir_kb'] = sum(int(file['size']) for file in file_array) / 1024
                    # register too-old project_dir for return
                    too_old_dirs.append(dir)
        return ready_dirs, too_old_dirs
    except Exception:
        logging.error("err running with evalSubdirs:", exc_info=True)
        return [],[]

# from: https://stackoverflow.com/questions/51658/cross-platform-space-remaining-on-volume-using-python
def get_free_space_kb(win_dirname, nonwin_dirname):
    #"""Return folder/drive free space (in megabytes)."""
    if platform.system() == 'Windows':
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(win_dirname), None, None, ctypes.pointer(free_bytes))
        return free_bytes.value / 1024
    else:
        st = os.statvfs(nonwin_dirname)
        return st.f_bavail * st.f_frsize / 1024

def calc_init_quota(perjob_maxsize_KB, min_free_disk_KB):
    freespace = get_free_space_kb('S:', '/')
    # if there's less free space on disk than set minimum, we lower the quota
    if freespace < min_free_disk_KB / 1024:
        quota = freespace * .75
    else:
        quota = perjob_maxsize_KB
    return quota

# this is a mirror of this ruby function from bookmaker:
#   https://github.com/macmillanpublishers/bookmaker/blob/master/core/header.rb#L85-L104
def setTmpDirName(bkmkr_tmp_dir, docx_name):
    project_tmp_dir_base = os.path.join(bkmkr_tmp_dir, docx_name)
    tmp_suffix_re = re.compile(".*_\d+$")
    if tmp_suffix_re.match(project_tmp_dir_base):
        # adding a hyphen as pre-suffix to filenames that happen to end in our std naming: '_\d'
        projtmpdir_root = "{}-_".format(project_tmp_dir_base)
    else:
        projtmpdir_root = "{}_".format(project_tmp_dir_base)
    count = 1
    project_tmp_dir = "{}{}".format(project_tmp_dir_base,count)
    # increment until we find an unused path/dir
    while os.path.exists(project_tmp_dir):
        count +=1
        project_tmp_dir = "{}{}".format(project_tmp_dir_base,count)
    return project_tmp_dir

def setupDirs(bkmkr_tmp_dir, docx_name):
    try:
        # set tmpdir name, create tmpdir & subdir(s)
        #   not worried about normalizing docx name, these have been prescreened by rsuite
        docx_basename = os.path.splitext(docx_name)[0]
        project_tmpdir = setTmpDirName(bkmkr_tmp_dir, docx_basename)
        nondocx_tmpdir = os.path.join(project_tmpdir, "submitted_files")
        shared_utils.mkDir(bkmkr_tmp_dir)
        shared_utils.mkDir(project_tmpdir)
        shared_utils.mkDir(nondocx_tmpdir)
    except Exception:
        logging.error("err running with setupDirs:", exc_info=True)
        return '',''
    return project_tmpdir, nondocx_tmpdir

def downloadFiles(service, docx_object, project_tmpdir, nondocx_objects, nondocx_tmpdir):
    dl_success = False
    try:
        # download files!
        status = drive_api.downloadFile(service, docx_object['id'], os.path.join(project_tmpdir, docx_object['name']))
        for file in nondocx_objects:
            status = drive_api.downloadFile(service, file['id'], os.path.join(nondocx_tmpdir, file['name']))
        dl_success = True
        return dl_success
    except Exception:
        logging.error("err running with processReadyDir:", exc_info=True)
        return False

def processReadyDir(ready_dir): # other unlisted params, in scope: api_xfer_dir, service, bkmkr_tmp_dir, bkmkr_tmp_dir, bkmkr_cmd,
    # get the manuscript filename & id
    nondocx_objects = []
    for file in ready_dir['files']:
        if os.path.splitext(file['name'])[1] == '.docx':
            docx_object = file
        else:
            nondocx_objects.append(file)
    # set tmpdirs, download items
    if docx_object:
        project_tmpdir, nondocx_tmpdir = setupDirs(bkmkr_tmp_dir, docx_object['name'])
        dl_success = downloadFiles(service, docx_object, project_tmpdir, nondocx_objects, nondocx_tmpdir)
        if dl_success == True:
            # kick off bookmaker!
            # ** NOTE:
            #   we may need to change the working_dir in the header for this project. Can detect input_dir for project_name...
            #   orrrr pass 2 parameters .. one for convert-file & one with tmpdir name. Testing the latter
            docx_tmpdir_path = os.path.join(project_tmpdir)#, docx_object['name'])
            docx_convert_path = os.path.join(bkmkr_dir, "convert", docx_object['name'])
            popen_params = [r'{}'.format(os.path.join(bkmkr_cmd)), docx_convert_path, docx_tmpdir_path]
            p = subprocess.Popen(popen_params)
            print "PID %s" % p.pid



#---------------------  MAIN
service = drive_api.getDriveServiceOauth2()

if service is not None:
    # get rsuite_to_bookmaker dir id
    logging.info("getting maindir")
    maindir_id = drive_api.findDirByName(service, api_xfer_dir, 'root')
    archivedir_id = drive_api.findDirByName(service, '{}_sent'.format(api_xfer_dir), 'root')

    # get all dirs in rsuite_to_bookmaker
    logging.info("getting dirs_array")
    dirs_array = drive_api.returnAllSubdirs(service, maindir_id)

    # evaluate dirs, write markers & return any that are ready, or too old
    ready_dirs, too_old_dirs = evalSubdirs(service, dirs_array, stale_dir_maxtime_seconds, markers)
    logging.info("ready_dirs: %s" % len(ready_dirs))
    logging.info("too_old_dirs: %s" % len(too_old_dirs))

    # send alert for too_old_dirs
    for old_dir in too_old_dirs:
        stalejob_body = stalejob_txt.format(elapsed=stale_dir_maxtime_seconds, parent_folder=api_xfer_dir, \
        name=dir['name'], size=dir['dir_kb'], date=dir['createdTime'])
        sendmail.sendMail(alert_emails_to, stalejob_subject, stalejob_body)
        logging.info("sent mail for too old")

    # check sizes, divert to alert if too large
    if ready_dirs:
        size_quota = calc_init_quota(perjob_maxsize_KB, min_free_disk_KB)
        logging.info("init quota: %s" % size_quota)
        for ready_dir in ready_dirs:
            # send alert for any too_large_dir
            print ready_dir
            if ready_dir['dir_kb'] > size_quota:
                toolarge_body = stalejob_txt.format(server=server, quota=size_quota, \
                name=dir['name'], size=dir['dir_kb'], date=dir['createdTime'])
                sendmail.sendMail(alert_emails_to, toolarge_subject, toolarge_body)
                # remove this dir from the array
                ready_dirs.remove(ready_dir)
                logging.info("sending toolarge alert: \n%s" % toolarge_body)
                continue
            else:
                # resize the quota dir by dir in case it is a close thing
                size_quota -= ready_dir['dir_kb']
                logging.info("revized quota: %s" % size_quota)

    # process ready dirs
    # NOTE: I should be passing moe parameters maybe, based on scoping do not need to? Since this is a standalone right
    #   now and likelihood of re-use is moderate.
    if ready_dirs:
        for ready_dir in ready_dirs:
            logging.info("looks like we're downloading!")
            processReadyDir(ready_dir)
            # archive drive folder
            drive_api.moveObject(service, ready_dir['id'], maindir_id, archivedir_id)

else:
    print "ERRRORRR with drive API"

# PLAN FOR OUTAGE - preserve files (done already. Add retry decorator?)

# error fielding
# LOGGING
# tracking time on downloads?
# # download! multithtred! keep an eye on time
# pool = ThreadPool(4)
# results = pool.map(my_function, my_array
# def multiThreadDlReadyDirs(ready_dir):

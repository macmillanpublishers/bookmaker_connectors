
import os
import sys
import logging
import imp
from datetime import datetime
import time
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


# # ---------------------  NOTES
# # This script is intended to be run as a cronjob,
# #     to regularly check for new project folders passed from RSuite to bookmaker via GoogleDrive,
# #     & download them for processing.
# # A script parameter will be written to json indicating what drive folders we are checking and what server we should return
# #     bookmaker output to. it should read 'rs_dev', 'rs_stg' or 'rs_prod'
# # Basic outline:
# #     1) Checks for new folders that are ready (determined via presence of metadata.json),
# #     2) writes a 'marker' file in said folder so it is not re-processed
# #     3) verifies that space is available to download contents
# #     4) Download files to rsuite_bookmaker tmp_drive folder/subfolders (determine project_dirname, create folders as needed)
# #     5) upon successful download:
# #         a) initiate bookmaker via Popen > .bat script. Pass infile, server_param & tmpdir path as parameters
# #         b) move downloaded folder to '_sent' folder
# #
# # Alerts sent for following mishaps:
# #     a) a project folder without metadata.json and past a certain age is detected
# #     b) a folder is ready, but is too large to be downloaded
# #     c) a folder is taking too long to download
# #     d) any other errors are encountered along the way

# NOTES for future development:
#   - there is a potential failure wherein a download indefinitely hangs but does not fail for an extended period of time,
#       or is extremly slow. In Windows task scheduler we can set this task to die after an hour or something, and that should trigger email alert.
#       Alternately could spawn a process that checks this scripts' process' status after x time or something similar.
#   - ideally we would multithread/multiprocess but that involves --- welll, actually ideally we would multithread. Postponing, but created ticket
#   - optionally can send email alert to user that submission is received (can get submitter from metadata.json)
#       may skip or handle this in tmparchive_rsuite for now.

#---------------------  INPUT PARAMETERS
if len(sys.argv) > 1:
    servername_param = sys.argv[1]
else:
    servername_param = 'rs_dev'
server_shortname = servername_param.split('_')[1]

#---------------------  LOCAL DECLARATIONS
stale_dir_maxtime_seconds = 600
download_maxtime_seconds = 300
perjob_maxsize_KB = 2000000
min_free_disk_KB = 2000000
alert_emails_to = ['workflows@macmillan.com']
api_xfer_dir = 'rsuite_to_bookmaker_{}'.format(server_shortname)
markers = {
    'rs_ready': 'bookmakerMetadata.json',
    'bkmkr_processing': 'bkmkr_begun_processing_this_folder',
    'unprocessed': 'this_folder_has_been_here_too_long'
}
server = gethostname()
currentuser = getuser()
staging_filename = 'staging.txt'
staging_file = os.path.join("C:", os.sep, staging_filename)
rs_to_bkmkr_name = 'rs_to_bkmkr'
runtype = 'rsuite'
bkmkr_toolchain_name = 'bookmaker_galley'
dropfolder_maindir = os.path.join("G:", os.sep, "My Drive", "Workflow Tools")    #<< drive
bkmkr_scripts_dir = os.path.join("S:", os.sep, "resources", "bookmaker_scripts")
bkmkr_tmp_dir = os.path.join("S:", os.sep, "bookmaker_tmp", bkmkr_toolchain_name)
drive_api_key_json = os.path.join(bkmkr_scripts_dir, 'bookmaker_authkeys', 'drive-api_oauth2credentials_wfnotifications.json')

# edits to above ^ for Mac OS / UNIX
if platform.system() != 'Windows':  # for testing:
    staging_file = os.path.join(os.sep,"Users", currentuser, staging_filename)
    dropfolder_maindir = os.path.join(os.sep, "Volumes", "GoogleDrive", "My Drive", "Workflow Tools")     #<< drive
    bkmkr_scripts_dir = os.path.join(os.sep,'Users', currentuser, 'bookmaker-dev')
    bkmkr_tmp_dir = os.path.join(os.sep, 'Users', currentuser, 'bookmaker-dev', 'bookmaker_tmp', bkmkr_toolchain_name)

bkmkr_dir = os.path.join(dropfolder_maindir, rs_to_bkmkr_name)
bkmkr_cmd = os.path.join(bkmkr_scripts_dir, "bookmaker_deploy", "{}.bat".format(rs_to_bkmkr_name))
logdir = os.path.join(dropfolder_maindir, "bookmaker_logs", "bookmaker_connectors", rs_to_bkmkr_name)

if os.path.exists(staging_file):
    bkmkr_dir = '{}_stg'.format(bkmkr_dir)
    logdir = '{}_stg'.format(logdir)

bkmkr_toolchain_dir = os.path.join(bkmkr_dir, bkmkr_toolchain_name)

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

err_subject = "ALERT: rsuite > bookmaker: unexpected error ({})".format(server)
err_txt  = msg_header + dedent("""
    An unexpected error was encountered while running rs_to_bkmkr_cronjob.py.
    - server/host: {server}
    - logfile: {logfile}
    """)


#---------------------  FUNCTIONS
@decorators.debug_logging
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
    except Exception as e:
        logging.error("err running with evalSubdirs:", exc_info=True)
        raise Exception('reraise')   # re-raise to send email

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
@decorators.debug_logging
def setTmpDirName(bkmkr_tmp_dir, docx_name):
    project_tmp_dir_base = os.path.join(bkmkr_tmp_dir, docx_name.replace(' ',''))   # < remove whitespace from docxname
    project_tmp_dir = "{}_{}".format(project_tmp_dir_base, time.strftime("%y%m%d%H%M%S"))
    ## ^ new way
    ## we're now not trying to match tmpdirs, since we're removing the need for done-folders:
    ##   so we don't need auto-increment and can just timestamp for unique directories
    ## \/ old way
    # tmp_suffix_re = re.compile(".*_\d+$")
    # if tmp_suffix_re.match(project_tmp_dir_base):
    #     # adding a hyphen as pre-suffix to filenames that happen to end in our std naming: '_\d'
    #     projtmpdir_root = "{}-_".format(project_tmp_dir_base)
    # else:
    #     projtmpdir_root = "{}_".format(project_tmp_dir_base)
    # count = 1
    # project_tmp_dir = "{}{}".format(projtmpdir_root,count)
    # # increment until we find an unused path/dir
    # while os.path.exists(project_tmp_dir):
    #     count +=1
    #     project_tmp_dir = "{}{}".format(projtmpdir_root,count)
    return project_tmp_dir

@decorators.debug_logging
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
        return project_tmpdir, nondocx_tmpdir
    except Exception:
        logging.error("err running with setupDirs:", exc_info=True)
        raise Exception('reraise')   # re-raise to send email

@decorators.debug_logging
def downloadFiles(service, docx_object, project_tmpdir, nondocx_objects, nondocx_tmpdir):
    dl_errors = []
    # download files!   # the details should be logged through debug.log decorator in referenced api functions.
    status = drive_api.downloadFile(service, docx_object['id'], os.path.join(project_tmpdir, docx_object['name'].replace(' ','')))
    if status != "Download 100%":
        dl_errors.append(docx_object['name'])
    for file in nondocx_objects:
        status = drive_api.downloadFile(service, file['id'], os.path.join(nondocx_tmpdir, file['name']))
        if status != "Download 100%":
            dl_errors.append(file['name'])
    return dl_errors

@decorators.debug_logging
def processReadyDir(ready_dir): # other unlisted params, in scope: api_xfer_dir, service, bkmkr_tmp_dir, bkmkr_tmp_dir, bkmkr_cmd..
    logging.info("processing ready_dir: %s" % ready_dir['name'])
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
        dl_errors = downloadFiles(service, docx_object, project_tmpdir, nondocx_objects, nondocx_tmpdir)
        if not dl_errors:
            # set bkmkr parameters, kick off bookmaker!
            docx_tmpdir_path = os.path.join(project_tmpdir)#, docx_object['name'])
            docx_convert_path = os.path.join(bkmkr_toolchain_dir, "convert", docx_object['name'])
            try:
                popen_params = [r'{}'.format(os.path.join(bkmkr_cmd)), docx_convert_path, runtype, 'placeholder_param', servername_param]
                logging.debug("popen params to launch bkmkr: \n'%s'" % popen_params)
                p = subprocess.Popen(popen_params)
                logging.info("bookmaker initiated for file '%s', pid %s" % (docx_object['name'], p.pid))
            except Exception:
                logging.error("error invoking bkmkr_cmd: '%s'" % bkmkr_cmd, exc_info=True)
                raise Exception('reraise')   # re-raise to send email
        else:
            errmsg = 'download(s) unsuccessful for files in "%s": "%s"' % (ready_dir['name'], dl_errors)
            raise Exception(errmsg)
    else:
        errmsg = '.docx not found in readydir! : "%s"' % ready_dir['name']
        raise Exception(errmsg)



#---------------------  MAIN
try:
    service = drive_api.getDriveServiceOauth2(drive_api_key_json)

    # get rsuite_to_bookmaker dir id
    maindir_id = drive_api.findDirByName(service, api_xfer_dir, 'root')
    archivedir_id = drive_api.findDirByName(service, '{}_sent'.format(api_xfer_dir), 'root')

    # get all dirs in rsuite_to_bookmaker
    dirs_array = drive_api.returnAllSubdirs(service, maindir_id)

    # evaluate dirs, write markers & return any that are ready, or too old
    ready_dirs, too_old_dirs = evalSubdirs(service, dirs_array, stale_dir_maxtime_seconds, markers)

    # send alert for too_old_dirs
    for old_dir in too_old_dirs:
        logging.info("sending alert mail for too_old_dir: %s" % old_dir['name'])
        stalejob_body = stalejob_txt.format(elapsed=stale_dir_maxtime_seconds, parent_folder=api_xfer_dir, \
        name=old_dir['name'], size=old_dir['dir_kb'], created=old_dir['createdTime'])
        sendmail.sendMail(alert_emails_to, stalejob_subject, stalejob_body)


    # check sizes, divert to alert if too large
    if ready_dirs:
        size_quota = calc_init_quota(perjob_maxsize_KB, min_free_disk_KB)
        logging.info("init quota: %s" % size_quota)
        for ready_dir in ready_dirs:
            # send alert for any too_large_dir
            if ready_dir['dir_kb'] > size_quota:
                logging.info("sending alert mail for toolarge_dir: %s" % ready_dir['name'])
                toolarge_body = toolarge_txt.format(server=server, quota=size_quota, parent_folder=api_xfer_dir,\
                name=ready_dir['name'], size=ready_dir['dir_kb'], created=ready_dir['createdTime'])
                sendmail.sendMail(alert_emails_to, toolarge_subject, toolarge_body)
                # remove this dir from the array
                ready_dirs.remove(ready_dir)
                continue
            else:
                # resize the quota dir by dir in case it is a close thing
                size_quota -= ready_dir['dir_kb']
                logging.info("revised quota: %s" % size_quota)

    # process ready dirs
    # NOTE: Maybe should be passing mote parameters, based on scoping in script, and since this is a standalone right now, and ..
    #   .. likelihood of one-off function re-use is low. Also just having 1 param lends itself to simple map funciton later, for multithread, eg:
    #      'results = pool.map(my_function, my_array)' '
    if ready_dirs:
        for ready_dir in ready_dirs:
            processReadyDir(ready_dir)
            # archive drive folder
            drive_api.moveObject(service, ready_dir['id'], maindir_id, archivedir_id)

except Exception as e:
    if e[0] == 'reraise':
        logging.warning("sending alert_mail for trapped/re-raised err")
    else:
        logging.error("sending alert_mail for untrapped top-level err", exc_info=True)
    err_body = err_txt.format(server=server, logfile=logfile)
    sendmail.sendMail(alert_emails_to, err_subject, err_body)

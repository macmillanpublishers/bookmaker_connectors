import os
import time
import sys
import shutil
import logging
import platform

#---------------------  IMPORT other custom python utils for functions below
if __name__ == '__main__':
    import imp
    # to go up a level to read shared files/resources:
    # sharedutils_path = os.path.join(sys.path[0], '..', 'python_utils', 'shared_utils.py')
    sendmail_path = os.path.join(sys.path[0], '..', 'utilities', 'python_utils', 'sendmail.py')
    # sharedutils = imp.load_source('sharedutils', sharedutils_path)
    sendmail = imp.load_source('sendmail', sendmail_path)

#---------------------  LOCAL DECLARATIONS
script_name = os.path.basename(sys.argv[0]).replace(".py","_py")
inputfolder = sys.argv[1]
from_rsuite_dirname = os.path.basename(os.path.dirname(inputfolder))

# platform dependent paths
if platform.system() == 'Windows':
    # presuming Google File Stream has been mounted to drive letter 'G'
    filestream_mydrive_location = os.path.join('G:',os.sep,'My Drive')
    from_rsuite_tmp_dir_base = os.path.join(filestream_mydrive_location,'rsuite_to_bookmaker-tmp')
    from_rsuite_archive_dir_base = os.path.join('S:',os.sep,'resources','file_cleanup','archived','rsuite_to_bookmaker-archive')
####### for testing
else:
    import getpass
    currentuser = getpass.getuser()
    filestream_mydrive_location = os.path.join(os.sep,'Volumes','GoogleDrive','My Drive')
    from_rsuite_tmp_dir_base = os.path.join(os.sep,'Users',currentuser,'testing','rsuite_to_bookmaker-tmp')
    from_rsuite_archive_dir_base = os.path.join(os.sep,'Users',currentuser,'testing','resources','file_cleanup','archived','rsuite_to_bookmaker-archive')

# basepaths & prod specific paths
bookmaker_rsuite_dir = os.path.join(filestream_mydrive_location,'bookmaker_bot_RS')
from_rsuite_tmp_dir = os.path.join(from_rsuite_tmp_dir_base, 'prod')
from_rsuite_archive_dir = os.path.join(from_rsuite_archive_dir_base, 'prod')

# logging
logdir = os.path.join(filestream_mydrive_location,'logs','bookmaker_connectors')
logfile_basepath = os.path.join(logdir,'{}-{}'.format(script_name,time.strftime("%Y-%m")))
logfile = '{}.txt'.format(logfile_basepath)

# staging specific paths
if from_rsuite_dirname.rpartition('_')[2] == 'stg':
    from_rsuite_archive_dir = os.path.join(from_rsuite_archive_dir_base, 'stg')
    from_rsuite_tmp_dir = os.path.join(from_rsuite_tmp_dir_base, 'stg')
    bookmaker_rsuite_dir = '{}_stg'.format(bookmaker_rsuite_dir)
    logfile = '{}_stg.txt'.format(logfile_basepath)
# staging dependent paths
convert_dir = os.path.join(bookmaker_rsuite_dir, 'convert')
submitted_images_dir = os.path.join(bookmaker_rsuite_dir, 'submitted_images')

# general items
interval_time = 1
max_intervals = 15
err_alert_toaddr = ['workflows@macmillan.com']

#---------------------  LOGGING - set up log to file
# create log dir if it does not exist
if not os.path.exists(logdir):
    os.makedirs(logdir)
logging.basicConfig(filename=logfile, format='%(asctime)s %(message)s', level=logging.INFO)
logging.debug("* * * * * * running '%s':  %s" %(time.strftime("%y-%m-%d_%H:%M:%S"), script_name))


#---------------------  FUNCTIONS

def mkDir(dir):
    logging.debug(" - running 'mkDir'")
    if not os.path.isdir(dir):
        try:
            os.makedirs(dir)
        except Exception, e:
            logging.error('Failed to mk new dir "%s" exiting' % dir, exc_info=True)
            sys.exit(1)

def copyFiletoFile(pathtofile, dest_file):
    logging.debug(" - running 'copyFiletoFile'")
    # if not os.path.isdir(os.path.dirname(dest_file)):
    #     os.makedirs(os.path.dirname(dest_file))
    try:
        shutil.copyfile(pathtofile, dest_file)
    except Exception, e:
        logging.error('Failed copyfile, exiting', exc_info=True)
        sys.exit(1)

def testEmptyDirs(convert_dir, submitted_images_dir, interval_time, max_intervals):
    logging.debug(" - running 'testEmptyDirs'")
    empty_bool = False
    errstring = ''
    n = 0
    # wait up to interval_time * max_intervals for these dirs to empty before giving up
    while (os.listdir(convert_dir) or os.listdir(submitted_images_dir)) and n < max_intervals:
        n+=1
        time.sleep(interval_time)
    # check results
    if not os.listdir(convert_dir) and not os.listdir(submitted_images_dir):
        empty_bool = True
    else:
        errstring = "Waited {} * {} seconds, submitted_images/convert_dir for bookmaker_bot-rsuite are still not clear.".format(n,interval_time)
        logging.error("files hanging around in bookmaker_rsuite-bot: 'images': %s, 'convert': %s" % (os.listdir(submitted_images_dir), os.listdir(convert_dir)))

    return empty_bool, errstring

def mvRenameInputDir(input_dir, dest_parentdir):
    logging.debug(" - running 'mvRenameInputDir'")
    inputdir_basename = os.path.basename(input_dir)
    dest_dir = os.path.join(dest_parentdir, '{}_{}'.format(inputdir_basename, time.strftime("%y%m%d-%H%M%S")))
    # create dest_parentdir as needed
    mkDir(dest_parentdir)
    try:
        shutil.move(input_dir, dest_dir)
    except Exception, e:
        logging.error('Failed to move inputdir "{}", exiting'.format(input_dir), exc_info=True)
        sys.exit(1)
    finally:
        return dest_dir

# we have controls on the inputs auto-sent from rsuite, so I am not trying to anticipate errors here,
#   just gather and copy the files expected from rsuite.
def submitFilesFromRSuite(input_tmpdir, convert_dir, submitted_images_dir):
    logging.debug(" - running 'submitFilesFromRSuite'")
    # copy non-.docx files to submitted_images dir
    for filename in os.listdir(input_tmpdir):
        if os.path.splitext(filename)[1] != '.docx':
            current_filepath = os.path.join(input_tmpdir, filename)
            dest_filepath = os.path.join(submitted_images_dir, filename)
            logging.debug("moving %s to %s" % (current_filepath, dest_filepath))
            copyFiletoFile(current_filepath, dest_filepath)

    time.sleep(1) # give prev. copies a second to wrap up
    # copy the .docx
    for filename in os.listdir(input_tmpdir):
        if os.path.splitext(filename)[1] == '.docx':
            current_filepath = os.path.join(input_tmpdir, filename)
            dest_filepath = os.path.join(convert_dir, filename)
            logging.debug("moving %s to %s" % (current_filepath, dest_filepath))
            copyFiletoFile(current_filepath, dest_filepath)

def archiveTmpDir(input_tmpdir, dest_parentdir):
    logging.debug(" - running 'archiveTmpDir'")
    input_tmpdir_basename = os.path.basename(input_tmpdir)
    dest_dir = os.path.join(dest_parentdir, input_tmpdir_basename)
    # create dest_parentdir as needed
    mkDir(dest_parentdir)
    try:
        shutil.move(input_tmpdir, dest_dir)
    except Exception, e:
        logging.error('Failed to move inputdir "{}", exiting'.format(input_dir), exc_info=True)
        sys.exit(1)
    finally:
        return dest_dir

#---------------------  MAIN

#-------- IMPORT other custom python utils
if __name__ == '__main__':
    import imp
    # go up a level to read shared files/resources:
    sharedutils_path = os.path.join(sys.path[0], '..', 'utilities', 'python_utils', 'shared_utils.py')
    shared_utils = imp.load_source('sendmail', sharedutils_path)

    try:
        logging.info("detected new folder: %s" % inputfolder)
        # move new dir from rsuite to tmp, giving unique name as we move
        input_tmpdir = mvRenameInputDir(inputfolder, from_rsuite_tmp_dir)

        # test bookmaker_dirs, wait till empty
        empty_bool, errstring = testEmptyDirs(convert_dir, submitted_images_dir, interval_time, max_intervals)

        # copy files from tmpdir to bookmaker_rsuite dirs
        if empty_bool == True:
            submitFilesFromRSuite(input_tmpdir, convert_dir, submitted_images_dir)
            # move dir from tmp to archive
            archivedir = archiveTmpDir(input_tmpdir, from_rsuite_archive_dir)
            logging.info("submitted files from rsuite to bookmaker, archived dir from rsuite: %s" % archivedir)
        else:
            errstring = errstring + "\n Leaving input_dir in tmpdir for manual reconciliation: {}".format(input_tmpdir)
            shared_utils.sendEmailAlert(err_alert_toaddr, script_name, errstring, logfile)
            logging.warn(errstring)
    except Exception, e:
        errstring = 'General error during rsuite-to-bookmaker_connector for {}, sending alert'.format(inputfolder)
        logging.error(errstring, exc_info=True)
        shared_utils.sendEmailAlert(err_alert_toaddr, script_name, errstring, logfile)

# this file accepts arguments from flask api and invokes rsvalidate process

import sys
import os
import imp
import platform
import zipfile
from datetime import datetime
import logging
import subprocess
from textwrap import dedent
from socket import gethostname
from getpass import getuser


# Define harcoded relative import paths from other repos
utils_repo = os.path.join(sys.path[0], '..', '..', 'utilities')
exec_args = imp.load_source('exec_params', os.path.join(utils_repo, 'portable_flask-api', 'flaskr', 'exec_params.py'))
sendmail = imp.load_source('sendmail', os.path.join(utils_repo, 'python_utils','sendmail.py'))

# # # Define key vars and params from input
inputfile = sys.argv[1]
# the relative order of these passed params is determined in flaskr/exec_params.py
user_email = sys.argv[exec_args.execArgs().index('emailAddress') + 2]
user_name = sys.argv[exec_args.execArgs().index('displayname') + 2]
parentdir = os.path.dirname(inputfile)
jobId = os.path.basename(parentdir)
file_ext = os.path.splitext(inputfile)[1]

# Other key definitions
pypath = 'python'
this_script = os.path.basename(sys.argv[0])
runtype_string = 'direct'
server = gethostname()
currentuser = getuser()
alert_emails_to = ['workflows@macmillan.com']
staging_filename = 'staging.txt'
staging_file = os.path.join("C:", os.sep, staging_filename)
dropfolder_maindir = os.path.join("G:", os.sep, "My Drive", "Workflow Tools")    #<< drive
bkmkr_scripts_dir = os.path.join("S:", os.sep, 'resources', 'bookmaker_scripts')
# edits to above ^ for Mac OS / UNIX
if platform.system() != 'Windows':  # for testing:
    pypath = os.path.join(os.sep, 'usr', 'bin', 'python') # <- python 2.7 (system)
    staging_file = os.path.join(os.sep,"Users", currentuser, staging_filename)
    dropfolder_maindir = os.path.join(os.sep, "Volumes", "GoogleDrive", "My Drive", "Workflow Tools")     #<< drive
    bkmkr_scripts_dir = os.path.join(os.sep,'Users', currentuser, 'bookmaker-dev')
# conditional dependent paths
logdir = os.path.join(dropfolder_maindir, "bookmaker_logs", "bookmaker_connectors", "api_execs")
rsvalidate_cmd = os.path.join(bkmkr_scripts_dir, "sectionstart_converter", "xml_docx_stylechecks", "rsuitevalidate_main.py")
# \/ probably don't need to implement process_watch.py for this app; since it already sends alerts on error
#process_watch_py = os.path.join(bkmkr_scripts_dir, "sectionstart_converter", "xml_docx_stylechecks", "shared_utils", "process_watch.py")
if os.path.exists(staging_file):
    # bkmkr_dir = '{}_stg'.format(bkmkr_dir)
    logdir = '{}_stg'.format(logdir)
logfile = os.path.join(logdir, "{}-{}.log".format(this_script, datetime.now().strftime("%y-%m")))


# # # ERROR ALERTS info:
err_subject = "ALERT: {}: unexpected error ({})".format(this_script, server)
err_txt  = dedent("""
    Hello honored workflows personnel,

    An unexpected error was encountered while running {this_script}.
    - server/host: {server}
    - logfile: {logfile}
    - errstring: {errstring}
    """)
err_dict = {
    "err_subject": err_subject,
    "err_txt": err_txt,
    "alert_emails_to": alert_emails_to,
    "server": server,
    "logile": logfile,
    "this_script": this_script
}


# # # FUNCTIONS
def sendExceptionAlert(errstring, err_dict):
    try:
        logging.info("err occurred, attempting send ")
        err_body = err_txt.format(server=err_dict['server'], logfile=err_dict['logfile'], \
            this_script=err_dict['this_script'], errstring=errstring)
        sendmail.sendMail(err_dict['alert_emails_to'], err_dict['err_subject'], err_dict['err_body'])
    except Exception as e:
        logging.error('Error sending Exception alert-mail', exc_info=True)

def try_create_dir(newpath, err_dict):
    try:
        if not os.path.exists(newpath):
            os.makedirs(newpath)
    except Exception as e:
        logging.error('Destination dir "{}" could not be created'.format(newpath), exc_info=True)
        sendExceptionAlert(e, err_dict)

# handle unzipping as needed
def unzipZips(inputfile, err_dict):
    if os.path.splitext(inputfile)[1] == '.zip':
        logging.debug("zip file, unzipping")
        parentdir = os.path.dirname(inputfile)
        try:
            zf = zipfile.ZipFile(inputfile, 'a')
            zf.extractall(parentdir)
            zf.close()
        except Exception as e:
            logging.error('Error unzipping "{}"'.format(inputfile), exc_info=True)
            sendExceptionAlert(e, err_dict)

# kickoff process via subprocess.popen
def invokeRSvalidate(pypath, cmd, file, runtype_string, user_email, user_name, err_dict):
    p = ''
    try:
        popen_params = [pypath, r'{}'.format(os.path.join(cmd)), file, runtype_string, user_email, user_name]
        logging.debug("popen params for 'invokeRSvalidate': \n{}".format(popen_params))
        p = subprocess.Popen(popen_params)
        logging.info("rsvalidate initiated for file '%s', pid %s" % (os.path.basename(file), p.pid))
        # logging.debug("popen output: {}".format(p)) < I don' think this works, b/c we are not piping stdout or anything
    except Exception as e:
        logging.error("error invoking bkmkr_cmd: '%s'" % cmd, exc_info=True)
        if p:
            logging.info("(popen output: {})".format(p))
        sendExceptionAlert(e, err_dict)


# # # setup logging
# create log dir if it does not exist
try_create_dir(logdir, err_dict)
logging.basicConfig(filename=logfile, level=logging.DEBUG)#INFO)
logging.info("* * * * * * running '{}':  {}".format(this_script, datetime.now().strftime("%y-%m-%d_%H:%M:%S")))


# # # RUN
if __name__ == '__main__':
    try:
        # unzip file if it was a zip, into the parentdir
        unzipZips(inputfile, err_dict)
        # we're only looking for docx that were zipped solo here; so just checking for docx in
        #   parentdir (where zips where extracted to) should be fine (no need to recurse)
        for fname in os.listdir(parentdir):
            if os.path.splitext(fname)[1] == '.docx':
                file = os.path.join(parentdir, fname)
                logging.debug('found docx: {}'.format(file))
                output = invokeRSvalidate(pypath, rsvalidate_cmd, file, runtype_string, user_email, user_name, err_dict)

    except Exception as e:
        logging.error("untrapped top-level exception occurred", exc_info=True)
        sendExceptionAlert(e, err_dict)

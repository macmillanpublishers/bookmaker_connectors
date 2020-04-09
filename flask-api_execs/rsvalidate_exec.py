import sys
import os
import imp
import zipfile
import subprocess
from socket import gethostname
from getpass import getuser

# # # Define key paths dependencies

# import arg definitions for extransoue params from flask, so we can pick them up by index
exec_args_dirpath = os.path.join(sys.path[0], '..', '..', 'utilities', 'portable_flask-api', 'flaskr')
exec_args = imp.load_source('exec_params', os.path.join(exec_args_dirpath,'exec_params.py'))

# # # Define key vars and params from input
inputfile = sys.argv[1]
user_email = sys.argv[exec_args.execArgs().index('emailAddress') + 2]
user_name = sys.argv[exec_args.execArgs().index('displayname') + 2]
parentdir = os.path.dirname(inputfile)
jobId = os.path.basename(parentdir)
file_ext = os.path.splitext(inputfile)[1]

server = gethostname()
currentuser = getuser()
staging_filename = 'staging.txt'
staging_file = os.path.join("C:", os.sep, staging_filename)
bkmkr_scripts_dir = os.path.join("S:", os.sep, "resources", "bookmaker_scripts")
# edits to above ^ for Mac OS / UNIX
if platform.system() != 'Windows':  # for testing:
    staging_file = os.path.join(os.sep,"Users", currentuser, staging_filename)
    bkmkr_scripts_dir = os.path.join(os.sep,'Users', currentuser, 'bookmaker-dev')
rsvalidate_cmd = os.path.join(bkmkr_scripts_dir, "sectionstart_converter", "xml_docx_stylechecks", "rsuitevalidate_main.py")


print ("inputfile: {}".format(inputfile))
print ("jobId: {}".format(jobId))
print ("user_email: {}".format(user_email))
print ("user_name: {}".format(user_name))

# # # setup logging


# # # FUNCTIONS
# handle unzipping as needed
def unzipZips(inputfile):
    if os.path.splitext(inputfile)[1] == '.zip':
        logging.debug("zip file, unzipping")
        parentdir = os.path.dirname(inputfile)
        try:
            zf = zipfile.ZipFile(inputfile, 'a')
            zf.extractall(parentdir)
            zf.close()
        except Exception as e:
            # on error pass errstring back to parent script
            print (e)
            # return ''

def invokeRSvalidate(rsvalidate_cmd, file, user_email, user_name):
    print ("invoking for : {}, {}, {}".format(file, user_email, user_name))
    try:
        popen_params = ['python', r'{}'.format(os.path.join(rsvalidate_cmd)), file, user_email, user_name]
        # logging.debug("popen params to launch bkmkr: \n'%s'" % popen_params)
        p = subprocess.Popen(popen_params)
        print p
        # logging.info("bookmaker initiated for file '%s', pid %s" % (docx_object['name'], p.pid))
    except Exception:
        logging.error("error invoking bkmkr_cmd: '%s'" % bkmkr_cmd, exc_info=True)
        # raise Exception('reraise')   # re-raise to send email

# # # RUN
if __name__ == '__main__':
    # unzip file if it was a zip, into the parentdir
    unzipZips(inputfile)

    # we're only looking for docx that were zipped solo here; so just checking for docx in
    #   parentdir (where zips where extracted to) should be fine (no need to recurse)
    for fname in os.listdir(parentdir):
        if os.path.splitext(fname)[1] == '.docx':
            file = os.path.join(parentdir, fname)
            output = invokeRSvalidate(file, user_email, user_name)
            print output

# logging. parameter handling. process watcher management. erreor mail. test python version here vs server.

# will need to override dbox params in rsvalidate; may be a little tricky.
# But can define args by script, so shouls not be bad; and can force disable dropbox based on executable.

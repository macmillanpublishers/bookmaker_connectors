# this file accepts arguments from flask api and invokes bookmaker process
import os
import shutil
import logging
import shared_cfg
import platform
from textwrap import dedent


# # Local key definitions
productname = 'bookmaker'
infile_basename = os.path.basename(shared_cfg.inputfile)
product_cmd = os.path.join(shared_cfg.bkmkr_scripts_dir, "bookmaker_deploy", "bookmaker_direct.bat")
bkmkr_tmpdir = os.path.join(os.path.join("S:", os.sep, "bookmaker_tmp"))
if platform.system() != 'Windows':  # for testing:
    bkmkr_tmpdir = os.path.join(os.sep, 'Users', shared_cfg.currentuser, 'testup', 'bkmkr_tmp')


# # # EMAIL TEMPLATES for bookmaker_Exec:
# for Alerts
alerttxts = ''
alertmail_subject = "bookmaker update: a problem with your submitted files"
alertmail_txt = dedent("""
    Hello {uname},

    Bookmaker encountered the problem(s) listed below when attempting to process your submitted file(s):
    (submitted file(s): {infile_basename})

    {alerttxts}

    Please resolve the above issues and resubmit to bookmaker!

    Or contact the workflows team at {to_mail} for further assistance:)
    """)

# for Success
successmail_subject = "bookmaker processing begun for: '{docx_basename}'"
zipfile_extratext = ''
if shared_cfg.file_ext == '.zip':
    zipfile_extratext = " (from zipfile '{}')".format(infile_basename)
successmail_txt = dedent("""
    Hello {uname},

    Bookmaker has begun processing your submitted manuscript '{docx_basename}'{zipfile_extratext}.


    If you don't receive a follow-up email from bookmaker within 20-25 minutes, please reach out to the workflows team for further assistance: {to_mail}.
    """)

# addons for Staging server
if os.path.isfile(shared_cfg.staging_file):
    alertmail_subject += '- {}'.format(shared_cfg.server)
    alertmail_txt += '\n\nSENT FROM BOOKMAKER STAGING (TESTING) SERVER'
    successmail_subject += '- {}'.format(shared_cfg.server)
    successmail_txt += '\n\nSENT FROM BOOKMAKER STAGING (TESTING) SERVER'


# # # FUNCTIONS
# walk through the tree and unzip all .zips (not nested ones)
def walkAndUnzip(root_dir, err_dict):
    try:
        for root, dirs, files in os.walk(root_dir):
            zips = [f for f in files if (os.path.splitext(f)[1] == '.zip' and os.path.join(root, f) != shared_cfg.inputfile)]
            dirs[:] = [d for d in dirs if d not in ['__MACOSX']]
            for name in zips:
                # print('found zip {}'.format(os.path.join(root, name)))
                logging.debug("unzipping sub-zip: {}".format(os.path.join(root, name)))
                shared_cfg.unzipZips(os.path.join(root, name), shared_cfg.err_dict)
    except Exception as e:
        logging.error('Error walking and unzipping "{}"'.format(shared_cfg.inputfile), exc_info=True)
        shared_cfg.sendExceptionAlert(e, err_dict)

def checkSubmittedFiles(root_dir, err_dict):
    walkAndUnzip(root_dir, err_dict)
    word_docs = []
    all_docs = {}
    dupe_files = set()
    try:
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in ['__MACOSX']]
            files[:] = [f for f in files if f not in ['.DS_Store'] and os.path.splitext(f)[1] != '.zip']
            for name in files:
                relative_name = os.path.join(root, name).replace(root_dir,'')
                # capture all .doc or .docx files so we can count them
                if os.path.splitext(name)[1] == '.docx' or os.path.splitext(name)[1] == '.doc':
                    word_docs.append(relative_name)
                # check if we've already captured a doc with this name
                if name in all_docs.keys():
                    # track relative names of both dupes
                    dupe_files.add(relative_name)
                    dupe_files.add(all_docs[name])
                all_docs[name] = relative_name
                # print(os.path.join(root, name))
    except Exception as e:
        logging.error('Error checking bookmaker submitted files "{}"'.format(shared_cfg.inputfile), exc_info=True)
        shared_cfg.sendExceptionAlert(e, err_dict)
    finally:
        return word_docs, list(dupe_files)

def passBookmakerSubmittedFiles(root_dir, new_tmpdir, submittedfiles_dir, err_dict):
    sanitized_docxname = ''
    try:
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in ['__MACOSX']]
            files[:] = [f for f in files if f not in ['.DS_Store'] and os.path.splitext(f)[1] != '.zip']
            for name in files:
                fname_ext = os.path.splitext(name)[1]
                currentfile = os.path.join(root, name)
                # strip out whitespace and bad chars from docx basename as we move it
                #   (these can sneak in in a zipped .docx)
                if fname_ext == '.docx' or fname_ext == '.doc':
                    dest_filename = shared_cfg.sanitizeFilename(name, err_dict)
                    sanitized_docxname = dest_filename
                else:
                    dest_filename = name
                movedfile = os.path.join(submittedfiles_dir, dest_filename)
                # docx and config.json go in newtmpdir_root, everythign else goes in s-i dir
                if fname_ext == '.docx' or fname_ext == '.doc' or name == 'config.json':
                    movedfile = os.path.join(new_tmpdir, dest_filename)
                logging.debug("copying {} to {}".format(currentfile, movedfile))
                shutil.move(currentfile, movedfile)
        return True, sanitized_docxname
    except Exception as e:
        logging.error('Error sending submitted files to bookmaker "{}"'.format(shared_cfg.inputfile), exc_info=True)
        shared_cfg.sendExceptionAlert(e, err_dict)
        return False


# # # RUN
if __name__ == '__main__':
    try:
        # init logging
        logging.basicConfig(filename=shared_cfg.logfile, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt='%Y-%m-%d %H:%M:%S')#DEBUG)
        logging.info("* * * * * * running '{}'".format(shared_cfg.this_script))
        # unzip file if it was a zip, right into the parentdir
        shared_cfg.unzipZips(shared_cfg.inputfile, shared_cfg.err_dict)
        # unlike the other two execs; here we want all files passed. Walking folder-tree (if present) three times:
        #   Once to unzip any nested zips (just one pass, not digging into nested>nested zips)
        #   Again to verify only one .doc(x) file and no files with the same names in different dirs
        #   And finally to pass unique files to a new tmpfolder for bookmaker
        word_docs, dupe_files = checkSubmittedFiles(shared_cfg.parentdir, shared_cfg.err_dict)

        # prepare notice for the wrong number of docx files
        if len(word_docs) != 1:
            alerttxts += "-- Bookmaker requires that exactly one Word .doc(x) be present in each file submission; however, "
            if len(word_docs) == 0:
                alertstr = "no .doc(x) files were found among submitted file(s)."
            else:
                alertstr = "more than one .doc(x) file was present among submitted file(s).\n(docx files: {})".format(word_docs)
            alerttxts += "{}\n\n".format(alertstr)
            logging.warn(alertstr)
        # prepare notice re: duplicate filenames in received heirarchy
        if dupe_files:
            alertstr = "-- Some files with exact same name were found among submitted files. \nFiles: {}".format(dupe_files)
            alerttxts += "{}\n\n".format(alertstr)
            logging.warn(alertstr)
        # send mail as needed
        if alerttxts:
            logging.info("sending mail to submitter re: previous warnings")
            shared_cfg.sendmail.sendMail([shared_cfg.user_email], alertmail_subject, \
                alertmail_txt.format(uname=shared_cfg.user_name, infile_basename=infile_basename, alerttxts=alerttxts, to_mail=shared_cfg.alert_emails_to[0]))

        # we're ok! proceed with creating tmpdir for bookmaker and moving files there
        if not dupe_files and len(word_docs) == 1:
            # make dest tmpdir(s)
            new_tmpdir = os.path.join(bkmkr_tmpdir, shared_cfg.bkmkr_project, os.path.basename(shared_cfg.parentdir))
            submittedfiles_dir = os.path.join(new_tmpdir, 'submitted_files') # bookmaker sub-tmpdir for all non-docx files
            shared_cfg.try_create_dir(submittedfiles_dir, shared_cfg.err_dict)
            # send files
            filepass_ok, sanitized_docxname = passBookmakerSubmittedFiles(shared_cfg.parentdir, new_tmpdir, submittedfiles_dir, shared_cfg.err_dict)
            logging.debug("filepass_ok: {}".format(filepass_ok))

            # tempdir created, files moved, now kickoff bookmaker!
            if filepass_ok == True:
                # set params
                docx_basename = os.path.basename(word_docs[0])  # used for mailer instead of sanitized_docxname
                newdocfilepath = os.path.join(new_tmpdir, sanitized_docxname)
                popen_params = [r'{}'.format(os.path.join(product_cmd)), newdocfilepath, \
                    shared_cfg.runtype_string, shared_cfg.user_email, shared_cfg.user_name]
                # invoke subprocess.popen
                logging.info("invoking {} for {}".format(productname, newdocfilepath))
                logging.debug("process params: {}".format(popen_params))
                process_ok = shared_cfg.invokeSubprocess(popen_params, productname, shared_cfg.err_dict)
                # send 'bookmaker_begun' email to submitter
                if process_ok == True:
                    shared_cfg.sendmail.sendMail([shared_cfg.user_email], successmail_subject.format(docx_basename=docx_basename), \
                        successmail_txt.format(uname=shared_cfg.user_name, zipfile_extratext=zipfile_extratext, docx_basename=docx_basename, to_mail=shared_cfg.alert_emails_to[0]))
                    logging.info("emailed submitter bookmaker-start notification")

    except Exception as e:
        logging.error("untrapped top-level exception occurred", exc_info=True)
        shared_cfg.sendExceptionAlert(e, shared_cfg.err_dict)

# this file accepts arguments from flask api and invokes rsvalidate process
import os
import logging
import shared_cfg


# # Local key definitions
productname = 'rsuite_validate'
productname_cap = productname[0].upper() + productname[1:]
product_cmd = os.path.join(shared_cfg.bkmkr_scripts_dir, "sectionstart_converter", "xml_docx_stylechecks", "rsuitevalidate_main.py")


# # # RUN
if __name__ == '__main__':
    try:
        # init logging
        logging.basicConfig(filename=shared_cfg.logfile, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt='%Y-%m-%d %H:%M:%S')#DEBUG)
        logging.info("* * * * * * running {} for file: '{}'".format(shared_cfg.this_script, shared_cfg.infile_name))
        # unzip file if it was a zip, right into the parentdir
        shared_cfg.unzipZips(shared_cfg.inputfile, shared_cfg.err_dict)
        # we're only looking for docx that were zipped solo here; so just checking for docx in
        #   parentdir (where zips where extracted to) should be fine (no need to recurse)
        word_doc_count = 0
        for fname in os.listdir(shared_cfg.parentdir):
            if os.path.splitext(fname)[1] == '.docx':
                word_doc_count += 1
                # sanitize filename in case it was in a zip and has unfriendly chars
                sanitized_fname = shared_cfg.sanitizeFilename(fname, shared_cfg.err_dict)
                # define file with full path
                file = os.path.join(shared_cfg.parentdir, sanitized_fname)
                # make copy of file with sanitized name
                if sanitized_fname != fname:
                    shared_cfg.copyFile(os.path.join(shared_cfg.parentdir, fname), file, shared_cfg.err_dict)
                logging.debug('found docx: {}'.format(file))
                popen_params = [shared_cfg.pypath, r'{}'.format(os.path.join(product_cmd)), file, shared_cfg.runtype_string, \
                    shared_cfg.user_email, shared_cfg.user_name]
                logging.info("invoking {} for {}; parameters: {}".format(productname, sanitized_fname, popen_params))
                output = shared_cfg.invokeSubprocess(popen_params, productname, shared_cfg.err_dict)
        # send mail if we didn't find any word docs
        if shared_cfg.file_ext == '.zip' and word_doc_count == 0:
            # get mail ready:
            alerttxts = "-- {} requires that exactly one Word .doc(x) be present in each file submission; however, no .doc(x) files were found among submitted file(s).".format(productname_cap)
            subject = shared_cfg.alertmail_subject.format(productname=productname)
            mail_txt = shared_cfg.alertmail_txt.format(uname=shared_cfg.user_name, infile_basename=shared_cfg.infile_name, \
            alerttxts=alerttxts, productname=productname, productname_cap=productname_cap, to_mail=shared_cfg.alert_emails_to[0])
            # send mail
            logging.warn("sending mail to submitter: no docx found in submitted zip")
            shared_cfg.sendmail.sendMail([shared_cfg.user_email], subject, mail_txt)
        elif word_doc_count > 1:
            logging.warn("found (and presumably processed) more than 1 docx file in zip (word_doc_count = {})".format(word_doc_count))

    except Exception as e:
        logging.error("untrapped top-level exception occurred", exc_info=True)
        shared_cfg.sendExceptionAlert(e, shared_cfg.err_dict)

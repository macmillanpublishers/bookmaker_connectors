# this file accepts arguments from flask api and invokes rsvalidate process
import os
import logging
import shared_cfg


# # Local key definitions
rsvalidate_cmd = os.path.join(shared_cfg.bkmkr_scripts_dir, "sectionstart_converter", "xml_docx_stylechecks", "rsuitevalidate_main.py")


# # # RUN
if __name__ == '__main__':
    try:
        # unzip file if it was a zip, right into the parentdir
        shared_cfg.unzipZips(shared_cfg.inputfile, shared_cfg.err_dict)
        # we're only looking for docx that were zipped solo here; so just checking for docx in
        #   parentdir (where zips where extracted to) should be fine (no need to recurse)
        for fname in os.listdir(shared_cfg.parentdir):
            if os.path.splitext(fname)[1] == '.docx':
                file = os.path.join(shared_cfg.parentdir, fname)
                logging.debug('found docx: {}'.format(file))
                popen_params = [shared_cfg.pypath, r'{}'.format(os.path.join(rsvalidate_cmd)), file, shared_cfg.runtype_string, \
                    shared_cfg.user_email, shared_cfg.user_name]
                output = shared_cfg.invokeSubprocess(popen_params, 'rsuite_validate', shared_cfg.err_dict)

    except Exception as e:
        logging.error("untrapped top-level exception occurred", exc_info=True)
        shared_cfg.sendExceptionAlert(e, shared_cfg.err_dict)

# this file accepts arguments from flask api and invokes bookmaker process
import os
import logging
import shared_cfg


# # Local key definitions
productname = 'bookmaker'
product_cmd = os.path.join(shared_cfg.bkmkr_scripts_dir, "bookmaker_deploy", "rs_to_bkmkr.bat")


# # # RUN
if __name__ == '__main__':
    try:
        # unzip file if it was a zip, right into the parentdir
        shared_cfg.unzipZips(shared_cfg.inputfile, shared_cfg.err_dict)
        # unlike the other two execs; here we want all files passed. May walk tree and pickup
        #   any with whitelisted file exts. (or ignore blacklisted ones)
        for fname in os.listdir(shared_cfg.parentdir):
            if os.path.splitext(fname)[1] == '.docx':
                file = os.path.join(shared_cfg.parentdir, fname)
                logging.debug('found docx: {}'.format(file))
                popen_params = [r'{}'.format(os.path.join(product_cmd)), file, shared_cfg.runtype_string, \
                    shared_cfg.user_email, shared_cfg.user_name, shared_cfg.bookmakerproject]
                logging.info("invoking {} for {}".format(productname, fname))
                output = shared_cfg.invokeSubprocess(popen_params, productname, shared_cfg.err_dict)

    except Exception as e:
        logging.error("untrapped top-level exception occurred", exc_info=True)
        shared_cfg.sendExceptionAlert(e, shared_cfg.err_dict)

    # from sys import argv
    #
    # count = 0
    # for arg in argv:
    # 	count += 1
    # 	print("argv{}: {}".format(count, arg))

# TO do: look at existing .bat, does it cover param passing needs? Can make a new one. Can write params passed initially
# to metadata in tmparchive_rsuite tooo... This may work a little differently than wat we have going.
# ALSO:
# need to capture all files in zip. Again look at handling in tmparchive_rsuite.

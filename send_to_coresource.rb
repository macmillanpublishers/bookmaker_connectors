require 'fileutils'

require_relative '../bookmaker/core/header.rb'
require_relative '../bookmaker/core/metadata.rb'

# ---------------------- VARIABLES

local_log_hash, @log_hash = Bkmkr::Paths.setLocalLoghash

csfilename = "#{Metadata.eisbn}_EPUB"
csfilename = renameFinalEpub(csfilename, stage_dir, 'rename_final_epub_for_firstpass')
csdir = File.join(Bkmkr::Project.working_dir, "send_to_coresource")
epubregexp = File.join(Bkmkr::Paths.done_dir, "*.epub")

# ---------------------- METHODS

## wrapping a Mcmlln::Tools method in a new method for this script; to return a result for json_logfile
def localCopyFile(source, dest, logkey='')
  Mcmlln::Tools.copyFile(source, dest)
  logstring = 'copying to send_to_coresource folder'
rescue => logstring
ensure
    Mcmlln::Tools.logtoJson(@log_hash, logkey, logstring)
end

# ---------------------- PROCESSES

# copy all epubs from done dir
# to coresource_send dir,
# which then triggers the coresource_connector.rb script in /utilities
localCopyFile(epubregexp, csdir, "copyfile")

# Write json log:
Mcmlln::Tools.logtoJson(@log_hash, 'completed', Time.now)
Mcmlln::Tools.write_json(local_log_hash, Bkmkr::Paths.json_log)
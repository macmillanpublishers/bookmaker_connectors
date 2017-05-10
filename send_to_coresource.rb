require 'fileutils'

require_relative '../bookmaker/core/header.rb'
require_relative '../bookmaker/core/metadata.rb'

# ---------------------- VARIABLES

csfilename = "#{Metadata.eisbn}_EPUB"
csfilename = renameFinalEpub(csfilename, stage_dir, 'rename_final_epub_for_firstpass')
csdir = File.join(Bkmkr::Project.working_dir, "send_to_coresource")
epubregexp = File.join(Bkmkr::Paths.done_dir, "*.epub")

# ---------------------- METHODS

## wrapping a Mcmlln::Tools method in a new method for this script; to return a result for json_logfile
def localCopyFile(source, dest)
  Mcmlln::Tools.copyFile(source, dest)
end

# ---------------------- PROCESSES

# copy all epubs from done dir
# to coresource_send dir,
# which then triggers the coresource_connector.rb script in /utilities
localCopyFile(epubregexp, csdir)
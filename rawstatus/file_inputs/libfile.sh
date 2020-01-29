export RAW_IS_FOLDER=0
export KANTELEHOST=https://mozzarella.scilifelab.se
export SCP_FULL=mslab.mslab@kalevala.scilifelab.se:/home/tmp

export CLIENT_ID=b3894e6112cbbf68a0af8fe500bc96bfb45bdb99
export KEYFILE=/home/jorrit/.ssh/mslab

if [ $# -eq 3 ] 
  then
      export FILETYPE_ID=$2
      python "$(dirname "$0")"/upload_libfiles.py $1 "$3"
  else
    echo USAGE:
    echo ./libfile.sh FNPATH FT_ID DESCRIPTION
    echo Example:
    echo ./libfile.sh /path/to/file.fa  25  'A new libary file'
fi

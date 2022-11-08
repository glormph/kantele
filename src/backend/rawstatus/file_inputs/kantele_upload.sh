#!/usr/bin/env bash

set -euo pipefail

if [[ -e "$1" ]] 
then
    echo Started upload script
else
    echo File "$1" does not exist, is the path correct?
fi

python3 -m venv .kantele-upload-venv
source .kantele-upload-venv/bin/activate
pip install requests requests_toolbelt

python upload.py --file "$1"

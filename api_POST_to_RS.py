import sys
import os
import requests
from xml.etree import ElementTree

file = sys.argv[1]
url_POST = sys.argv[2]

try:
    rs_status_code, rs_status_msg, r = '', '', ''
    # send POST request with file
    filename = os.path.basename(file)
    fileobj = open(file,'rb')
    r = requests.post(url_POST, data = {"mysubmit":"Go"}, files={"file": (filename, fileobj)})
    # parse xml output for more info
    root = ElementTree.fromstring(r.content)
    for key in root.iter('*'):
        if key.tag == 'status-code':    # < - this represents status-code from rsuite-api
            rs_status_code = key.text
        elif key.tag == 'status-message':
            rs_status_msg = key.text

    results_str  = '{}_{}'.format(rs_status_code, rs_status_msg)

except Exception as e:
    if r:
        results_str = 'err-api-code-{}_api-msg-{}'.format(r.status_code, r.content)
    else:
        results_str = 'n-a_{}-err--{}'.format(os.path.basename(__file__), e)
finally:
    print results_str

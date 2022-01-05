import sys
import os

root = os.path.dirname(os.path.realpath(__file__))
if sys.path[0] != root:
    sys.path.insert(0, root)

#from my_flask_app import app as application

from my_flask_app import app as application




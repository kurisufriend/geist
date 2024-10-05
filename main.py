from geist import geist
from sys import argv

if (len(argv) > 1): geist(argv[1]).run()
else: geist().run()
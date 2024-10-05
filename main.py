from geist import geist
from sys import argv
import asyncio

if (len(argv) > 1): asyncio.run(geist(argv[1]).run())
else: asyncio.run(geist().run())
"""Exit 0 when two EPUBs differ only in their dcterms:modified stamp."""
import re, sys, zipfile
a, b = (zipfile.ZipFile(p) for p in sys.argv[1:3])
if sorted(a.namelist()) != sorted(b.namelist()):
    sys.exit(1)
strip = lambda d: re.sub(rb'<meta property="dcterms:modified">[^<]*</meta>', b"", d)
sys.exit(0 if all(strip(a.read(n)) == strip(b.read(n)) for n in a.namelist()) else 1)

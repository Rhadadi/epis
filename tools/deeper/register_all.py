"""Register every SEP/IEP corpus document that has no source key yet (keys get a/b suffixes on collision)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus_lib import c, sources, keydocs
import srcadd
S = srcadd.S
have = {d for k in S for d in keydocs(k, S)}
for r in c.execute("select id, title from docs where (url like '%plato.stanford%' or url like '%iep.utm%') order by id"):
    if r["id"] in have:
        continue
    try:
        srcadd.from_corpus(r["id"])
    except SystemExit as e:
        msg = str(e)
        if "already exists" in msg:
            base = msg.split()[0]
            for suf in "bcdef":
                if base + suf not in S:
                    srcadd.from_corpus(r["id"], base + suf); break
        else:
            print("skip", r["id"], msg)
import json
with open(srcadd.SOURCES_PATH, "w") as f:
    json.dump(dict(sorted(S.items())), f, ensure_ascii=False, indent=2); f.write("\n")

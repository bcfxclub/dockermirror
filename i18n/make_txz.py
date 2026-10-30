import tarfile, os

BASE = "D:/AI/Work/2026-10-29-21-34-19/dockermirror/i18n"
BUILD = os.path.join(BASE, "build", "usr")
OUT = os.path.join(BASE, "unraid-docker-folders-modern-2026.10.29-zh1.txz")

assert os.path.isdir(BUILD), "build dir missing: %s" % BUILD
if os.path.exists(OUT):
    os.remove(OUT)

with tarfile.open(OUT, "w:xz") as tar:
    for root, dirs, files in os.walk(BUILD):
        for name in sorted(files):
            full = os.path.join(root, name)
            arc = "usr/" + os.path.relpath(full, BUILD).replace(os.sep, "/")
            ti = tar.gettarinfo(full, arcname=arc)
            ti.uid = 0; ti.gid = 0; ti.uname = "root"; ti.gname = "root"
            with open(full, "rb") as f:
                tar.addfile(ti, f)
        for d in sorted(dirs):
            full = os.path.join(root, d)
            arc = "usr/" + os.path.relpath(full, BUILD).replace(os.sep, "/")
            ti = tar.gettarinfo(full, arcname=arc)
            ti.uid = 0; ti.gid = 0; ti.uname = "root"; ti.gname = "root"
            tar.addfile(ti)

print("created", OUT, "size bytes:", os.path.getsize(OUT))
with tarfile.open(OUT, "r:*") as t:
    names = t.getnames()
print("entries:", len(names))
print("sample:", names[:3])

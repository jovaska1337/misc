#!/bin/env python

# convert image to METADATA_BLOCK_PICTURE

import os
import re
import sys
import struct
import base64
import subprocess

def ffprobe(path):
    proc = subprocess.Popen([
            "ffprobe",
            "-loglevel", "quiet",
            "-count_packets",
            "-count_frames",
            "-show_entries", "format:stream",
        path],
        stdin=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.PIPE)

    out = str(proc.communicate()[0], 'utf-8')

    proc.wait()

    if proc.returncode != 0:
        raise RuntimeError("ffprobe: nonzero exit status ({})"
            .format(proc.returncode))

    kv = {}

    tag = None
    tgt = None

    for line in out.split("\n"):
        line = line.strip()

        m = re.match("^\[([^/][^\]]+)\]$", line)
        if m:
            tmp = m.group(1)

            if tag != None:
                continue

            if tmp == "FORMAT":
                tgt = kv

            elif tmp == "STREAM":
                tgt = {}

            tag = tmp

            continue

        m = re.match("^\[/([^\]]+)\]$", line)
        if m:
            tmp = m.group(1)

            if tag != tmp:
                continue

            if tmp == "STREAM":
                if "index" in tgt:
                    if not "__streams__" in kv:
                        kv["__streams__"] = []

                    l = kv["__streams__"]
                    i = int(tgt["index"])

                    if i > (len(l) - 1):
                        l.extend([None for x in range(len(l), i + 1)])

                    kv["__streams__"][i] = tgt

            tag = None
            tgt = None

            continue

        m = re.match("^([^=]+)=(.+)$", line)
        if m:
            key = m.group(1)
            val = m.group(2)

            if tgt != None:
                tgt[key] = val

            continue

    return kv

def usage():
    print("""
Usage: IDV3v2_TYPE DESCRIPTION IMAGE"
Where IDV3v2_TYPE is one of:
   0 - Other
   1 - 32x32 pixels 'file icon' (PNG only)
   2 - Other file icon
   3 - Cover (front)
   4 - Cover (back)
   5 - Leaflet page
   6 - Media (e.g. label side of CD)
   7 - Lead artist/lead performer/soloist
   8 - Artist/performer
   9 - Conductor
  10 - Band/Orchestra
  11 - Composer
  12 - Lyricist/text writer
  13 - Recording Location
  14 - During recording
  15 - During performance
  16 - Movie/video screen capture
  17 - A bright coloured fish
  18 - Illustration
  19 - Band/artist logotype
  20 - Publisher/Studio logotype
    """.strip(), file=sys.stderr)
    sys.exit(1)

def main():
    if len(sys.argv) != 4:
        usage()

    # get args
    idv3 = sys.argv[1].strip()
    desc = sys.argv[2].strip()
    file = sys.argv[3]

    # validate idv3 type
    try:
        idv3 = int(idv3)
    except:
        usage()
    if (idv3 < 0) or (idv3 > 20):
        usage()

    # check that file exists
    if not (os.path.isfile(file) and os.access(file, os.R_OK)):
        print(f"Can't access '{file}'", file=sys.stderr)
        return 1

    # get file mime type 
    tmp = subprocess.check_output(["file", "--mime", file])
    tmp = tmp.split(b":", 1)
    tmp = tmp[1].split(b";", 1)
    tmp = tmp[0].strip()
    if not tmp.startswith(b"image/"):
        print(f"'{file}' is not an image ({str(tmp, 'utf-8')})", file=sys.stderr)
        return 1
    mime = tmp

    # get width, heigth and bpp
    tmp = ffprobe(file)
    tmp = tmp["__streams__"][0]
    w   = tmp["width"]
    h   = tmp["height"]
    bpp = tmp["bits_per_raw_sample"]
    if bpp == "N/A":
        # determine manually
        tmp = tmp["pix_fmt"]
        if tmp == "rgb24":
            bpp = 24
        else:
            print("Unable to detemine pixel depth.", file=sys.stderr)
            return 1
    w   = int(w)
    h   = int(h)
    bpp = int(bpp)

    # construct data
    data = bytearray()
    data += struct.pack(">I", idv3)
    data += struct.pack(">I", len(mime))
    data += mime
    data += struct.pack(">I", len(desc))
    if len(desc) > 0:
        data += bytes(desc, "utf-8")
    data += struct.pack(">I", w)
    data += struct.pack(">I", h)
    data += struct.pack(">I", bpp)
    data += b'\0\0\0\0'
    with open(file, "rb") as fp:
        tmp = fp.read()
        data += struct.pack(">I", len(tmp))
        data += tmp

    # write output
    sys.stdout.buffer.write(b"METADATA_BLOCK_PICTURE=")
    sys.stdout.buffer.write(base64.b64encode(data))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()

    return 0

if __name__ == "__main__":
    sys.exit(main())

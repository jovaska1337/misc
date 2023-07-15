#!/bin/env python

import re
import os
import sys
import math
import getopt
import subprocess

def cue_ltok(line):
    tok = []

    quot = False
    prev = None
    char = None

    i = 0
    j = 0
    k = 0

    while i < len(line):
        char = line[i]

        if quot:
            if char == "\"" and (prev != "\\"):
                quot = False

            k += 1

        else:
            if (char == "\"") and (prev != "\\"):
                j += 1
                quot = True

            elif char.isspace():
                if k > j:
                   tok.append(line[j:k]) 
                k = j = i + 1

            else:
                k += 1

        prev = char

        i += 1

    if k > j:
        tok.append(line[j:k])

    if len(tok) < 1:
        return (None, None)

    return (tok[0].upper(), tok[1:])

def dur2ms(s):
	dur = 0
	tmp = s.split(":")

	i = 0
	while i < len(tmp):
		dur += float(tmp[len(tmp) - 1 - i]) * math.pow(60.0, i)
		i   += 1

	return int(round(dur * 1000.0, 0))

def ms2dur(ms):
	secs = ms // 1000
	mils = ms % 1000 

	hrs  = secs // 3600
	secs = secs % 3600
	mins = secs // 60
	secs = secs % 60

	return "{:02d}:{:02d}:{:02d}.{:03d}".format(hrs, mins, secs, mils)

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

def meta(data, key, value="", stream=None):
    if not stream in data:
        data[stream] = {}
    data[stream][key] = value

def usage():
    print("Usage: {} [OPTIONS] CUESHEET [[STREAM:]KEY[=VALUE]...".format(sys.argv[0]))
    print("Known options are:")
    print("  -h,--help         : print this usage")
    print("  -t,--type=<TYPE>  : select output type (flac)")
    print("  -p,--path=<PATH>  : output path        (cuesheet directory)")
    print("  -c,--cover=<PATH> : path to cover art  (autodetected)")
    print("Known output types are:")
    print("  mp3  : re-encode to 320kpbs mp3")
    print("  flac : remux to singlular flac files")

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "ht:p:c", \
            ["help", "type=", "path=", "cover="])
    except getopt.GetoptError:
        usage()
        return 1

    if len(args) < 1:
        usage()
        return 1

    out_type   = None
    out_path   = None
    cover_path = None

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            return 0

        elif opt in ("-t", "--type"):
            if not arg in ("mp3", "flac"):
                print("Invalid output type '{}'.".format(arg))
                return 1
            out_type = arg

        elif opt in ("-p", "--path"):
            try:
                os.makedirs(arg, exist_ok=True)
            except OSError:
                print("Invalid output path.")
                return 1
            out_path = arg

        elif opt in ("-c", "--cover"):
            try:
                out = ffprobe(arg)
                if not out["format_name"] in ["image2", "png_pipe"]:
                    raise Exception()
                cover_path = arg
            except:
                print("Invalid cover path.")
                return 1
    cue_path = args[0]
    ext_meta = args[1:]

    if not os.path.isfile(cue_path):
        print("No such cuesheet.")
        return 1

    cue_dir = os.path.dirname(cue_path)
    if len(cue_dir) == 0:
        cue_dir = "."

    if out_path == None:
        out_path = cue_dir 
    if out_type == None:
        out_type = "flac"

    genre  = None
    date   = None
    file   = None
    album  = None
    artist = None
    target = None
    tracks = []

    with open(cue_path, "r", encoding="latin-1") as fp:
        for line in fp:
            cmd, args = cue_ltok(line[:-1])

            if cmd == "REM":
                    if len(args) != 2:
                        continue

                    key = args[0]
                    val = args[1]

                    if key == "GENRE":
                        genre = val
                    elif key == "DATE":
                        date = int("".join(c for c in val if c.isdigit()))

            elif cmd == "PERFORMER":
                if target:
                    target[4] = args[0]
                else:
                    artist = args[0]

            elif cmd == "TITLE":
                if target:
                    target[3] = args[0]
                else:
                    album = args[0]

            elif cmd == "FILE":
                file = os.path.join(cue_dir, args[0])

            elif cmd == "TRACK":
                i = int(args[0])
                
                if len(tracks) < i:
                    tracks.extend([None]*(len(tracks) - i + 2))

                tracks[i - 1] = [None]*5
                target = tracks[i - 1]

                target[0] = int(args[0])

            elif cmd == "INDEX":
                i = tracks.index(target)

                target[1] = dur2ms(".".join(args[1].rsplit(":",1)))
                target[2] = 0

    if not os.path.isfile(file):
        name, ext = file.rsplit(".", 1)

        for try_ext in ["flac"]:
            if try_ext != ext:
                file = name + "." + try_ext
                if os.path.isfile(file):
                    break
        else:
            print("'{}.{}' is not a file.".format(name, ext))
            return 1

    metadata = ffprobe(file)
    
    full_duration = int(float(metadata['duration'])*1000)

    i = 0
    while i < len(tracks):
        if i < (len(tracks) - 1):
            next_offset = tracks[i + 1][1]
        else:
            next_offset = full_duration

        tracks[i][2] = next_offset - tracks[i][1]

        i += 1

    if cover_path == None:
        for name in ["cover", "front", "folder"]:
            for tmp in os.listdir(cue_dir):
                if not os.path.isfile(tmp):
                    continue
                try:
                    out = ffprobe(tmp)
                except:
                    continue
                if out["format_name"] != ["image2", "png_pipe"]:
                    continue
                if tmp.lower().startswith(name):
                    cover_path = os.path.join(cue_dir, tmp)
                    break
            if cover_path != None:
                break

    print("Parsed cuesheet:")
    print("  File     : '{}'".format(file))
    if cover_path != None:
        print("  Cover    : '{}'".format(cover_path))
    print("  Artist   : '{}'".format(artist))
    print("  Album    : '{}'".format(album))
    print("  Genre    : '{}'".format(genre))
    print("  Date     : '{}'".format(date))
    print("  Duration : {}".format(ms2dur(full_duration)))
    print("  Tracks   : {}".format(len(tracks)))
    for track in tracks:
        print("    {:02d} - {} ({})" \
            .format(track[0], track[3], \
                ms2dur(track[2])))

    ffmpeg_metadata = {}

    for arg in ext_meta:
        tmp = arg.split(":", 2)
        if len(tmp) == 2:
            stm = tmp[0]
            arg = tmp[1]
        else:
            stm = None

        tmp = arg.split("=", 2)
        if len(tmp) == 2:
            key = tmp[0]
            val = tmp[1]
        else:
            key = arg
            val = ""

        meta(ffmpeg_metadata, key, val, stm)

    i = 0
    while i < len(tracks):
        index, offset, duration, title, _ = tracks[i]

        cmd = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-stats"]

        if i != 0:
            cmd.extend(["-ss", ms2dur(offset)])
        
        if i != (len(tracks) - 1):
            cmd.extend(["-t", ms2dur(duration)])

        cmd.extend(["-i", file])
        
        if cover_path != None:
            cmd.extend(["-i", cover_path])

        ext = None
        if out_type == "mp3":
            cmd.extend([
                "-c:a", "libmp3lame",
                "-ab", "320k",
                "-map_metadata", "0",
                "-id3v2_version", "3"
            ])
            ext = "mp3"
        elif out_type == "flac":
            cmd.extend([
                "-c:a", "flac",
                "-map_metadata", "0"
            ])
            ext = "flac"
        else:
            raise RuntimeError("Impossible.")

        if cover_path != None:
            cmd.extend(["-c:v", "mjpeg"])

        if album:
            meta(ffmpeg_metadata, "album", album)
        if artist:
            meta(ffmpeg_metadata, "artist", artist)
        if genre:
            meta(ffmpeg_metadata, "genre", genre)
        if date:
            meta(ffmpeg_metadata, "date", date)
        if title:
            meta(ffmpeg_metadata, "title", title)

        meta(ffmpeg_metadata, "track", "{}/{}".format(index, len(tracks)))

        # these aren't stripped automatically
        meta(ffmpeg_metadata, "LOG")
        meta(ffmpeg_metadata, "CUESHEET")
        meta(ffmpeg_metadata, "COMMENT")
        meta(ffmpeg_metadata, "ENCODEDBY")
        meta(ffmpeg_metadata, "ALBUM ARTIST")

        # this does fuck all for whatever reason
        cmd.extend(["-map_metadata", "-1"])

        if cover_path != None:
            meta(ffmpeg_metadata, "title", "Album cover", "v")
            meta(ffmpeg_metadata, "comment", "Cover (front)", "v")
            cmd.extend(["-disposition:v", "attached_pic"])

        # metadata (use arguments from command line)
        for stream in ffmpeg_metadata:
            base = "-metadata"
            if stream != None:
                base = base + ":s:" + stream
            tmp = ffmpeg_metadata[stream]
            for key in tmp:
                cmd.extend([base, "{}={}".format(key, tmp[key])])

        cmd.extend(["-map", "0:a"])

        if cover_path != None:
            cmd.extend(["-map", "1:v"])

        cmd.extend([os.path.join(out_path, \
            "{:02d} - {}.{}".format(index, title, ext) \
                .replace("/", "_"))])

        subprocess.call(cmd)

        i += 1

    return 0

if __name__ == "__main__":
    sys.exit(main())

#!/bin/env python

# convert image to METADATA_BLOCK_PICTURE

import sys
import struct
import base64
from pathlib import Path
from PIL import Image, UnidentifiedImageError
import io


def usage():
    print(
        """
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
    """.strip(),
        file=sys.stderr,
    )
    sys.exit(1)


def image_bit_depth(image: Image.Image) -> int:
    """
    Returns the bit depth of the image. Equivalent to bits_per_raw_sample from FFmpeg/FFprobe.
    """
    mode = image.mode
    if mode == "1":
        return 1
    elif mode in {"L", "P", "RGB", "RGBA", "CMYK", "YCbCr", "LAB", "HSV"}:
        return 8
    elif mode in {"I", "F"}:
        return 32
    else:
        raise ValueError(f"Unsupported image mode: {mode}")


def main():
    if len(sys.argv) != 4:
        usage()

    # get args and validate idv3 type
    try:
        idv3 = int(sys.argv[1].strip())
    except ValueError:
        usage()
    desc = sys.argv[2].strip()
    file = Path(sys.argv[3])

    if (idv3 < 0) or (idv3 > 20):
        usage()

    # read file to bytes and open image
    try:
        image_bytes = file.read_bytes()
        img = Image.open(io.BytesIO(image_bytes))
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        print(f"Can't access '{file}'", file=sys.stderr)
        return 1
    except UnidentifiedImageError:
        # PIL can't open the file
        print(f"File: '{file}' is not an image supported by PIL", file=sys.stderr)
        return 1

    # get file mime type and convert to unicode bytes
    mime = img.get_format_mimetype().encode("utf-8")

    # get width, heigth
    width, height = img.size

    # get bits_per_pixel
    try:
        bits_per_pixel = image_bit_depth(img)
    except ValueError:
        print(f"Unsupported image in mode: {img.mode}", file=sys.stderr)
        return 1

    desc = desc.encode("utf-8")

    # construct data
    data = bytearray()
    data += struct.pack(">II", idv3, len(mime))
    data += mime
    data += struct.pack(">I", len(desc))
    if desc:
        data += desc
    data += struct.pack(">IIIII", width, height, bits_per_pixel, 0, len(image_bytes))
    data += image_bytes

    # write output
    sys.stdout.buffer.write(b"METADATA_BLOCK_PICTURE=" + base64.b64encode(data) + b"\n")
    sys.stdout.buffer.flush()

    return 0


if __name__ == "__main__":
    sys.exit(main())

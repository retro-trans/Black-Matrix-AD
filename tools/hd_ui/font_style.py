"""Pinned outline font for the stock HD packs. Run this file to fetch it.

Font files are read directly, never installed system-wide or executed.
"""
import hashlib
import io
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = '0.0.4'
DIRECTORY = ROOT/'build/fonts/bizin-gothic-v0.0.4'
MEMBER = 'BizinGothic_v0.0.4/BizinGothic-Regular.ttf'
DEFAULT_TTF = DIRECTORY/MEMBER
LICENSE = DIRECTORY/'LICENSE'
FONT_SHA256 = '302c6467491bde54d87f77293922b90950a49960b85f436f174b46b357a5d835'
ZIP_SHA256 = 'e9d01c6ba56161c8a68e2998b71508110e2d70742512f6dafde1a569b0fbf877'
LICENSE_SHA256 = '84d463be283b64d6da4645194b5a2ea57f3a99b135574cce76eea0b9e3bffada'
RELEASE = 'https://github.com/yuru7/bizin-gothic/releases/tag/v0.0.4'
URL = 'https://github.com/yuru7/bizin-gothic/releases/download/v0.0.4/BizinGothic_v0.0.4.zip'
LICENSE_URL = 'https://raw.githubusercontent.com/yuru7/bizin-gothic/v0.0.4/LICENSE'


def verified(data, expected):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Bizin Gothic asset checksum mismatch')
    return data


def default_font():
    if not DEFAULT_TTF.exists() or not LICENSE.exists():
        raise FileNotFoundError('Run tools/hd_ui/font_style.py to fetch Bizin Gothic first')
    verified(DEFAULT_TTF.read_bytes(), FONT_SHA256)
    verified(LICENSE.read_bytes(), LICENSE_SHA256)
    return DEFAULT_TTF


def copy_license(output):
    default_font()
    shutil.copyfile(LICENSE, Path(output)/'Bizin-Gothic-LICENSE.txt')


def fetch():
    if DEFAULT_TTF.exists() and LICENSE.exists():
        return default_font()
    with urllib.request.urlopen(URL, timeout=60) as response:
        archive = verified(response.read(), ZIP_SHA256)
    # Read only the explicitly named member; never extract arbitrary paths.
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        font = verified(z.read(MEMBER), FONT_SHA256)
    with urllib.request.urlopen(LICENSE_URL, timeout=60) as response:
        license_data = verified(response.read(), LICENSE_SHA256)
    for path, data in ((DEFAULT_TTF, font), (LICENSE, license_data)):
        if path.exists() and path.read_bytes() != data:
            raise ValueError('refusing to overwrite a different local font asset')
    for path, data in ((DEFAULT_TTF, font), (LICENSE, license_data)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return default_font()


if __name__ == '__main__':
    print(fetch())

import struct
from pathlib import Path
from typing import Sequence, Union, List
from dds import decode_dds

# Map DXGI format to block size (block-compressed formats use 4x4 blocks)
DXGI_BLOCK_SIZE = {
    80: 8,  # BC4_UNORM
    90: 8,  # BC4_SNORM
    83: 16,  # BC5_UNORM
    91: 16,  # BC5_SNORM
    95: 16,  # BC6H_UF16
    96: 16,  # BC6H_SF16
    98: 16,  # BC7_UNORM
    99: 16,  # BC7_UNORM_SRGB
}

# Map DXGI format to bytes per pixel (non-block-compressed formats)
DXGI_BPP = {
    28: 4,   # R8G8B8A8_UNORM
    61: 1,   # R8_UNORM
    49: 2,   # R8G8_UNORM
    118: 2,  # R8G8_SNORM (V8U8)
    71: None,  # BC1 - block compressed, handled by DXGI_BLOCK_SIZE
    74: None,  # BC2
    77: None,  # BC3
}


def _collect_mip_files(src: Union[str, Path, Sequence[Union[str, Path]]]) -> List[Path]:
    if isinstance(src, (str, Path)):
        p = Path(src)
        if p.is_dir():
            mip_files = [f for f in p.iterdir() if f.is_file() and f.stem.isdigit()]
            if not mip_files:
                raise FileNotFoundError(f"No numeric mip files found in {p}")
            return sorted(mip_files, key=lambda f: int(f.stem))
        return [p]  # single file

    return [Path(f) for f in src]


def _make_header(w: int, h: int, mips: int, dxgi: int, array_size: int) -> bytes:
    block_bytes = DXGI_BLOCK_SIZE.get(dxgi)
    bpp = DXGI_BPP.get(dxgi)

    if block_bytes:
        # Block-compressed: linear_size = blocks * block_bytes
        blocks_w = (w + 3) // 4
        blocks_h = (h + 3) // 4
        linear_size = blocks_w * blocks_h * block_bytes
    elif bpp:
        # Per-pixel: linear_size = w * h * bpp (pitch = w * bpp for DDSD_PITCH)
        linear_size = w * bpp
    else:
        raise ValueError(f"Unsupported DXGI format: {dxgi}")

    DDSD_CAPS = 0x1
    DDSD_HEIGHT = 0x2
    DDSD_WIDTH = 0x4
    DDSD_PIXELFORMAT = 0x1000
    DDSD_LINEARSIZE = 0x80000
    DDSD_PITCH = 0x8
    DDSD_MIPMAPCOUNT = 0x20000

    DDSCAPS_TEXTURE = 0x1000
    DDSCAPS_MIPMAP = 0x400000
    DDSCAPS_COMPLEX = 0x8

    if block_bytes:
        flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE
    else:
        flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_PITCH
    caps = DDSCAPS_TEXTURE
    if mips > 1:
        flags |= DDSD_MIPMAPCOUNT
        caps |= DDSCAPS_MIPMAP | DDSCAPS_COMPLEX

    header = struct.pack(
        "<4s I 6I 11I 8I 5I",
        b"DDS ", 124,
        flags, h, w, linear_size, 0, mips,
        *(0,) * 11,
        32, 0x4, struct.unpack("<I", b"DX10")[0],
        *(0,) * 5,
        caps, 0, 0, 0, 0,
    )
    dx10 = struct.pack("<5I", dxgi, 3, 0, array_size, 0)
    return header + dx10


def make_dds_data(
    source: Union[str, Path, Sequence[Union[str, Path]]],
    width: int,
    height: int,
    dxgi_format: int = 98,
    array_size: int = 1,
):
    mip_files = _collect_mip_files(source)
    mip_count = len(mip_files)
    data = b"".join(f.read_bytes() for f in mip_files)

    header = _make_header(width, height, mip_count, dxgi_format, array_size)
    return header + data


def make_png_data(
    source: Union[str, Path, Sequence[Union[str, Path]]],
    width: int,
    height: int,
    dxgi_format: int = 98,
    array_size: int = 1,
):
    mip_files = _collect_mip_files(source)
    mip_count = len(mip_files)
    full_data = b""
    first_mip_data = b""

    for i, mip in enumerate(mip_files):
        mip_bytes = mip.read_bytes()
        full_data += mip_bytes
        if i == 0:
            first_mip_data = mip_bytes

    header = _make_header(width, height, mip_count, dxgi_format, array_size)
    dds_data = header + full_data

    return dds_data, decode_dds(header + first_mip_data)


def make_png_from_data(
    raw_data: bytes,
    width: int,
    height: int,
    dxgi_format: int = 98,
    array_size: int = 1,
):
    header = _make_header(width, height, 1, dxgi_format, array_size)
    return decode_dds(header + raw_data)


def write_dds(
    source: Union[str, Path, Sequence[Union[str, Path]]],
    width: int,
    height: int,
    dxgi_format: int = 98,
    array_size: int = 1,
    output: Union[str, Path, None] = None,
) -> Path:
    mip_files = _collect_mip_files(source)
    mip_count = len(mip_files)
    data = b"".join(f.read_bytes() for f in mip_files)

    header = _make_header(width, height, mip_count, dxgi_format, array_size)

    if output is None:
        base = mip_files[0] if mip_files else Path(source) # type: ignore
        out_name = base.stem + ".dds" if base.is_file() else base.name + ".dds"
        output = base.parent / out_name

    Path(output).write_bytes(header + data)
    return Path(output)

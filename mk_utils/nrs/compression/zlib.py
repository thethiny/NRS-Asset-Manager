import zlib

from mk_utils.nrs.compression.base import CompressionBase


class ZlibCompression(CompressionBase):
    def decompress(self, chunk: bytes, output_size: int) -> bytes:
        data = zlib.decompress(chunk)
        if output_size >= 0 and len(data) != output_size:
            raise RuntimeError(
                f"ZLIB decompression size mismatch: got {len(data)}, expected {output_size}"
            )
        return data

    def compress(self, chunk: bytes, level: int = zlib.Z_DEFAULT_COMPRESSION) -> bytes:
        return zlib.compress(chunk, level)

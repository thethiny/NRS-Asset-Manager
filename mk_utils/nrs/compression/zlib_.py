import zlib

from mk_utils.nrs.compression.base import CompressionBase


class ZlibCompression(CompressionBase):
    def decompress(self, chunk, size):
        return zlib.decompress(chunk)

    def compress(self, chunk, size):
        return zlib.compress(chunk)

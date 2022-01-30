class Bitfield:
    def __init__(self, bitfield: bytes) -> None:
        # bitfield 是一个的 bitmap, 用于指示当前该终端已下载的文件分片,
        # 其中第一个字节的 8 位分别表示文件的前 8 个分片,
        # 第二个字节的 8 位分别表示文件的第 9 至 16 个分片, 以此类推.
        # 已下载的分片对应的位的值为 1, 否则为 0, 由于文件分片数不一定是 8 的整数倍,
        # 所以最后一个分片可能有冗余的比特位, 对于这些冗余的比特位都设置为 0.
        self.bitfield = bitfield

    def has_piece(self, piece_index: int):
        byte_index = int(piece_index / 8)
        offset = piece_index % 8
        if byte_index < 0 and byte_index >= len(self.bitfield):
            return False
        return ((self.bitfield[byte_index] >> (7 - offset)) & 1) != 0

    def set_piece(self, piece_index: int):
        byte_index = int(piece_index / 8)
        offset = piece_index % 8
        if byte_index < 0 and byte_index >= len(self.bitfield):
            return
        self.bitfield[byte_index] |= 1 << (7 - offset)

    def get_bitmap(self):
        bitmap = ''
        for i in range(len(self.bitfield)):
            byte_bitmap = self.bitfield[i]
            byte_bitmap = bin(byte_bitmap)[2:]
            bitmap += byte_bitmap
        return bitmap

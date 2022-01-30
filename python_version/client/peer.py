import hashlib
from typing import Union
import socket
import struct
import math

from client.bitfield import Bitfield
from utils.index import recv_full

# keep alive: <len=0000>
# choke: <len=0001><id=0>
# unchoke: <len=0001><id=1>
# interested: <len=0001><id=2>
# not interested: <len=0001><id=3>
# have: <len=0005><id=4><piece index>
# bitfield: <len=0001+X><id=5><bitfield>
# request: <len=0013><id=6><index><begin><length>
# piece: <len=0009+X><id=7><index><begin><block>
# cancel: <len=0013><id=8><index><begin><length>
# port: <len=0003><id=9><listen-port>

MSG_ID = {
    "keep alive": -1,
    "choke": 0,
    "unchoke": 1,
    "interested": 2,
    "not interested": 3,
    "have": 4,
    "bitfield": 5,
    "request": 6,
    "piece": 7,
    "cancel": 8,
    "port": 9,
}


class Peer:
    def __init__(self, peer_ip: str, peer_port: int, torrent: dict) -> None:
        socket.setdefaulttimeout(None)  # 不设置超时

        self.ip = peer_ip
        self.port = peer_port
        self.torrent = torrent
        self.conn = None
        self.bitfield = None
        self.unchoked = False  # 默认阻塞

    # 下载当前 peer 所拥有的某个 piece
    def download_piece(self,
                       piece: dict,
                       max_block_size: int = 16 * 1024,
                       max_pending_count: int = 5):
        piece_length = piece["length"]  # 当前所下载的 piece 的长度
        piece_index = piece["index"]  # 当前所下载的 piece 的索引

        # 把 piece 分成多个 block 来进行下载
        blocks = []
        block_count = math.ceil(piece_length / max_block_size)
        for i in range(block_count):
            offset = i * max_block_size
            block_size = max_block_size if i < block_count - 1 else (
                piece_length - max_block_size * (block_count - 1))
            blocks.append((offset, block_size))

        pending_count = 0  # 正在下载的 block 的队列长度
        downloaded_count = 0  # 已下载完成的 block 的数量
        piece_data = bytearray(piece_length)
        while downloaded_count < block_count:
            if self.unchoked:  # 等待 peer 发出 unchoked 信号
                while pending_count < max_pending_count and len(blocks) > 0:
                    pending_count += 1
                    offset, block_size = blocks.pop()
                    # 发出下载 block 的请求
                    self.send_request(piece_index, offset, block_size)

            # 处理返回的各种信号
            msg_id, msg_payload = self.receive_message()
            if msg_id == MSG_ID["unchoke"]:
                self.unchoked = True
                continue
            if msg_id == MSG_ID["choke"]:
                self.unchoked = False
                continue
            if msg_id == MSG_ID["have"]:
                new_piece_index = struct.unpack('>i', msg_payload)[0]
                self.bitfield.set_piece(new_piece_index)
                continue
            if msg_id == MSG_ID["piece"]:
                block_offset = struct.unpack(">i", msg_payload[4:8])[0]
                block_data = msg_payload[8:]
                piece_data[block_offset:block_offset +
                           len(block_data)] = block_data
                downloaded_count += 1
                pending_count -= 1
                continue

        # 校验数据正确性, 并返回索引和数据
        if hashlib.sha1(piece_data).digest() == piece["hash"]:
            return piece_data

    def connect(self):
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((self.ip, self.port))

        # 携带 torrent 信息和 peer 进行握手
        handshake_msg = (
            b"\x13"  # ProtocolLength: 1 bytes
            + "BitTorrent protocol".encode("utf-8")  # ProtocolName: 19 bytes
            + struct.pack('>q', 0)  # Reserved: 8 bytes
            + self.torrent["info_hash"].digest()  # InfoHash: 20 bytes
            + self.torrent["my_id"].encode("utf-8")  # PeerID: 20 bytes
        )
        conn.sendall(handshake_msg)

        # 获取 info_hash 来校验是否握手成功
        data = recv_full(conn, 1)  # 获取 1 bytes 的 ProtocolLength
        protocol_length = data[0]
        data = recv_full(conn, protocol_length + 48)
        info_hash = data[protocol_length + 8:protocol_length + 28]

        if info_hash == self.torrent["info_hash"].digest():
            self.conn = conn
            # 获取后续返回的 bitfield
            # bitfield 包含了该 peer 所拥有的 pieces
            msg_id, msg_payload = self.receive_message()
            if msg_id == MSG_ID["bitfield"]:
                self.bitfield = Bitfield(msg_payload)
            return conn
        raise Exception("The connection has wrong occurred.")

    def disconnect(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def receive_message(self):
        if self.conn is None:
            return None, None
        conn = self.conn

        data = recv_full(conn, 4)  # 获取 4 bytes 的 BTMessage 的 Length
        msg_length = struct.unpack(">I", data)[0]

        # 如果 msg_length = 0, 则说明是 keep alive 的消息
        if msg_length == 0:
            return MSG_ID["keep alive"], None

        data = recv_full(conn, msg_length)
        msg_id = data[0]  # 获取 1 bytes 的 BTMessage 的 ID

        # 如果是 msg_length = 1, 则说明消息不携带后续数据
        if msg_length == 1:
            return msg_id, None

        msg_payload = data[1:msg_length]  # 获取后续携带的数据
        return msg_id, msg_payload

    def send_message(self, msg_id: int, msg_payload: bytes = None):
        if self.conn is None:
            return

        # 如果发送的消息是 keep alive, 则只有 length 数据
        if msg_id == MSG_ID["keep alive"]:
            msg_length = struct.pack('>i', 0)
            self.conn.sendall(msg_length)
            return

        # 把 msg_id 编码成 bytes
        msg_id = struct.pack('>b', msg_id)
        # 错误转换: msg_id = str(msg_id).encode('utf-8')
        # 这样转换的结果是字符串 '1' 的 utf-8 二进制形式,
        # 而不是实际上想要的 0b00000001

        # 当发生的消息没有 msg_payload 时
        if msg_payload is None:
            msg_length = struct.pack('>i', 1)
            self.conn.sendall(msg_length + msg_id)
            return

        # 当发生的消息有 msg_payload 时
        msg_length = struct.pack('>i', 1 + len(msg_payload))
        self.conn.sendall(msg_length + msg_id + msg_payload)

    # 如果在一段时间内没有收到消息, 对方会断开连接,
    # 因此需要发送保持活动的信息来保持连接.
    # 一条保持活动的信息大概每两分钟发送一次.
    def send_keep_alive(self):
        self.send_message(MSG_ID["keep alive"])

    # 告诉对方不能请求任何数据, 先等待
    def send_choke(self):
        self.send_message(MSG_ID["choke"])

    # 告诉对方可以开始请求数据了
    def send_unchoke(self):
        self.send_message(MSG_ID["unchoke"])

    def send_interested(self):
        self.send_message(MSG_ID["interested"])

    def send_not_interested(self):
        self.send_message(MSG_ID["not interested"])

    # 告诉对方我有某个 Piece
    def send_have(self, piece_index: int):
        piece_index = struct.pack(">i", piece_index)
        self.send_message(MSG_ID["have"], piece_index)

    # 将我有的所有 Piece 编码成 Bitfield 发送给对方.
    # 在握手成功之后, 其他类型消息发送之前发送给对方.
    # 若文件没有分片, 则不发送该消息.
    def send_bitfield(self, bitmap: Union[str, int]):
        if type(bitmap) == int:
            bitmap = str(bitmap)

        msg_payload = b''
        for i in range(int(len(bitmap) / 8)):
            byte_bitmap = int(bitmap[i * 8:(i + 1) * 8], 2)
            byte_bitmap = str(byte_bitmap).encode('utf-8')
            msg_payload += byte_bitmap

        self.send_message(MSG_ID["bitfield"], msg_payload)

    # 向对方请求下载某个 Piece
    # 当我们使用 Request 下载时, 并不是一次请求一个完整的 Piece,
    # 而是分为 Block 下载, Block 的大小可以在消息体中指定, 一般为 16K.
    def send_request(self, piece_index: int, offset: int, block_size: int):
        piece_index = struct.pack(">i", piece_index)
        offset = struct.pack(">i", offset)
        block_size = struct.pack(">i", block_size)
        msg_payload = piece_index + offset + block_size
        self.send_message(MSG_ID["request"], msg_payload)

    # 发送 Piece 数据给到对方
    def send_piece(self, piece_index: int, offset: int, block: bytes):
        piece_index = struct.pack(">i", piece_index)
        offset = struct.pack(">i", offset)
        msg_payload = piece_index + offset + block
        self.send_message(MSG_ID["piece"], msg_payload)

    # 用于取消下载某个 Piece 的 Block
    def send_cancel(self, piece_index: int, offset: int, block_size: int):
        piece_index = struct.pack(">i", piece_index)
        offset = struct.pack(">i", offset)
        block_size = struct.pack(">i", block_size)
        msg_payload = piece_index + offset + block_size
        self.send_message(MSG_ID["cancel"], msg_payload)

    def send_port(self, listen_port: int):
        listen_port = struct.pack(">h", listen_port)
        self.send_message(MSG_ID["port"], listen_port)

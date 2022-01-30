import hashlib

from client.tracker import parse_torrent_file, fetch_peers_by_http, fetch_peers_by_udp
from client.peer import Peer
from utils.log import Printer


class Downloader:
    def __init__(self,
                 torrent_file_path: str,
                 saved_file_path: str = "./",
                 extra_trackers_path: str = None) -> None:
        self.torrent_file_path = torrent_file_path
        self.saved_file_path = saved_file_path
        self.extra_trackers_path = extra_trackers_path

        self.torrent = None
        self.unfinished_pieces = []
        self.peers = []
        self.result = []
        self.is_done = False

    # 解析 torrent
    def get_torrent(self):
        torrent_file_path = self.torrent_file_path

        Printer.inkjet('解析种子文件: %s' % torrent_file_path)
        torrent = parse_torrent_file(torrent_file_path)
        Printer.inkjet('解析成功.')
        Printer.inkjet(torrent, level=2, is_pprint=True)

        self.torrent = torrent

        # 存储未下载的所有 piece
        piece_count = torrent["piece"]["count"]
        piece_length = torrent["piece"]["length"]
        for i in range(piece_count):
            self.unfinished_pieces.append({
                "index":
                i,
                "hash":
                torrent["piece"]["hashes"][i],
                "length":
                piece_length if i < piece_count - 1 else torrent["length"] -
                piece_length * (piece_count - 1)
            })

    # 从 Tracker 中获取 Peer
    def fetch_peers(self):
        Printer.inkjet('向 Tracker 索取 Peer.')

        trackers = self.torrent["trackers"]
        extra_trackers_path = self.extra_trackers_path

        if extra_trackers_path is not None:
            with open(extra_trackers_path, 'r') as file:
                raw_trackers = file.read().split('\n')
                extra_trackers = [t for t in raw_trackers if t]
                trackers += extra_trackers

        for url in trackers:
            try:
                if url.startswith('http'):
                    self.peers += fetch_peers_by_http(url, self.torrent)
                if url.startswith('udp'):
                    self.peers += fetch_peers_by_udp(url, self.torrent)
            except Exception as e:
                Printer.inkjet(e, level=3)
                continue

        Printer.inkjet('索取结束.')
        Printer.inkjet(self.peers, level=2, is_pprint=True)

    # 按序创建并连接 Peer, 并让它们开始工作
    def start(self):
        if len(self.peers) == 0:
            Printer.inkjet('无 Peer 可以提供下载.')
            return

        for peer in self.peers:
            if self.is_done:
                return
            peer = Peer(peer["ip"], peer["port"], self.torrent)
            self.work(peer)

    # 连接 peer, 并分配 piece 让该 Peer 进行下载
    def work(self, peer: Peer, ttl: int = 200):
        Printer.inkjet('连接 Peer: %s:%s' % (peer.ip, peer.port))

        try:
            peer.connect()
        except:
            Printer.inkjet('连接失败.')
            return

        Printer.inkjet('连接成功.')

        peer.send_unchoke()
        peer.send_interested()

        while True:
            if len(self.unfinished_pieces) == 0:
                break

            piece = self.unfinished_pieces.pop()  # 取出某个 piece

            # 判断该 peer 是否拥有该 piece
            if peer.bitfield.has_piece(piece["index"]) is False:
                ttl -= 1
                self.unfinished_pieces.append(piece)
                if ttl < 0:
                    break
                continue

            Printer.inkjet('下载 [piece %s].' % piece["index"])

            # 让该 peer 下载这个 piece
            piece_data = peer.download_piece(piece)
            if piece_data is None:
                Printer.inkjet('下载 [piece %s] 失败.' % piece["index"])
                self.unfinished_pieces.append(piece)
                continue

            Printer.inkjet('下载 [piece %s] 成功.' % piece["index"])

            # 存储所下载的 piece 的结果
            self.result.append((piece["index"], piece_data))

            # 如果所有 piece 都被下载了, 则对这些 piece 进行组装
            if len(self.result) == self.torrent["piece"]["count"]:
                Printer.inkjet('下载完成.')
                self.is_done = True
                self.handle_result()

        peer.disconnect()

    # 组装 piece
    def handle_result(self):
        self.result.sort(key=lambda x: x[0])
        all_data = b''.join([piece_data for _, piece_data in self.result])

        # 根据 files 组装每个 file 的数据, 并分别进行保存
        finished_length = 0
        for file_info in self.torrent["files"]:
            file_length = file_info["length"]
            file_data = all_data[finished_length:finished_length + file_length]
            finished_length += file_length

            Printer.inkjet('保存文件: %s' % file_info["name"])
            if file_info.get("hash"):
                if hashlib.sha1(file_data).digest() == file_info["hash"]:
                    Printer.inkjet('文件哈希校验成功.')
                else:
                    Printer.inkjet('文件哈希校验失败.')

            saved_file_path = self.saved_file_path + file_info["name"]
            with open(saved_file_path, 'wb') as file:
                file.write(file_data)

            Printer.inkjet('保存成功.')

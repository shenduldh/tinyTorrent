from time import sleep
import requests
import hashlib
import struct
import socket

from utils.bencode import decode_bencode, encode_bencode
from utils.index import gen_random_id, gen_random_key

MY_PORT = 3000
TIMEOUT = 4


# 解析 .torrent 文件
def parse_torrent_file(file_path: str):
    with open(file_path, "rb") as file:
        data = file.read()

    decoded_data = decode_bencode(data)
    info = decoded_data["info"]
    pieces = info["pieces"]
    pieces_count = int(len(pieces) / 20)
    piece_hashes = []
    for i in range(pieces_count):
        piece_hashes.append(pieces[i * 20:(i + 1) * 20])

    raw_files = info.get('files')
    files = []
    if raw_files is None:
        total_length = info["length"]
        files.append({
            'hash': info["filehash"] if info.get("filehash") else None,
            'length': info["length"],
            'name': info["name"]
        })
    else:
        total_length = 0
        for file in raw_files:
            total_length += file["length"]
            files.append({
                'hash': file["filehash"] if file.get("filehash") else None,
                'length': file["length"],
                'name': file["path"][0]
            })

    trackers = [decoded_data["announce"]]
    if decoded_data.get("announce-list"):
        trackers += [x[0] for x in decoded_data["announce-list"]]

    return {
        "trackers": trackers,
        "files": files,
        "piece": {
            "length": info["piece length"],
            "count": pieces_count,
            "hashes": piece_hashes,
        },
        "length": total_length,
        "info_hash": hashlib.sha1(encode_bencode(info)),
        "my_id": gen_random_id(20),
    }


# 从 udp Tracker 中获取 Peer 的地址
def fetch_peers_by_udp(tracker_url, torrent):
    socket.setdefaulttimeout(TIMEOUT)

    conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    conn.bind(('127.0.0.1', MY_PORT))

    address = tracker_url[6:].split(":")
    ip = '127.0.0.1' if address[0] in ['0.0.0.0', 'localhost'] else address[0]
    port = int(address[1].split("/")[0])

    # 请求连接
    my_transaction_id = gen_random_id(4)
    connect_msg = (
        struct.pack('>q', int('41727101980', 16))  # connection_id
        + struct.pack('>i', 0)  # action
        + my_transaction_id.encode('utf-8')  # transaction_id
    )
    conn.sendto(connect_msg, (ip, port))
    data = conn.recv(16)

    # 校验返回数据
    action = struct.unpack('>i', data[0:4])
    transaction_id = data[4:8].decode('utf-8')
    if action != 0 and transaction_id != my_transaction_id:
        conn.close()
        raise Exception('The connection is wrong.')

    # 获取 peers
    announce_msg = (
        data[8:16]  # connection_id
        + struct.pack('>i', 1)  # action
        + my_transaction_id.encode('utf-8')  # transaction_id
        + torrent["info_hash"].digest()  # info_hash
        + torrent["my_id"].encode('utf-8')  # peer_id
        + struct.pack('>q', 0)  # downloaded
        + struct.pack('>q', torrent["length"])  # left
        + struct.pack('>q', 0)  # uploaded
        + struct.pack('>i', 0)  # event
        + struct.pack('>I', 0)  # ip
        + struct.pack('>I', gen_random_key(4))  # key
        + struct.pack('>i', -1)  # num_want
        + struct.pack('>H', MY_PORT)  # port
    )
    conn.sendto(announce_msg, (ip, port))
    sleep(0.01)  # 两次 conn.recv 之间阻塞一下
    data = conn.recv(1024)

    # 校验返回数据
    action = struct.unpack('>i', data[0:4])
    transaction_id = data[4:8].decode('utf-8')
    if action != 0 and transaction_id != my_transaction_id:
        conn.close()
        raise Exception('The connection is wrong.')

    # interval = struct.unpack('>i', data[8:12])
    # leechers = struct.unpack('>i', data[12:16])
    # seeders = struct.unpack('>i', data[16:20])

    raw_peers = data[20:]
    peers = []
    for i in range(int(len(raw_peers) / 6)):
        raw_peer = raw_peers[i * 6:(i + 1) * 6]
        ip = ".".join([str(raw_peer[i]) for i in range(4)])
        port = struct.unpack(">H", raw_peer[4:6])[0]
        peers.append({"ip": ip, "port": port})

    conn.close()
    return peers


# 从 http/https Tracker 中获取 Peer 的地址
def fetch_peers_by_http(tracker_url, torrent):
    info_hash = torrent["info_hash"].hexdigest()
    _info_hash = ""
    for i in range(int(len(info_hash) / 2)):
        _info_hash += "%" + info_hash[i * 2:(i + 1) * 2]

    query = {
        "info_hash": _info_hash,
        "peer_id": torrent["my_id"],
        "port": 3000,
        "uploaded": 0,
        "downloaded": 0,
        "compact": 1,
        "left": torrent["length"],
    }
    query_str = "&".join(["%s=%s" % (k, v) for k, v in query.items()])

    res = requests.get(tracker_url + "?" + query_str, timeout=TIMEOUT)
    decoded_res = decode_bencode(res.content)

    # interval = decoded_res["interval"]

    raw_peers = decoded_res["peers"]
    if type(raw_peers) == str:
        raw_peers = raw_peers.encode('utf-8')

    peers = []
    for i in range(int(len(raw_peers) / 6)):
        raw_peer = raw_peers[i * 6:(i + 1) * 6]
        ip = ".".join([str(raw_peer[i]) for i in range(4)])
        port = struct.unpack(">H", raw_peer[4:6])[0]
        peers.append({"ip": ip, "port": port})

    return peers

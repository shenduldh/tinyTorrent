import random
from socket import SocketType
from time import sleep


def gen_random_id(length: int = 20):
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    id = ""
    for _ in range(length):
        id += alphabet[random.randint(0, len(alphabet) - 1)]
    return id


def gen_random_key(length: int = 4):
    alphabet = "0123456789"
    key = ""
    for _ in range(length):
        key += alphabet[random.randint(0, len(alphabet) - 1)]
    return int(key)


def recv_full(conn: SocketType, data_length: int):
    left_length = data_length
    total_data = b''

    while left_length > 0:
        sleep(0.01)  # 两次 conn.recv 之间阻塞小小阻塞一下
        data = conn.recv(left_length)
        total_data += data
        left_length -= len(data)

    return total_data

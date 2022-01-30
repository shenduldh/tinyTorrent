from collections import deque
from typing import Tuple, Union


def to_binary(data: Union[str, bytes]):
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode("utf-8")
    raise TypeError("Expect a type of bytes or str.")


STRING_TYPE = [b"0", b"1", b"2", b"3", b"4", b"5", b"6", b"7", b"8", b"9"]
INT_TYPE = b"i"
LIST_TYPR = b"l"
DICT_TYPE = b"d"
END_CHAR = b"e"
COLON_CHAR = b":"

# =============== Decoder ===============


def decode_int(data: bytes, start: int) -> Tuple[int, int]:
    # i[int]e
    start += 1
    end = data.index(END_CHAR, start)
    int_data = int(data[start:end])
    return int_data, end + 1


def decode_str(data: bytes, start: int) -> Tuple[Union[str, bytes], int]:
    # [length]:[string]
    colon = data.index(COLON_CHAR, start)
    str_length = int(data[start:colon])
    colon += 1
    end = colon + str_length
    bytes_data = data[colon:end]
    try:
        str_data = bytes_data.decode("utf-8")
        return str_data, end
    except:
        return bytes_data, end


def decode_list(data: bytes, start: int) -> Tuple[list, int]:
    # l[list]e
    start += 1
    result = []
    while data[start:start + 1] != END_CHAR:
        symbol = data[start:start + 1]
        item, start = decode_func(symbol)(data, start)
        result.append(item)
    return result, start + 1


def decode_dict(data: bytes, start: int) -> Tuple[dict, int]:
    # d[dict]e
    start += 1
    result = {}
    while data[start:start + 1] != END_CHAR:
        key, start = decode_str(data, start)
        symbol = data[start:start + 1]
        result[key], start = decode_func(symbol)(data, start)
    return result, start + 1


def decode_func(symbol):
    if symbol in STRING_TYPE:
        return decode_str
    if symbol == INT_TYPE:
        return decode_int
    if symbol == LIST_TYPR:
        return decode_list
    if symbol == DICT_TYPE:
        return decode_dict
    raise


def decode_bencode(data: Union[str, bytes]) -> Union[int, str, list, dict]:
    try:
        binary_data = to_binary(data)
        symbol = binary_data[0:1]
        decoded_data, decoded_length = decode_func(symbol)(binary_data, 0)
        if decoded_length != len(binary_data):
            raise
        return decoded_data
    except:
        raise Exception("Not a valid bencode data.")


# =============== Encoder ===============


def encode_int(data: int, result: deque):
    result.extend((INT_TYPE, str(data).encode("utf-8"), END_CHAR))


def encode_bytes(data: bytes, result: deque):
    result.extend((str(len(data)).encode("utf-8"), COLON_CHAR, data))


def encode_str(data: str, result: deque):
    encode_bytes(data.encode("utf-8"), result)


def encode_list(data: list, result: deque):
    result.append(LIST_TYPR)
    for item in data:
        item_type = type(item)
        encode_func(item_type)(item, result)
    result.append(END_CHAR)


def encode_dict(data: dict, result: deque):
    result.append(DICT_TYPE)
    for key, value in data.items():
        key_type = type(key)
        encode_func(key_type)(key, result)
        value_type = type(value)
        encode_func(value_type)(value, result)
    result.append(END_CHAR)


def encode_func(data_type):
    if data_type == int:
        return encode_int
    if data_type == bytes:
        return encode_bytes
    if data_type == str:
        return encode_str
    if data_type == list:
        return encode_list
    if data_type == dict:
        return encode_dict
    raise Exception("The Type of the data is not supported.")


def encode_bencode(data: Union[int, bytes, str, list, dict]):
    result = deque()
    data_type = type(data)
    encode_func(data_type)(data, result)
    return b"".join(result)

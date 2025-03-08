from math import ceil
import base64
import io
import traceback


def byte(n):
    return bytes((n,))


def varint_encode(offset):
    '''In this encoding system, for each 8-bit byte, the first bit is 1 if there are more bytes, and 0 is this is the last one.
    The next 7 bits are data. These 7-bit sections represent the data in Little endian order. For example, suppose the data is
    aaaaaaabbbbbbbccccccc (each of these sections is 7 bits). It will be encoded as:
    1ccccccc 1bbbbbbb 0aaaaaaa

    This encoding is used in youtube parameters to encode offsets and to encode the length for length-prefixed data.
    See https://developers.google.com/protocol-buffers/docs/encoding#varints for more info.'''
    needed_bytes = ceil(offset.bit_length()/7) or 1 # (0).bit_length() returns 0, but we need 1 in that case.
    encoded_bytes = bytearray(needed_bytes)
    for i in range(0, needed_bytes - 1):
        encoded_bytes[i] = (offset & 127) | 128  # 7 least significant bits
        offset = offset >> 7
    encoded_bytes[-1] = offset & 127  # leave first bit as zero for last byte

    return bytes(encoded_bytes)


def varint_decode(encoded):
    decoded = 0
    for i, byte in enumerate(encoded):
        decoded |= (byte & 127) << 7*i

        if not (byte & 128):
            break
    return decoded


def string(field_number, data):
    data = as_bytes(data)
    return _proto_field(2, field_number, varint_encode(len(data)) + data)


nested = string


def uint(field_number, value):
    return _proto_field(0, field_number, varint_encode(value))


def _proto_field(wire_type, field_number, data):
    ''' See https://developers.google.com/protocol-buffers/docs/encoding#structure '''
    return varint_encode((field_number << 3) | wire_type) + data


def percent_b64encode(data):
    return base64.urlsafe_b64encode(data).replace(b'=', b'%3D')


def unpadded_b64encode(data):
    return base64.urlsafe_b64encode(data).replace(b'=', b'')


def as_bytes(value):
    if isinstance(value, str):
        return value.encode('utf-8')
    return value


def read_varint(data):
    result = 0
    i = 0
    while True:
        try:
            byte = data.read(1)[0]
        except IndexError:
            if i == 0:
                raise EOFError()
            raise Exception('Unterminated varint starting at ' + str(data.tell() - i))
        result |= (byte & 127) << 7*i
        if not byte & 128:
            break

        i += 1
    return result


def read_group(data, end_sequence):
    start = data.tell()
    index = data.original.find(end_sequence, start)
    if index == -1:
        raise Exception('Unterminated group')
    data.seek(index + len(end_sequence))
    return data.original[start:index]

def read_protobuf(data):
    data_original = data
    data = io.BytesIO(data)
    data.original = data_original
    while True:
        try:
            tag = read_varint(data)
        except EOFError:
            break
        wire_type = tag & 7
        field_number = tag >> 3

        if wire_type == 0:
            value = read_varint(data)
        elif wire_type == 1:
            value = data.read(8)
        elif wire_type == 2:
            length = read_varint(data)
            value = data.read(length)
        elif wire_type == 3:
            end_bytes = encode_varint((field_number << 3) | 4)
            value = read_group(data, end_bytes)
        elif wire_type == 5:
            value = data.read(4)
        else:
            raise Exception("Unknown wire type: " + str(wire_type) + ", Tag: " + bytes_to_hex(succinct_encode(tag)) + ", at position " + str(data.tell()))
        yield (wire_type, field_number, value)


def parse(data, include_wire_type=False):
    '''Returns a dict mapping field numbers to values

    data is the protobuf structure, which must not be b64-encoded'''
    if include_wire_type:
        return {field_number: [wire_type, value]
                for wire_type, field_number, value in read_protobuf(data)}
    return {field_number: value
            for _, field_number, value in read_protobuf(data)}


base64_enc_funcs = {
    'base64': base64.urlsafe_b64encode,
    'base64s': unpadded_b64encode,
    'base64p': percent_b64encode,
}


def _make_protobuf(data):
    '''
    Input: Recursive list of protobuf objects or base-64 encodings
    Output: Protobuf bytestring
    Each protobuf object takes the form [wire_type, field_number, field_data]
    If a string protobuf has a list/tuple of length 2, this has the form
    (base64 type, data)
    The base64 types are
    - base64 means a base64 encode with equals sign paddings
    - base64s means a base64 encode without padding
    - base64p means a url base64 encode with equals signs replaced with %3D
    '''
    # must be dict mapping field_number to [wire_type, value]
    if isinstance(data, dict):
        new_data = []
        for field_num, (wire_type, value) in sorted(data.items()):
            new_data.append((wire_type, field_num, value))
        data = new_data
    if isinstance(data, str):
        return data.encode('utf-8')
    elif len(data) == 2 and data[0] in list(base64_enc_funcs.keys()):
        return base64_enc_funcs[data[0]](_make_protobuf(data[1]))
    elif isinstance(data, list):
        result = b''
        for field in data:
            if field[0] == 0:
                result += uint(field[1], field[2])
            elif field[0] == 2:
                result += string(field[1], _make_protobuf(field[2]))
            else:
                raise NotImplementedError('Wire type ' + str(field[0])
                    + ' not implemented')
        return result
    return data


def make_protobuf(data):
    return _make_protobuf(data).decode('ascii')


def _set_protobuf_value(data, *path, value):
    if not path:
        return value
    op = path[0]
    if op in base64_enc_funcs:
        inner_data = b64_to_bytes(data)
        return base64_enc_funcs[op](
            _set_protobuf_value(inner_data, *path[1:], value=value)
        )
    pb_dict = parse(data, include_wire_type=True)
    pb_dict[op][1] = _set_protobuf_value(
        pb_dict[op][1], *path[1:], value=value
    )
    return _make_protobuf(pb_dict)


def set_protobuf_value(data, *path, value):
    '''Set a field's value in a raw protobuf structure

    path is a list of field numbers and/or base64 encoding directives

    The directives are
        base64: normal base64 encoding with equal signs padding
        base64s ("stripped"): no padding
        base64p: %3D instead of = for padding

    return new_protobuf, err'''
    try:
        new_protobuf = _set_protobuf_value(data, *path, value=value)
        return new_protobuf.decode('ascii'), None
    except Exception:
        return None, traceback.format_exc()


def b64_to_bytes(data):
    if isinstance(data, bytes):
        data = data.decode('ascii')
    data = data.replace("%3D", "=")
    return base64.urlsafe_b64decode(data + "="*((4 - len(data) % 4) % 4))

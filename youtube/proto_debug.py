# TODO: clean this file up more and heavily refactor

''' Helper functions for reverse engineering protobuf.

Basic guide:

Run interactively with python3 -i proto_debug.py

The function dec will decode a base64 string
(regardless of whether it includes = or %3D at the end) to a bytestring

The function pb (parse_protobuf) will return a list of tuples.
Each tuple is (wire_type, field_number, field_data)

The function enc encodes as base64 (inverse of dec)
The function uenc is like enc but replaces = with %3D

See https://developers.google.com/protocol-buffers/docs/encoding#structure

Example usage:
>>> pb(dec('4qmFsgJcEhhVQ1lPX2phYl9lc3VGUlY0YjE3QUp0QXcaQEVnWjJhV1JsYjNNWUF5QUFNQUU0QWVvREdFTm5Ua1JSVlVWVFEzZHBYM2gwTTBaeFRuRkZiRFZqUWclM0QlM0Q%3D'))
[(2, 80226972, b'\x12\x18UCYO_jab_esuFRV4b17AJtAw\x1a@EgZ2aWRlb3MYAyAAMAE4AeoDGENnTkRRVUVTQ3dpX3h0M0ZxTnFFbDVjQg%3D%3D')]

>>> pb(b'\x12\x18UCYO_jab_esuFRV4b17AJtAw\x1a@EgZ2aWRlb3MYAyAAMAE4AeoDGENnTkRRVUVTQ3dpX3h0M0ZxTnFFbDVjQg%3D%3D')
[(2, 2, b'UCYO_jab_esuFRV4b17AJtAw'), (2, 3, b'EgZ2aWRlb3MYAyAAMAE4AeoDGENnTkRRVUVTQ3dpX3h0M0ZxTnFFbDVjQg%3D%3D')]

>>> pb(dec(b'EgZ2aWRlb3MYAyAAMAE4AeoDGENnTkRRVUVTQ3dpX3h0M0ZxTnFFbDVjQg%3D%3D'))
[(2, 2, b'videos'), (0, 3, 3), (0, 4, 0), (0, 6, 1), (0, 7, 1), (2, 61, b'CgNDQUESCwi_xt3FqNqEl5cB')]

>>> pb(dec(b'CgNDQUESCwi_xt3FqNqEl5cB'))
[(2, 1, b'CAA'), (2, 2, b'\x08\xbf\xc6\xdd\xc5\xa8\xda\x84\x97\x97\x01')]

>>> pb(b'\x08\xbf\xc6\xdd\xc5\xa8\xda\x84\x97\x97\x01')
[(0, 1, 10893665244101960511)]

>>> pb(dec(b'CAA'))
[(0, 1, 0)]

The function recursive_pb will try to do dec/pb recursively automatically.
It's a dumb function (so might try to dec or pb something that isn't really
base64 or protobuf) so be careful.
The function pp will pretty print the recursive structure:

>>> pp(recursive_pb('4qmFsgJcEhhVQ1lPX2phYl9lc3VGUlY0YjE3QUp0QXcaQEVnWjJhV1JsYjNNWUF5QUFNQUU0QWVvREdFTm5Ua1JSVlVWVFEzZHBYM2gwTTBaeFRuRkZiRFZqUWclM0QlM0Q%3D'))

('base64p',
 [
  [2, 80226972,
   [
    [2, 2, b'UCYO_jab_esuFRV4b17AJtAw'],
    [2, 3,
     ('base64p',
      [
       [2, 2, b'videos'],
       [0, 3, 3],
       [0, 4, 0],
       [0, 6, 1],
       [0, 7, 1],
       [2, 61,
        ('base64?',
         [
          [2, 1, b'CAA'],
          [2, 2,
           [
            [0, 1, 10893665244101960511],
           ]
          ],
         ]
        )
       ],
      ]
     )
    ],
   ]
  ],
 ]
)


- base64 means a base64 encode with equals sign paddings
- base64s means a base64 encode without padding
- base64p means a url base64 encode with equals signs replaced with %3D
- base64? means the base64 type cannot be inferred because of the length

make_proto is the inverse function. It will take a recursive_pb structure and
make a ctoken out of it, so in general,
x == make_proto(recursive_pb(x))

There are some other functions I wrote while reverse engineering stuff
that may or may not be useful.
'''


import urllib.request
import urllib.parse
import re
import time
import json
import os
import pprint


# ------ from proto.py -----------------------------------------------
from math import ceil
import base64
import io

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
    encoded_bytes[-1] = offset & 127 # leave first bit as zero for last byte

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
    return varint_encode( (field_number << 3) | wire_type) + data


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
    'base64?': base64.urlsafe_b64encode,
}
def _make_protobuf(data):
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
make_proto = make_protobuf


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
    return base64.urlsafe_b64decode(data + "="*((4 - len(data)%4)%4) )
# --------------------------------------------------------------------


dec = b64_to_bytes


def get_b64_type(data):
    '''return base64, base64s, base64p, or base64?'''
    if isinstance(data, str):
        data = data.encode('ascii')
    if data.endswith(b'='):
        return 'base64'
    if data.endswith(b'%3D'):
        return 'base64p'
    # Length of data means it wouldn't have an equals sign,
    # so we can't tell which type it is.
    if len(data) % 4 == 0:
        return 'base64?'

    return 'base64s'


def enc(t):
    return base64.urlsafe_b64encode(t).decode('ascii')

def uenc(t):
    return enc(t).replace("=", "%3D")

def b64_to_ascii(t):
    return base64.urlsafe_b64decode(t).decode('ascii', errors='replace')

def b64_to_bin(t):
    decoded = base64.urlsafe_b64decode(t)
    #print(len(decoded)*8)
    return " ".join(["{:08b}".format(x) for x in decoded])

def bytes_to_bin(t):
    return " ".join(["{:08b}".format(x) for x in t])
def bin_to_bytes(t):
    return int(t, 2).to_bytes((len(t) + 7) // 8, 'big')

def bytes_to_hex(t):
    return ' '.join(hex(n)[2:].zfill(2) for n in t)
tohex = bytes_to_hex
fromhex = bytes.fromhex


def aligned_ascii(data):
    return ' '.join(' ' + chr(n) if n in range(32,128) else ' _' for n in data)

def parse_protobuf(data, mutable=False, spec=()):
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
            end_bytes = varint_encode((field_number << 3) | 4)
            value = read_group(data, end_bytes)
        elif wire_type == 5:
            value = data.read(4)
        else:
            raise Exception("Unknown wire type: " + str(wire_type) + ", Tag: " + bytes_to_hex(varint_encode(tag)) + ", at position " + str(data.tell()))
        if mutable:
            yield [wire_type, field_number, value]
        else:
            yield (wire_type, field_number, value)
read_protobuf = parse_protobuf


def pb(data, mutable=False):
    return list(parse_protobuf(data, mutable=mutable))


def bytes_to_base4(data):
    result = ''
    for b in data:
        result += str(b >> 6) + str((b >> 4) & 0b11) + str((b >> 2) & 0b11) + str(b & 0b11)
    return result


import re
import struct
import binascii


# Base32 encoding/decoding must be done in Python
_b32alphabet = b'abcdefghijklmnopqrstuvwxyz012345'
_b32tab2 = None
_b32rev = None

bytes_types = (bytes, bytearray)  # Types acceptable as binary data

def _bytes_from_decode_data(s):
    if isinstance(s, str):
        try:
            return s.encode('ascii')
        except UnicodeEncodeError:
            raise ValueError('string argument should contain only ASCII characters')
    if isinstance(s, bytes_types):
        return s
    try:
        return memoryview(s).tobytes()
    except TypeError:
        raise TypeError("argument should be a bytes-like object or ASCII "
                        "string, not %r" % s.__class__.__name__) from None



def b32decode(s, casefold=False, map01=None):
    """Decode the Base32 encoded bytes-like object or ASCII string s.

    Optional casefold is a flag specifying whether a lowercase alphabet is
    acceptable as input.  For security purposes, the default is False.

    RFC 3548 allows for optional mapping of the digit 0 (zero) to the
    letter O (oh), and for optional mapping of the digit 1 (one) to
    either the letter I (eye) or letter L (el).  The optional argument
    map01 when not None, specifies which letter the digit 1 should be
    mapped to (when map01 is not None, the digit 0 is always mapped to
    the letter O).  For security purposes the default is None, so that
    0 and 1 are not allowed in the input.

    The result is returned as a bytes object.  A binascii.Error is raised if
    the input is incorrectly padded or if there are non-alphabet
    characters present in the input.
    """
    global _b32rev
    # Delay the initialization of the table to not waste memory
    # if the function is never called
    if _b32rev is None:
        _b32rev = {v: k for k, v in enumerate(_b32alphabet)}
    s = _bytes_from_decode_data(s)
    if len(s) % 8:
        raise binascii.Error('Incorrect padding')
    # Handle section 2.4 zero and one mapping.  The flag map01 will be either
    # False, or the character to map the digit 1 (one) to.  It should be
    # either L (el) or I (eye).
    if map01 is not None:
        map01 = _bytes_from_decode_data(map01)
        assert len(map01) == 1, repr(map01)
        s = s.translate(bytes.maketrans(b'01', b'O' + map01))
    if casefold:
        s = s.upper()
    # Strip off pad characters from the right.  We need to count the pad
    # characters because this will tell us how many null bytes to remove from
    # the end of the decoded string.
    l = len(s)
    s = s.rstrip(b'=')
    padchars = l - len(s)
    # Now decode the full quanta
    decoded = bytearray()
    b32rev = _b32rev
    for i in range(0, len(s), 8):
        quanta = s[i: i + 8]
        acc = 0
        try:
            for c in quanta:
                acc = (acc << 5) + b32rev[c]
        except KeyError:
            raise binascii.Error('Non-base32 digit found') from None
        decoded += acc.to_bytes(5, 'big')
    # Process the last, partial quanta
    if padchars:
        acc <<= 5 * padchars
        last = acc.to_bytes(5, 'big')
        if padchars == 1:
            decoded[-5:] = last[:-1]
        elif padchars == 3:
            decoded[-5:] = last[:-2]
        elif padchars == 4:
            decoded[-5:] = last[:-3]
        elif padchars == 6:
            decoded[-5:] = last[:-4]
        else:
            raise binascii.Error('Incorrect padding')
    return bytes(decoded)

def dec32(data):
    if isinstance(data, bytes):
        data = data.decode('ascii')
    return b32decode(data + "="*((8 - len(data)%8)%8))


_patterns = [
    (b'UC', 24), # channel
    (b'PL', 34), # playlist
    (b'LL', 24), # liked videos playlist
    (b'UU', 24), # user uploads playlist
    (b'RD', 15), # radio mix
    (b'RD', 43), # radio mix
    (b'', 11),   # video
    (b'Ug', 26), # comment
    (b'Ug', 49), # comment reply (of form parent_id.reply_id)
    (b'9', 22), # comment reply id
]
def is_youtube_object_id(data):
    try:
        if isinstance(data, str):
            data = data.encode('ascii')
    except Exception:
        return False

    for start_sequence, length in _patterns:
        if len(data) == length and data.startswith(start_sequence):
            return True

    return False


def recursive_pb(data):
    try:
        # check if this fits the basic requirements for base64
        if isinstance(data, str) or all(i > 32 for i in data):
            if len(data) > 11 and not is_youtube_object_id(data):
                raw_data = b64_to_bytes(data)
                b64_type = get_b64_type(data)

                rpb = recursive_pb(raw_data)
                if rpb == raw_data:
                    # could not interpret as protobuf, probably not b64
                    return data
                return (b64_type, rpb)
            else:
                return data
    except Exception as e:
        return data

    try:
        result = pb(data, mutable=True) 
    except Exception as e:
        return data

    for tuple in result:
        if tuple[0] == 2:
            tuple[2] = recursive_pb(tuple[2])

    return result



def indent_lines(lines, indent):
    return re.sub(r'^', ' '*indent, lines, flags=re.MULTILINE)

def _pp(obj, indent):   # not my best work
    if isinstance(obj, tuple):
        if len(obj) == 3:   # (wire_type, field_number, data)
            return obj.__repr__()
        else:   # (base64, [...])
            return ('(' + obj[0].__repr__() + ',\n'
                    + indent_lines(_pp(obj[1], indent), indent) + '\n'
                    + ')')
    elif isinstance(obj, list):
        # [wire_type, field_number, data]
        if (len(obj) == 3
            and not any(isinstance(x, (list, tuple)) for x in obj)
        ):
            return obj.__repr__()

        # [wire_type, field_number, [...]]
        elif (len(obj) == 3
            and not any(isinstance(x, (list, tuple)) for x in obj[0:2])
        ):
            return ('[' + obj[0].__repr__() + ', ' + obj[1].__repr__() + ',\n'
                    + indent_lines(_pp(obj[2], indent), indent) + '\n'
                    + ']')
        else:
            s = '[\n'
            for x in obj:
                s += indent_lines(_pp(x, indent), indent) + ',\n'
            s += ']'
            return s
    else:
        return obj.__repr__()

def pp(obj, indent=1):
    '''Pretty prints the recursive pb structure'''
    print(_pp(obj, indent))


desktop_user_agent = 'Mozilla/5.0 (Windows NT 6.1; rv:52.0) Gecko/20100101 Firefox/52.0'
desktop_headers = (
    ('Accept', '*/*'),
    ('Accept-Language', 'en-US,en;q=0.5'),
    ('X-YouTube-Client-Name', '1'),
    ('X-YouTube-Client-Version', '2.20180830'),
) + (('User-Agent', desktop_user_agent),)

mobile_user_agent = 'Mozilla/5.0 (Linux; Android 7.0; Redmi Note 4 Build/NRD90M) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Mobile Safari/537.36'
mobile_headers = (
    ('Accept', '*/*'),
    ('Accept-Language', 'en-US,en;q=0.5'),
    ('X-YouTube-Client-Name', '2'),
    ('X-YouTube-Client-Version', '2.20180830'),
) + (('User-Agent', mobile_user_agent),)



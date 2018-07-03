from math import ceil
import base64

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
        return value.encode('ascii')
    return value
    
    
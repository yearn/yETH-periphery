# @version 0.3.7
"""
@title Executor
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
"""

interface Proxy:
    def execute(_to: address, _data: Bytes[65536]): nonpayable

enum Access:
    WHITELIST
    BLACKLIST

management: public(address)
proxy: public(address)
governors: public(HashMap[address, bool])
access: public(HashMap[uint256, Access]) # target => access control setting
whitelisted: public(HashMap[uint256, HashMap[address, bool]]) # target => governor => whitelisted
blacklisted: public(HashMap[uint256, HashMap[address, bool]]) # target => governor => blacklisted

event Execute:
    by: indexed(address)
    contract: indexed(address)
    identifier: indexed(bytes4)
    size: uint256

event SetGovernor:
    by: indexed(address)
    governor: indexed(address)
    flag: bool

event SetAccess:
    by: indexed(address)
    contract: indexed(address)
    identifier: indexed(bytes4)
    access: Access

TARGET_MASK: public(constant(uint256)) = shift(1, 192) - 1
IDENTIFIER_MASK: constant(uint256) = shift(1, 32) - 1

@external
def __init__(_proxy: address):
    self.management = msg.sender
    self.proxy = _proxy
    self.governors[msg.sender] = True

@external
def execute_single(_to: address, _data: Bytes[2048]):
    assert self.governors[msg.sender]
    assert len(_data) >= 4
    identifier: bytes4 = convert(slice(_data, 0, 4), bytes4)
    target: uint256 = self._pack_target(_to, identifier)

    # check access control
    access: Access = self.access[target]
    if access == Access.BLACKLIST:
        assert not self.blacklisted[target][msg.sender]
    elif access == Access.WHITELIST:
        assert self.whitelisted[target][msg.sender]

    Proxy(self.proxy).execute(_to, _data)
    log Execute(msg.sender, _to, identifier, len(_data))

@external
def execute(_script: Bytes[65536]):
    assert self.governors[msg.sender]

    i: uint256 = 0
    for x in range(32):
        if i == len(_script):
            break
        assert i + 32 <= len(_script)
    
        # extract target and calldata size
        target: uint256 = extract32(_script, i, output_type=uint256) # calldata size (64) | address (160) | identifier (32)
        size: uint256 = shift(target, -192)
        target &= TARGET_MASK
        i += 28 # calldata field (8 bytes) + address (20 bytes)
        assert i + size <= len(_script)
        assert size >= 4 and size <= 2048

        # check access control
        access: Access = self.access[target]
        if access == Access.BLACKLIST:
            assert not self.blacklisted[target][msg.sender]
        elif access == Access.WHITELIST:
            assert self.whitelisted[target][msg.sender]

        contract: address = empty(address)
        identifier: bytes4 = empty(bytes4)
        contract, identifier = self._unpack_target(target)
        calldata: Bytes[65536] = slice(_script, i, size)

        i += size
        assert i <= len(_script)

        Proxy(self.proxy).execute(contract, calldata)
        log Execute(msg.sender, contract, identifier, size)

    assert i == len(_script)

@external
def set_proxy(_proxy: address):
    assert msg.sender == self.management
    assert _proxy != empty(address)
    self.proxy = _proxy

@external
def set_governor(_governor: address, _flag: bool):
    assert msg.sender == self.management
    self.governors[_governor] = _flag
    log SetGovernor(msg.sender, _governor, _flag)

@external
def set_access(_contract: address, _identifier: bytes4, _access: Access):
    assert msg.sender == self.management
    target: uint256 = self._pack_target(_contract, _identifier)
    self.access[target] = _access
    log SetAccess(msg.sender, _contract, _identifier, _access)

@external
def set_whitelist(_contract: address, _identifier: bytes4, _caller: address, _whitelisted: bool):
    assert msg.sender == self.management
    target: uint256 = self._pack_target(_contract, _identifier)
    self.whitelisted[target][_caller] = _whitelisted

@external
def set_blacklist(_contract: address, _identifier: bytes4, _caller: address, _blacklisted: bool):
    assert msg.sender == self.management
    target: uint256 = self._pack_target(_contract, _identifier)
    self.blacklisted[target][_caller] = _blacklisted

@internal
@pure
def _pack_target(_contract: address, _identifier: bytes4) -> uint256:
    return shift(convert(_contract, uint256), 32) | convert(_identifier, uint256)

@internal
@pure
def _unpack_target(_target: uint256) -> (address, bytes4):
    return convert(shift(_target, -32), address), convert(convert(_target & IDENTIFIER_MASK, uint32), bytes4)

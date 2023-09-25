# @version 0.3.7
"""
@title Ownership proxy
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
"""

management: public(address)

event SetManagement:
    management: indexed(address)

@external
def __init__():
    """
    @notice Constructor
    """
    self.management = msg.sender

@external
def execute(_to: address, _data: Bytes[2048]):
    assert msg.sender == self.management
    raw_call(_to, _data)

@external
def set_management(_management: address):
    """
    @notice Set the new management address
    @param _management New management address
    """
    assert msg.sender == self
    self.management = _management
    log SetManagement(_management)

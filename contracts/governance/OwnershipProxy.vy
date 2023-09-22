# @version 0.3.7
"""
@title Ownership proxy
@author 0xkorin, Yearn Finance
@license GNU AGPLv3
"""

management: public(address)
pending_management: public(address)

event PendingManagement:
    management: indexed(address)

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
    @notice 
        Set the pending management address.
        Needs to be accepted by that account separately to transfer management over
    @param _management New pending management address
    """
    assert msg.sender == self
    self.pending_management = _management
    log PendingManagement(_management)

@external
def accept_management():
    """
    @notice 
        Accept management role.
        Can only be called by account previously marked as pending management by current management
    """
    assert msg.sender == self.pending_management
    self.pending_management = empty(address)
    self.management = msg.sender
    log SetManagement(msg.sender)

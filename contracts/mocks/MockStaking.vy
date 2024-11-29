# @version 0.3.10

from vyper.interfaces import ERC20

asset: public(immutable(address))
totalSupply: public(uint256)
balanceOf: public(HashMap[address, uint256])

@external
def __init__(_asset: address):
    asset = _asset

@external
def deposit(_assets: uint256, _receiver: address = msg.sender) -> uint256:
    # mint 1:1
    self.totalSupply += _assets
    self.balanceOf[_receiver] += _assets
    assert ERC20(asset).transferFrom(msg.sender, self, _assets, default_return_value=True)
    return _assets

@external
def withdraw(_assets: uint256, _receiver: address = msg.sender) -> uint256:
    # burn 1:1
    self.totalSupply -= _assets
    self.balanceOf[msg.sender] -= _assets
    assert ERC20(asset).transfer(_receiver, _assets, default_return_value=True)
    return _assets

@external
def transfer(_receiver: address, _amount: uint256) -> bool:
    self.balanceOf[msg.sender] -= _amount
    self.balanceOf[_receiver] += _amount
    return True

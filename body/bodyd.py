#!/usr/bin/env python3
import struct
import time
import cereal.messaging as messaging

from openpilot.common.params import Params
from openpilot.common.realtime import config_realtime_process
from openpilot.selfdrive.pandad.pandad_api_impl import can_list_to_can_capnp, can_capnp_to_list
from opendbc.car.isotp import isotp_build_send, isotp_build_recv, isotp_reassemble_recv

from selfdrive.car.card import can_comm_callbacks

ISOTP_TX_ADDR = 1
ISOTP_RX_ADDR = 2
BUS = 0
BODY_BASE_ADDR = 0x250
USB_REQUEST_IN = 0xC0  # usb1.ENDPOINT_IN | usb1.TYPE_VENDOR | usb1.RECIPIENT_DEVICE
USB_REQUEST_OUT = 0x40  # usb1.ENDPOINT_OUT | usb1.TYPE_VENDOR | usb1.RECIPIENT_DEVICE
ENTER_BOOTLOADER = b"\xce\xfa\xad\xde\x1e\x0b\xb0\x0a"


def controlRead(request_type, request, value, index, length):
  dat = struct.pack("HHBBHHH", 0, 0, request_type, request, value, index, length)
  return isotp_build_send(dat, ISOTP_TX_ADDR, BUS)


def controlWrite(request_type, request, value, index, data):
  dat = struct.pack("HHBBHHH", 0, 0, request_type, request, value, index, len(data)) + data
  return isotp_build_send(dat, ISOTP_TX_ADDR, BUS)


class Bodyd:
  def __init__(self):
    self.params = Params()
    self.fw_version: bytes | None = None
    self._rx_buf: bytes = b""
    self._rx_tlen: int = 0
    self._rx_remaining: int = 0
    self._rx_msgs: list = []

  def update(self, sm: messaging.SubMaster, can_msgs: list):
    for _, frames in can_msgs:
      for addr, data, src in frames:
        if addr != ISOTP_RX_ADDR:
          continue

        if self._rx_remaining > 0:
          self._rx_msgs.append(data)
          self._rx_remaining -= 1
          if self._rx_remaining == 0:
            self.fw_version = isotp_reassemble_recv(self._rx_buf, self._rx_msgs, self._rx_tlen)
        else:
          dat, tlen, n_remaining = isotp_build_recv(data)
          if n_remaining == 0:
            self.fw_version = dat
          else:
            self._rx_buf = dat
            self._rx_tlen = tlen
            self._rx_remaining = n_remaining
            self._rx_msgs = []

  def get_fw_request(self) -> list[tuple]:
    return controlRead(USB_REQUEST_IN, 0xd6, 0, 0, 0x40)


def send_frames(pm, frames):
  pm.send('bodycan', can_list_to_can_capnp(frames, msgtype='bodycan'))


def recv_isotp(can_sock, sm, bodyd):
  while bodyd.fw_version is None:
    can_strings = messaging.drain_sock_raw(can_sock)
    if can_strings:
      can_msgs = can_capnp_to_list(can_strings)
      bodyd.update(sm, can_msgs)


def main():

  sm = messaging.SubMaster(['deviceState'])
  pm = messaging.PubMaster(['bodycan'])
  can_sock = messaging.sub_sock('can', timeout=20)

  bodyd = Bodyd()

  print("Entering bootloader...")
  send_frames(pm, [(BODY_BASE_ADDR, ENTER_BOOTLOADER, BUS)])
  time.sleep(1)

  print("Requesting firmware version...")
  send_frames(pm, bodyd.get_fw_request())

  print("Waiting for firmware version response...")
  recv_isotp(can_sock, sm, bodyd)
  print(f"Body firmware version: {bodyd.fw_version.hex()}")

  print("Resetting back to application...")
  send_frames(pm, controlWrite(USB_REQUEST_OUT, 0xd8, 0, 0, b""))


if __name__ == "__main__":
  main()

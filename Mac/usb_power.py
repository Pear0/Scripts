#!/usr/bin/env python3
import json
import os
import sys

import usb.control
import usb.core
from usb.util import *

CLEAR_FEATURE = 1
SET_FEATURE = 3

FEATURE_POWER = 8

SAVE_FILE = '/tmp/saved-unpowered-usb-devices.json'

devices_to_power_down = [
    # (vid, pid)
    (0x04d9, 0x0355),  # keyboard
    (0x046d, 0xc092),  # mouse
]


def set_port_powered(hub, port_number, powered):
    req = SET_FEATURE if powered else CLEAR_FEATURE
    hub.ctrl_transfer(CTRL_OUT | CTRL_TYPE_CLASS | CTRL_RECIPIENT_OTHER, req, wValue=FEATURE_POWER, wIndex=port_number)


def power_up():
    if not os.path.exists(SAVE_FILE):
        return

    with open(SAVE_FILE, 'r') as f:
        power_up_record = json.load(f)

    for record in power_up_record:
        for dev in usb.core.find(find_all=True, idVendor=record['hub_vendor'], idProduct=record['hub_product']):
            if dev.port_numbers != tuple(record['hub_port_numbers']):
                continue
            set_port_powered(dev, record['port_number'], True)

    os.unlink(SAVE_FILE)


def power_down():
    power_up_record = []
    hub_port_pairs = []

    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r') as f:
            power_up_record = json.load(f)

    for idVendor, idProduct in devices_to_power_down:
        dev = usb.core.find(idVendor=idVendor, idProduct=idProduct)
        if dev is None:
            print('device [{}:{}] not found, skipping', hex(idVendor), hex(idProduct))
            continue
        if dev.parent is None:
            print('device [{}:{}] has no parent (is libusb up to date?), skipping', hex(idVendor), hex(idProduct))
            continue

        hub = dev.parent

        power_up_record.append({
            'hub_port_numbers': list(hub.port_numbers),
            'hub_vendor': hub.idVendor,
            'hub_product': hub.idProduct,
            'port_number': dev.port_number,
        })
        hub_port_pairs.append((hub, dev.port_number))

    with open(SAVE_FILE, 'w') as f:
        json.dump(power_up_record, f, indent=2)

    for hub, port in hub_port_pairs:
        set_port_powered(hub, port, False)


def daemon():
    import Foundation
    import objc
    import traceback

    class Listener(object):
        def __init__(self):
            center = Foundation.NSDistributedNotificationCenter.defaultCenter()

            sel_locked = objc.selector(self.on_locked, signature=b'v@:@')
            center.addObserver_selector_name_object_(self, sel_locked, 'com.apple.screenIsLocked', None)

            sel_unlocked = objc.selector(self.on_unlocked, signature=b'v@:@')
            center.addObserver_selector_name_object_(self, sel_unlocked, 'com.apple.screenIsUnlocked', None)

        def on_locked(self):
            try:
                power_down()
            except Exception:
                traceback.print_exc()
                exit(1)

        def on_unlocked(self):
            try:
                power_up()
            except Exception:
                traceback.print_exc()
                exit(1)

    listener = Listener()
    Foundation.NSRunLoop.currentRunLoop().run()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('need param: up/down')
    elif sys.argv[1] == 'up':
        power_up()
    elif sys.argv[1] == 'down':
        power_down()
    elif sys.argv[1] == 'daemon':
        daemon()
    else:
        print('need param:', sys.argv[1])

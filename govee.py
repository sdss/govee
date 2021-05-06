#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2021-03-26
# @Filename: govee.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import re
import struct
from datetime import datetime

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData


ADDRESSES = {"E0:13:D5:71:D0:66": "H5179", "A4:C1:38:82:A2:88": "H5072"}
PORT = 1111


def hex_string(data):
    return "".join("{:02x} ".format(x) for x in data)


def decode_temps_h5072(packet_value: int) -> float:
    """Decode potential negative temperatures."""
    # https://github.com/Thrilleratplay/GoveeWatcher/issues/2

    if packet_value & 0x800000:
        return float((packet_value ^ 0x800000) / -10000)
    return float(packet_value / 10000)


class GoveeWatcher:
    """Watches a Govee H5179 device and creates a TCP socket to request status.

    Parameters
    ----------
    addresses
        A mapping of the MAC addresses of the H5179 devices to watch to the model of
        device.
    port
        The port on localhost on which the TCP server will be started. The server
        accepts a single command, ``status``, and returns the address, temperature,
        humidity, battery, and the time of the last update in a single line.
    """

    def __init__(self, addresses: dict[str, str], port: int):

        self.addresses = addresses
        self.port = port

        self.humidity = {}
        self.temperature = {}
        self.battery = {}
        self.last_update = {}

        self.scanner = BleakScanner()
        self.scanner.register_detection_callback(self.detection_callback)

    async def start(self):
        """Starts the TCP server and the device discovery."""

        self.server = await asyncio.start_server(
            self.handle_request,
            "127.0.0.1",
            self.port,
        )
        await self.server.start_serving()

        await self.scanner.start()

        while True:
            await self.scanner.discover(5)
            await asyncio.sleep(1)

    def detection_callback(self, device: BLEDevice, data: AdvertisementData):
        """Called when an update is received from the bluetooth device."""

        address = device.address.upper()

        if address not in self.addresses:
            return

        if self.addresses[address] == 'H5179':

            # The temperature, humidity, and batter are the last 5 bytes in the
            # manufacturer data (not sure what the others are). Temperature and humidity
            # are uint8, while battery is a char (one byte). The data is little endian.
            # Reference: https://bit.ly/2Pvssx9

            if 34817 not in data.manufacturer_data:
                return

            device_data: bytes = data.manufacturer_data[34817]

            try:
                temp, hum, bat = struct.unpack_from("<HHB", device_data[-5:])
            except Exception:
                return

            # Negative values are encoded as two's complement of int16.
            if temp & (1 << 15):
                temp = temp - (1 << 16)
            if hum & (1 << 15):
                hum = hum - (1 << 16)

            temp /= 100
            hum /= 100

        elif self.addresses[address] == 'H5072':

            if 60552 not in data.manufacturer_data:
                return

            device_data: bytes = data.manufacturer_data[60552]

            mfg_data_5075 = hex_string(device_data[1:4]).replace(" ", "")
            packet = int(mfg_data_5075, 16)

            temp = decode_temps_h5072(packet)
            hum = float((packet % 1000) / 10)
            bat = int(device_data[4])

        else:
            return

        self.temperature[address] = temp
        self.humidity[address] = hum
        self.battery[address] = bat
        self.last_update[address] = datetime.utcnow()

    async def handle_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        """Handle connections to the TCP server."""

        while True:
            try:
                data = await reader.readline()

                command = data.decode().strip().lower()
                command_has_address = re.match('^status ((?:[0-9A-F]:?)+)', command)

                if command_has_address:
                    command_address = command_has_address.groups[0]
                    if command_address not in self.temperature:
                        writer.write(b'?\n')
                    else:
                        writer.write(
                            f"{command_address} {self.temperature[command_address]} "
                            f"{self.humidity[command_address]} "
                            f"{self.battery[command_address]} "
                            f"{self.last_update[command_address].isoformat()}\n".encode()
                        )
                    await writer.drain()
                    continue

                if command.startswith("status"):
                    for address in self.temperature:
                        writer.write(
                            f"{address} {self.temperature[address]} "
                            f"{self.humidity[address]} "
                            f"{self.battery[address]} "
                            f"{self.last_update[address].isoformat()}\n".encode()
                        )
                        await writer.drain()

                if reader.at_eof():
                    return
            except Exception:
                continue


async def run():
    watcher = GoveeWatcher(ADDRESSES, PORT)
    await watcher.start()


loop = asyncio.get_event_loop()
loop.run_until_complete(run())

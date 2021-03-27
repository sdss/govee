#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2021-03-26
# @Filename: govee.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import struct
from datetime import datetime

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

ADDRESS = "E0:13:D5:71:D0:66"
PORT = 1111


class GoveeWatcher:
    """Watches a Govee H5179 device and creates a TCP socket to request status."""

    def __init__(self, address, port):

        self.address = address.upper()
        self.port = port

        self.humidity = 0.0
        self.temperature = 0.0
        self.battery = 0.0
        self.last_update = datetime.utcnow()

        self.scanner = BleakScanner()
        self.scanner.register_detection_callback(self.detection_callback)

    async def start(self):

        self.server = await asyncio.start_server(
            self.handle_request, "127.0.0.1", self.port,
        )
        await self.server.start_serving()

        await self.scanner.start()

        while True:
            await self.scanner.discover(5)
            await asyncio.sleep(1)

    def detection_callback(self, device: BLEDevice, data: AdvertisementData):

        if device.address.upper() != self.address:
            return

        if 34817 not in data.manufacturer_data:
            return

        device_data: bytes = data.manufacturer_data[34817]

        # The temperature, humidity, and batter are the last 5 bytes in the
        # manufacturer data (not sure what the others are). Temperature and humidity
        # are uint8, while battery is a char (one byte). The data is little endian.
        # Reference: https://bit.ly/2Pvssx9

        try:
            temp, hum, bat = struct.unpack_from("<HHB", device_data[-5:])
        except Exception:
            return

        # TODO: negative temperatures are stored as two's complement.

        self.temperature = temp / 100
        self.humidity = hum / 100
        self.battery = bat
        self.last_update = datetime.utcnow()

    async def handle_request(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
    ):

        while True:
            try:
                data = await reader.readline()

                if data.decode().strip().lower() == "status":
                    writer.write(
                        f"{self.temperature} {self.humidity} "
                        f"{self.battery} {self.last_update.isoformat()}\n".encode()
                    )

                if reader.at_eof():
                    return
            except Exception:
                continue


async def run():

    watcher = GoveeWatcher(ADDRESS, PORT)
    await watcher.start()


loop = asyncio.get_event_loop()
loop.run_until_complete(run())

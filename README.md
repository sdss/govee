# Govee H5179/H5072

This code implements a watcher for the [Govee H5179](https://store.govee.com/products/wi-fi-temperature-humidity-sensor) or [Govee 5072 sensors](https://www.amazon.com/Bluetooth-Temperature-Thermometer-Hygrometer-Calibration/dp/B07DWMJKP5). The device reports the temperature, humidity, and battery as a Bluetooth Low Energy broadcast. This code continuously listens to the available device, identifies the device matching the MAC address, and reads the sensor data.

For the H5279, the temperature, humidity, and battery data are encoded in the manufacturer data package. The last five bytes represent the temperature (two bytes), humidity (two bytes), and battery (one byte).

While running, the code creates a TCP server on port 1111 (default) which accepts a single command `status`. It returns of line per device with the address, temperature, humidity, battery, and time at which the values were last seen.

## Installation

The code requires Python 3.7 or above. First, clone the repository

```
git clone https://github.com/sdss/govee
```

If desired, create a new virtual environment. Install [bleak](https://bleak.readthedocs.io/en/latest/)

```
pip install bleak
```

Depending on the installation, you may need to install `bluez` and `pybluez`. You may also need to allow the `python` binary to access the bluetooth device

```
setcap cap_net_raw,cap_net_admin+eip $(eval readlink -f `which python`)
```

## Running

Just run the main code

```
python govee.py
```

To run in detached mode

```
python govee.py > govee.log &
disown  -h  %1
```

You can reattach the process using `retty` or `reptyr` but normally you'll just want to kill it. You can also run the code inside a `tmux` or `screen`.

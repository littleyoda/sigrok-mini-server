#!/usr/bin/python

from __future__ import print_function
from sigrok.core.classes import *
from tcpsocket import *
from signal import signal, SIGINT
import argparse
import sys
import json

clients = []
devices = []
devicehashes = []

sigroklock = threading.Lock()


def openDevice(arg):
    print("Creating Device with " + arg)
    driver_spec = arg.split(":")

    if driver_spec[0] not in context.drivers:
        print("Devicename does not exist!")
        sys.exit(1)
    d = context.drivers[driver_spec[0]]

    driver_options = {}
    for pair in driver_spec[1:]:
        name, value = pair.split('=')
        key = ConfigKey.get_by_identifier(name)
        driver_options[name] = key.parse_string(value)

    foundDevices = d.scan(**driver_options)
    if (len(foundDevices) == 0):
        print("Device " + arg + " not found")
        sys.exit(1)
    if (len(foundDevices) > 1):
        print("Found more than one device. Using first one!")
        sys.exit(1)
    device = foundDevices[0]

    device.open()
    return device


def hash(device):
    return device.vendor + ":" + device.model + ":" + device.version + ":" + device.connection_id()


def handleDeviceOptions(device, string):
    for pair in string.split(":"):
        print(pair)
        name, value = pair.split('=')
        print("Setting %s to %s" % (name, value))
        key = ConfigKey.get_by_identifier(name)
        device.config_set(key, key.parse_string(value))


def handleCmdInfo(c):
    info = {
                    "msgtype": "deviceinfo",
                    "deviceinfo": []
           }
    for device in devices:
        dev = {
                "vendor": device.vendor,
                "model": device.model,
                "version": device.version,
                "id": device.connection_id(),
                "hash": hash(device),
                "settings": [],
                "channels": []
        }
        info["deviceinfo"].append(dev)
        for key in device.config_keys():
            with sigroklock:
                try:
                    supportsGet = False
                    supportsSet = False
                    supportsList = False
                    cap = device.config_capabilities(key)
                    currentValue = ""
                    if Capability.GET in cap:
                        supportsGet = True
                        currentValue = device.config_get(key)
                    if Capability.SET in cap:
                        supportsSet = True
                    if Capability.GET in cap:
                        supportsList = True
                    if (not(supportsGet or supportsSet)):
                        continue
                    dev["settings"].append({
                        "id": key.identifier,
                        "value": str(currentValue),
                        "valuetype": str(key.data_type().name),
                        "name": key.name,
                        "supportsGet": supportsGet,
                        "supportsSet": supportsSet,
                        "supportsList": supportsList
                       })
                except Exception as e:
                    print('Exception: ' + str(e))
        for channel in device.channels:
            dev["channels"].append(
                {
                    "name": channel.name,
                    "enabled": str(channel.enabled),
                    "idx": str(channel.index),
                    "type": channel.type.name
                }
            )
    json_string = json.dumps(info)
    send(json_string + "\n")


def handleCmdSet(c):
    dev = devices[devicehashes.index(c["hash"])]   
    key = ConfigKey.get_by_identifier(str(c["key"]))
    dev.config_set(key, key.parse_string(str(c["value"])))
    
def handleCmdGet(c):
    dev = devices[devicehashes.index(c["hash"])]   
    key = ConfigKey.get_by_identifier(str(c["key"]))
    value = dev.config_get(key)
    info = {
                    "msgtype": "value",
                    "device": c["hash"],
                    "key": str(c["key"]),
                    "value": str(value)
           }
    json_string = json.dumps(info)
    send(json_string + "\n")


def handleCmd(c):
    cmd = c["cmd"].lower();
    print("Cmd" + cmd)
    if (cmd == "info"):
        handleCmdInfo(c)
    elif (cmd == "set"):
        handleCmdSet(c)
        handleCmdGet(c) # Return changed Value
    elif (cmd == "get"):
        handleCmdGet(c)


def handleCmds():
    cmds = getCmds()
    if (len(cmds) == 0):
        return
    for c in cmds:
        handleCmd(c)


def datafeed_in(device, packet):
    if (packet.type == PacketType.FRAME_BEGIN):
        pass
    elif (packet.type == PacketType.FRAME_END):
        pass
    elif (packet.type == PacketType.LOGIC):
#        for v in packet.payload.data:
#           print("{0:08b}".format(v))
        pass
    elif (packet.type == PacketType.ANALOG):
        # https://sigrok.org/api/libsigrok/unstable/bindings/python/a00722.html
        if not len(packet.payload.channels):
            return
        h = hash(device)
        outputdata = {
            "msgtype": "data",
            "channels": [],
            "unit":  packet.payload.unit.name,
            "device": {
                "hash": h,
                "id": devicehashes.index(hash(device))
            }
        }
        for i in range(0, len(packet.payload.channels)):
            c = packet.payload.channels[i]
            array = []
            for value in packet.payload.data[i]:
                array.append(str(value))
            outputdata["channels"].append(c.name)
            outputdata[c.name] = array
        json_string = json.dumps(outputdata)
        send(json_string + "\n")
    else:
        print("Unknown PacketType: " + str(packet.type))
    handleCmds()

def exitHandler(signum, frame):
    setKillFlag()
    session.stop
    for d in devices:
        d.close()
    sys.exit(1)

def initDevices(list):
    for d in list:
        # d[0] => Device Options
        # d[1] => Config Options
        device = openDevice(d[0])
        devices.append(device)
        session.add_device(device)
        devicehashes.append(hash(device))

        if (len(d) > 1):
            handleDeviceOptions(device, d[1])

def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d', '--driver', help="The driver to use and (if necessary) driver options", nargs="+", action='append')
    parser.add_argument('-l', '--loglevel', help="Log level", type=int)
    args = parser.parse_args()
    if not (args.driver):
            parser.print_help()
            print("\n")
            print("Examples:")
            print("Using the Demo device (limited to one sample pro sec)")
            print("	sigrok-mini-server.py -d demo samplerate=1")
            print()
            print("Using two devices")
            print("	sigrok-mini-server.py -d demo samplerate=1 -d korad-kaxxxxp:conn=/dev/ttyACM0")
            sys.exit(1)
    return args

#
#
#
# Main
#
#
#

# Init
args = parseArgs()
context = Context.create()
if args.loglevel:
    context.log_level = LogLevel.get(int(args.loglevel))
session = context.create_session()
initDevices(args.driver)

# Start
session.start()
startWorkerThread()
session.add_datafeed_callback(datafeed_in)

# Clean-Up
signal(SIGINT, exitHandler)
session.run()

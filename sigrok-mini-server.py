#!/usr/bin/python

from __future__ import print_function
from sigrok.core.classes import *
from tcpsocket import *
from signal import signal, SIGINT
import argparse
import sys
import json
import signal
import time

deviceinfo = {}
threads = []
devicehashes = []
autoget = {}

sigroklock = threading.Lock()

class DeviceThread(threading.Thread):
    def __init__(self,context,arg):
        threading.Thread.__init__(self)
        self.session = context.create_session()
        self.device = self.openDevice(d[0])
        self.session.add_device(self.device)
        self.hash = hash(self.device)
        if (len(d) > 1):
            self.handleDeviceOptions(self.device, d[1])
        
    def getInfo(self):
        dev = {
                "vendor": self.device.vendor,
                "model": self.device.model,
                "version": self.device.version,
                "id": self.device.connection_id(),
                "hash": self.hash,
                "settings": [],
                "channels": [],
                "enabledAnalogChannels": [],
                "enabledLogicChannels": []
        }
        for key in self.device.config_keys():
            with sigroklock:
                try:
                    supportsGet = False
                    supportsSet = False
                    supportsList = False
                    cap = self.device.config_capabilities(key)
                    currentValue = ""
                    if Capability.GET in cap:
                        supportsGet = True
                        currentValue = self.device.config_get(key)
                    if Capability.SET in cap:
                        supportsSet = True
                    if Capability.LIST in cap:
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
        for channel in self.device.channels:
            cinfo = {
                    "name": channel.name,
                    "enabled": str(channel.enabled),
                    "idx": str(channel.index),
                    "type": channel.type.name
                }
            dev["channels"].append(cinfo)
            if channel.enabled and channel.type.name == "LOGIC":
                    dev["enabledLogicChannels"].append(cinfo)
            if channel.enabled and channel.type.name == "ANALOG":
                    dev["enabledAnalogChannels"].append(cinfo)
        return dev
        
    def run(self):
        self.session.start()
        self.session.add_datafeed_callback(datafeed_in)
        self.session.run()
        print("Waiting")
        
    def stop(self):
        print("Stopping Device")
        try:
            self.session.stop()
            time.sleep(1)
            self.device.close()
        except RuntimeError:
            pass

    def openDevice(self, arg):
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

    def handleDeviceOptions(self, device, string):
            for pair in string.split(":"):
                name, value = pair.split('=')
                print("Setting %s to %s" % (name, value))
                key = ConfigKey.get_by_identifier(name)
                device.config_set(key, key.parse_string(value))
                
    def handleCmdSet(self, c):
        try:
            key = ConfigKey.get_by_identifier(str(c["key"]))
            self.device.config_set(key, key.parse_string(str(c["value"])))
        except (ValueError, RuntimeError):
            print("ValueError: " + str(c["key"]) + " " + str(c["value"]))
    
    def handleCmdGet(self, c):
        try:
            dev = self.device
            key = ConfigKey.get_by_identifier(str(c["key"]))
            value = dev.config_get(key)
            didx = devicehashes.index(self.hash)
            info = {
               "device": {
                    "hash": self.hash,
                    "id": didx
                },
                    "msgtype": "value",
                    "key": str(c["key"]),
                    "value": str(value)
               }
            json_string = json.dumps(info)
            send(json_string + "\n")
        except (ValueError, KeyError, RuntimeError):
            print("[" + self.hash + "] Error " + str(c["key"]))
                


def hash(device):
    return device.vendor + ":" + device.model + ":" + device.version 
    #+ ":" + device.connection_id()


def collectDeviceInfo():
    info = {
                    "msgtype": "deviceinfo",
                    "deviceinfo": []
           }
    for t in threads:
        info["deviceinfo"].append(t.getInfo())
    return info
        

def handleCmdInfo(c):
    info = collectDeviceInfo()
    json_string = json.dumps(info)
    send(json_string + "\n")

def handleCmd(c):
    cmd = c["cmd"].lower();
    print("Cmd" + cmd)
    if (cmd == "info"):
        handleCmdInfo(c)
        return
    if (cmd == "autoget"):
        print(cmd)
        if (c["key"] in autoget):
            print("FOUND")
        else:
            autoget[c["key"]] = {
                "key": c["key"],
                "next": 0,
                "interval": float(c["interval"])
            }
        print(autoget)
        return
    print(c)
    for t in threads:
        if (t.hash == c["hash"] or c["hash"] == "*"):
            if (cmd == "set"):
                t.handleCmdSet(c)
                t.handleCmdGet(c) # Return changed Value
            elif (cmd == "get"):
                t. handleCmdGet(c)
            else:
                print("Unknown Command: " + cmd)


# remove duplicates 
def filterCmds(cmds):
    while len(cmds) > 1:
        if (cmds[0]["cmd"] == cmds[1]["cmd"]) and (cmds[0]["key"] == cmds[1]["key"]):
            cmds.pop(0)
        else:
            break
    return cmds

def handleCmds():
    cmds = getCmds()
    if (len(cmds) == 0):
        return
    cmds = filterCmds(cmds)
    for c in cmds:
        handleCmd(c)


def datafeed_in(device, packet):
    if not("deviceinfo" in deviceinfo):
        return
    if (packet.type == PacketType.FRAME_BEGIN):
        pass
    elif (packet.type == PacketType.FRAME_END):
        pass
    elif (packet.type == PacketType.LOGIC):
        h = hash(device)
        didx = devicehashes.index(h)
        outputdata = {
            "msgtype": "data",
            "channels": [],
            "unit":  "LOGIC ",
            "device": {
                "hash": h,
                "id": didx
            }
        }
        data = packet.payload.data
        dinfo = deviceinfo["deviceinfo"][didx]
        enabled = len(dinfo["enabledLogicChannels"])
        # Create Container
        for c in dinfo["enabledLogicChannels"]:
            outputdata["channels"].append(c["name"])
            outputdata[c["name"]] = []
        # Fill Container with data
        for i in xrange(0,len(data),packet.payload.unit_size()):
            for j in xrange(0, enabled):
                c = dinfo["enabledLogicChannels"][j]
                value = (data[ i + j / 8] >> (j % 8)) & 1
                outputdata[c["name"]].append(str(value))
                
        json_string = json.dumps(outputdata, sort_keys=True)
        send(json_string + "\n")
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
        json_string = json.dumps(outputdata, sort_keys=True)
        send(json_string + "\n")
    else:
        print("Unknown PacketType: " + str(packet.type))
    handleCmds()


def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d', '--driver', help="The driver incl. scan options and (if necessary) driver options", nargs="+", action='append')
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



def exitHandler(signum, frame):
    print("==================================================")
    print("Shutting down! Can take same seconds! Please wait!")
    print("==================================================")
    setKillFlag()
    for t in threads:
        t.stop()
    sys.exit(1)



    
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
    

for d in args.driver:
    t = DeviceThread(context, d)
    devicehashes.append(t.hash)
    threads.append(t)

deviceinfo = collectDeviceInfo()

for t in threads:
    t.start()

startWorkerThread()

signal.signal(signal.SIGINT, exitHandler)
try:
    while True:
        now = time.time()
        for k, v in autoget.items():
            if (v["next"] < now):
                print("Excute " + str(k))
                handleCmd( {
                "cmd": "get",
                "key": k,
                "hash": "*"
                })
                v["next"] = now + v["interval"] / 1000
                break # just one request
        time.sleep(0.05)
except:
    exitHandler(False, False)

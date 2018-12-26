# sigrok-mini-server
Delivers data from sigrok supported devices via TCP/IP in JSON Format

# Status
* early development stage
* only tested under linux
* hardly any error handling
* only analog sigrok packets supported, no logic packets

# How to use (under Linux)
Currently you need a patched version of sigrok

see https://github.com/sigrokproject/libsigrok/pull/14

On the first console
`./sigrok-mini-server.py  -d demo samplerate=1`
ls
On the second console
`nc localhost 8888`

Every second you should see new data in json format
```
{"channels": ["A3"], "device": {"hash": ":Demo device::", "id": 0}, "A3": ["4.0"], "msgtype": "data"}
{"channels": ["A1"], "device": {"hash": ":Demo device::", "id": 0}, "A1": ["9.51056"], "msgtype": "data"}
{"channels": ["A0"], "device": {"hash": ":Demo device::", "id": 0}, "msgtype": "data", "A0": ["-10.0"]}
{"channels": ["A2"], "device": {"hash": ":Demo device::", "id": 0}, "A2": ["8.0"], "msgtype": "data"}

```

# Commands in examples

## Information about connected devices
Request:`{ "cmd": "INFO" }` 

Response: You will receive a message with information about all connected devices.
The value of the hash-attribute is used to identify the device in all messages related to the device

```
{
   "deviceinfo":[
      {
         "hash":":Demo device::",
         "settings":[
            {
               "supportsGet":true,
               "name":"LIMIT_FRAMES",
               "supportsSet":true,
               "valuetype":"UINT64",
               "value":"0",
               "supportsList":true,
               "id":"limit_frames"
            },
            {
               "supportsGet":true,
               "name":"LIMIT_SAMPLES",
               "supportsSet":true,
               "valuetype":"UINT64",
               "value":"0",
               "supportsList":true,
               "id":"limit_samples"
            },
            {
               "supportsGet":true,
               "name":"LIMIT_MSEC",
               "supportsSet":true,
               "valuetype":"UINT64",
               "value":"0",
               "supportsList":true,
               "id":"limit_time"
            },
            {
               "supportsGet":true,
               "name":"AVG_SAMPLES",
               "supportsSet":true,
               "valuetype":"UINT64",
               "value":"0",
               "supportsList":true,
               "id":"avg_samples"
            },
            {
               "supportsGet":true,
               "name":"AVERAGING",
               "supportsSet":true,
               "valuetype":"BOOL",
               "value":"False",
               "supportsList":true,
               "id":"averaging"
            },
            {
               "supportsGet":true,
               "name":"CAPTURE_RATIO",
               "supportsSet":true,
               "valuetype":"UINT64",
               "value":"20",
               "supportsList":true,
               "id":"captureratio"
            },
            {
               "supportsGet":true,
               "name":"SAMPLERATE",
               "supportsSet":true,
               "valuetype":"UINT64",
               "value":"1",
               "supportsList":true,
               "id":"samplerate"
            }
         ],
         "version":"",
         "vendor":"",
         "model":"Demo device",
         "id":""
      }
   ],
   "msgtype":"deviceinfo"
}
```

## Set Configs
e.g. The following command changes the samplerate to 10

Request:
`{ "cmd": "set", "key": "samplerate", "value":"10", "hash":":Demo device::"}`

Response:
`{"device": ":Demo device::", "msgtype": "value", "value": "10", "key": "samplerate"}`


## Get Configs
Request:
`{ "cmd": "get", "key": "samplerate", "hash":":Demo device::"}`

Response:
`{"device": ":Demo device::", "msgtype": "value", "value": "1", "key": "samplerate"}`

## Auto Get Config
Request:
`{ "cmd":"autoget", "hash":"*", "key": "voltage_target", "interval": "500"}`

Response:
Get Config-Responses ever 500 ms

# Multiple Devices
You can access more than one device

e.g.`sigrok-mini-server.py -d demo samplerate=1 -d korad-kaxxxxp:conn=/dev/ttyACM0`




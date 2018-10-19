from signal import signal, SIGINT
import json
import socket
import select
import threading

lock = threading.Lock()
clients = []
cmds = []
killed = False

def send(msg):
    with lock:
        for s in clients:
            try:
                s.send(msg)
            except (RuntimeError, socket.error):
                print("Error sending Data")
                pass # client disconnected

def getCmds():
    global cmds
    with lock:
        newcmds = cmds
        cmds = []
        return newcmds            



def worker():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('', 8888))
    server_socket.listen(5)
    print("Listening on port 8888")
    read_list = [ server_socket ]
    while True:
        if killed:
            for c in clients:
                s.close()
            server_socket.close()
            return
        readable, writable, errored = select.select(read_list, [], [], 0.5)
        with lock:
            for s in readable:
                if s is server_socket:
                    client_socket, address = server_socket.accept()
                    read_list.append(client_socket)
                    clients.append(client_socket)
                    print("Connection from " + str(address))
                else:
                    try:
                        data = s.recv(1024)
                    except socket.error:
                        print("Errror receiving data")
                        pass
                    if data:
                        print("Received: " + data)
                        try:
                            cmds.append(json.loads(data))
                        except ValueError:
                            print("Error parsing: " + data)
                            pass
                    else:
                        print("Connection closed!")
                        s.close()
                        read_list.remove(s)    
                        clients.remove(s)

def setKillFlag():
    global killed
    killed = True
    
def startWorkerThread():
    t = threading.Thread(target=worker)
    t.start()

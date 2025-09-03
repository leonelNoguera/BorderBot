#!/usr/bin/env python
import sys
import borderbot
import socket
import json
class Client(object):
    def __init__(self, args):
        self.pair = 'WCT-USDT'
        port = 7000
        host = 'localhost'
        if (args):
            self.pair = args[0]
            host = args[2]
            port = int(args[3])
        self.socket = socket.socket()
        self.socket.connect((host, port))
        recv = json.JSONDecoder().decode(self.socket.recv(2048).decode())
        self.socket.send(json.JSONEncoder().encode({'type' : 'config', 'sub-type' : 'set_pair', 'pair' : self.pair}).encode())
        self.socket.recv(2048)
        config = ''
        self.socket.send(json.JSONEncoder().encode({'type' : 'config', 'sub-type' : 'get_config'}).encode())
        recv = json.JSONDecoder().decode(self.socket.recv(2048).decode())
        while (recv['config']):
            config += recv['config']
            self.socket.send(json.JSONEncoder().encode({'type' : 'config', 'sub-type' : 'get_config'}).encode())
            recv = json.JSONDecoder().decode(self.socket.recv(2048).decode())
        config = json.JSONDecoder().decode(config)
        while (True):
            bot = borderbot.BorderBot(args, socket = self.socket, config = config)
            bot.start()
        self.socket.close()
        print("Conexión cerrada")
Client(args = sys.argv[1:])

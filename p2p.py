from enum import Enum
import random
from struct import pack
from time import time
from socket import *
from tkinter import Pack
from typing import NamedTuple
from threading import Thread

import orjson
import json
import hashlib
import argparse

HELP = """
-- Help menu
/about      -> See detailed informations about specific user /about <id:str?>
/rename     -> read the command. it isn't that hard /rename <name:str>
/connect    -> connect to a specific peer /connect <host:str> <port:int?>
/disconnect -> disconnect from a specific peer /disconnect <host:str> <port:int?>
"""
def default(obj):
    if hasattr(obj, '_asdict'):
        return obj._asdict()

class NodeList(NamedTuple):
    pass

class NodeListResponse(NamedTuple):
    nodes: list[str]

class Message(NamedTuple):
    content: str
    username: str
    md5_hash: str
    timestamp: int
    host: str = None
    port: int = None

class Error(NamedTuple):
    content: str
    timestamp: int

class Protocol(Enum):
    HEART_BEAT = 0
    NODES = 1
    NODES_REPONSE = -1
    MESSAGE = 2
    ERROR = 3

class Node:
    connected_nodes = []
    own_address: tuple = ()
    buffer_size = 2048
    udp_socket_client: socket = None
    authentication_key = ''
    recent_messages: list[str] = []

    def __init__(self, host: str, port: int) -> None:
        self.own_address = (host, port)
        self.udp_socket_client = socket(AF_INET, SOCK_DGRAM)
        self.udp_socket_client.bind(self.own_address)
        pass

    def send_package(self, node, package: Protocol, client: NamedTuple, share_public: bool=True) -> bool:
        self.udp_socket_client.sendto(bytes(str(json.dumps({
            'pkg_id': package._value_,
            'data': json.loads(orjson.dumps(client, default=default).decode('ascii')),
            'share_public': share_public
        })), 'ascii'), node)

    def parse_message(self, peer: tuple, message: Message, share_public: bool=True):

        if message['content'] == '':
            return

        if message['md5_hash'] in self.recent_messages:
            return

        self.recent_messages.append(message['md5_hash'])

        redefined_message = Message(
            content=message['content'],
            timestamp=message['timestamp'],
            username=message['username'],
            md5_hash=message['md5_hash'],
            port=peer[1],
            host=peer[0]
        )

        print(f'[{redefined_message.md5_hash} | {redefined_message.timestamp} | {redefined_message.host}:{redefined_message.port}] {redefined_message.username}: {redefined_message.content}')
        
        if share_public == False:
            return

        for node in self.connected_nodes:
            if node == peer or node == self.own_address:
                continue
            self.send_package(node=(node[0], int(node[1])), package=Protocol.MESSAGE, client=redefined_message, share_public=share_public)

    def parse_buffer(self, buffer, address):
        j_dict = json.loads(str(buffer, 'ascii'))

        match j_dict['pkg_id']:
            case 0:
                self.udp_socket_client.sendto(bytes(0), address)
            case -1:
                conn_nodes = j_dict['data']['nodes']
                for node in conn_nodes:
                    self.connected_nodes.append(node)
                    self.send_package(self.own_address, package=Protocol.MESSAGE, client=Message(
                            content=f'registered new address -> {node}',
                            username='SYSTEM',
                            md5_hash='NO-HASH',
                            timestamp=time()
                        ), share_public=False)      
            case 1:
                self.send_package(node=address, package=Protocol.NODES_REPONSE, client=NodeListResponse(nodes=self.connected_nodes))
            case 2:
                self.parse_message(peer=address, message=j_dict['data'], share_public=j_dict['share_public'])
            case _:
                return

    def run_commandline(self):
        while True:
            buffer, address = self.udp_socket_client.recvfrom(self.buffer_size)
            if address not in self.connected_nodes:
                self.connected_nodes.append(address)
            self.parse_buffer(buffer, address)


class Peer:
    root_node: Node
    password: str
    username: str

    def send_message(self, content: str, share_public: bool=True):

        is_command = content.startswith('/')
        args = content.split(' ')

        if is_command == True:

            match args[0].removeprefix('/'):
                case 'rename':
                    if args[1] == None:
                        self.send_message(f"""
                        Your Username: {self.username}
                        """, False)
                        return
                    self.send_message(f"""
                    Old Username: {self.username}
                    New Username: {args[1]}
                    """, False)
                    self.username = args[1]
                case 'help':
                    self.send_message(HELP, False)
                case 'about':
                    self.send_message(f"""
                    Your Username: {self.username}
                    Host: {self.root_node.own_address[0]}
                    Port: {self.root_node.own_address[1]}
                    BufferSize: {self.root_node.buffer_size}
                    Own Address: {self.root_node.own_address}
                    Recent Messages len: {len(self.root_node.recent_messages)}
                    """)
                    pass
                case 'connect':
                    host, port = args[1], args[2]
                    if not host:
                        self.send_message(f"""
                        Please set Hostname! 
                        """, False)
                        return
                    if not port:
                        port = 5050
                        self.send_message(f"""
                        Port not specified! Using 5050 as fallback
                        """, False)
                    self.root_node.connected_nodes.append((host, int(port)))
                    for node in self.root_node.connected_nodes:
                        print(f'{node} -> requesting connected nodes...')
                        self.root_node.send_package(node=node, package=Protocol.NODES, client=NodeList())
            return

        root_node.send_package(node=self.root_node.own_address, package=Protocol.MESSAGE, client=Message(
            content=content,
            username=self.username,
            timestamp=time(),
            md5_hash=hashlib.md5((content + self.username + str(time())).encode('ascii')).hexdigest()
        ), share_public=share_public)

    def __init__(self, node: Node, username: str) -> None:
        self.username = username
        self.root_node = node
    
    def run(self):
        while 1:
            self.send_message(input('>> '))

parser = argparse.ArgumentParser(description='Decentralized Messaging Platform')
parser.add_argument('--port', metavar='-P', type=int, default=5050, help='on which port the thing should run')
parser.add_argument('--username', metavar='-U', type=str, help='your username')

args = parser.parse_args()
username = args.username
if username is None:
    username = random.choice(['fish', 'frosty', 'lion', 'tiger', 'hunter', 'queen', 'king'])
    print(f'No name defined! Your random generated username is {username}')

root_node = Node('0.0.0.0', args.port)
peer = Peer(root_node, username)
thread = Thread(target=peer.run)
thread.start()
root_node.run_commandline()

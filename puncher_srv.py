import logging
import socket
import sys
import json
import time
import signal
import threading

logger = logging.getLogger()
addresses = dict()
pairings = dict()
shutdown = threading.Event()
cleaner = None
retransmitter = None
server = None


class Cleaner(threading.Thread):
    def __init__(self):
        super(Cleaner, self).__init__(name="Cleaner")
        self.start()

    def run(self):
        while not shutdown.is_set():
            if shutdown.wait(60):
                break
            now5m = time.time() - (5*60)
            for k in list(addresses.keys()):
                if addresses[k]["count"]>0:
                    logger.info("got %d packets from %s:%d", addresses[k]["count"], addresses[k]["addr"],
                                addresses[k]["re_port"] if "re_port" in addresses[k] else 0)
                if addresses[k]["time"] < now5m:
                    logger.info("removing puncher IP %s", k)
                    del addresses[k]
                elif "$" in addresses[k]:
                    del addresses[k]["$"]

            for k in list(pairings.keys()):
                if pairings[k]["time"] < now5m:
                    logger.info("removing pairing id %s", k)
                    del pairings[k]

        logger.info("shutting down Cleaner")


class Retransmitter(threading.Thread):
    def __init__(self, host, port):
        super(Retransmitter, self).__init__(name="Retransmitter")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDPs
        self.sock.settimeout(5)
        self.sock.bind((host, port))
        logger.info("retransmitter is on %s:%d", host, port)
        self.start()

    def run(self):
        while not shutdown.is_set():
            try:
                datastr, addr = self.sock.recvfrom(1500)
            except socket.timeout:
                continue
            if addr[0] in addresses:
                addr_struct = addresses[addr[0]]
                addr_struct["time"] = time.time()
                addr_struct["re_port"] = addr[1]
                addr_struct["count"] += 1
                if "$" in addr_struct:
                    self.sock.sendto(datastr, addr_struct["$"])
                elif "send_to" in addr_struct and addr_struct["send_to"] in addresses:
                    receiver = addresses[addr_struct["send_to"]]
                    if "re_port" in receiver:
                        ap2 = (addr_struct["send_to"], receiver["re_port"])
                        addr_struct["$"] = ap2
                        self.sock.sendto(datastr, ap2)

        logger.info("shutting down Retransmitter")


class Server(threading.Thread):
    def __init__(self, host, port):
        super(Server, self).__init__(name="Server")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDPs
        self.sock.settimeout(5)
        self.sock.bind((host, port))
        logger.info("server is on %s:%d", host, port)
        self.start()

    def send_ports(self, source, target, comment=""):
        if isinstance(source, str):
            if source in addresses:
                source = addresses[source]
            else:
                return False
        if isinstance(target, str):
            if target in addresses:
                target = addresses[target]
            else:
                return False

        logger.info("sending ports of %s:%d to %s:%d", source["addr"], source["puncher_port"],
                    target["addr"], target["puncher_port"])
        self.sock.sendto(bytes(json.dumps({
            "punch_id": target["punch_id"],
            "addr": source["addr"],
            "port": source["puncher_port"],
            "comment": comment,
            "re_port": source["re_port"] if "re_port" in source else None
        }), "utf-8"), (target["addr"], target["puncher_port"]))
        return True

    def run(self):
        while not shutdown.is_set():
            try:
                datastr, addr = self.sock.recvfrom(1500)
                data = json.loads(datastr)
            except socket.timeout:
                continue
            except json.JSONDecodeError:
                logger.warning("got unparseable data in server port from %s:%d\n%s", addr[0], addr[1], repr(datastr))
                continue

            if "punch_id" in data and isinstance(data["punch_id"], str):
                punch_id = data["punch_id"]
                if addr[0] in addresses:
                    addr_struct = addresses[addr[0]]
                else:
                    addr_struct = addresses[addr[0]] = {
                        "puncher_port": addr[1],
                        "punch_id": punch_id,
                        "addr": addr[0],
                        "count": 0
                    }
                    logger.info("creating address structure %s:%d", addr[0], addr[1])
                addr_struct["time"] = time.time()
                if punch_id in pairings:
                    pairing = pairings[punch_id]
                else:
                    pairing = pairings[punch_id] = {
                        "addr1": addr[0]
                    }
                    logger.info("creating pairing structure %s", punch_id)
                pairing["time"] = time.time()
                addr1 = pairing["addr1"]
                if addr1 != addr[0] and "addr2" not in pairing:
                    pairing["addr2"] = addr[0]
                addr2 = pairing["addr2"] if "addr2" in pairing else None
                other_addr = addr1 if addr1 != addr[0] else addr2
                logger.info("other addr is %s", repr(other_addr))
                if other_addr is not None and other_addr in addresses:
                    other_addr_struct = addresses[other_addr]
                else:
                    other_addr_struct = None

                if "set_send_to" in data:
                    logger.info("found request set_send_to for addr %s:%d", addr[0], addr[1])
                    addr_struct["set_send_to"] = True

                if "set_send_to" in addr_struct and other_addr_struct is not None\
                        and "set_send_to" in other_addr_struct:
                    logger.info("setting connection %s <-> %s", addr[0], other_addr)
                    addr_struct["send_to"] = other_addr
                    other_addr_struct["send_to"] = addr[0]
                    del other_addr_struct["set_send_to"]
                    del addr_struct["set_send_to"]

                if "get_my_ports" in data:
                    logger.info("found request get_my_ports for addr %s:%d", addr[0], addr[1])
                    self.send_ports(addr_struct, addr_struct, "get_my_ports")

                if "get_other_comm_port" in data:
                    logger.info("found request get_other_comm_port for addr %s:%d", addr[0], addr[1])
                    if other_addr_struct is not None:
                        self.send_ports(other_addr_struct, addr_struct, "get_other_comm_port")

                if "get_other_ports" in data or "get_other_ports" in addr_struct:
                    logger.info("found request get_other_ports for addr %s:%d", addr[0], addr[1])
                    if other_addr_struct is not None and "re_port" in other_addr_struct:
                        self.send_ports(other_addr_struct, addr_struct, "get_other_ports")

        logger.info("shutting down Server")


def signal_handler(signum, frame):
    shutdown.set()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    port = 6980
    port2 = 6981
    host = "0.0.0.0"

    cleaner = Cleaner()
    retransmitter = Retransmitter(host, port2)
    server = Server(host, port)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGHUP, signal_handler)

    shutdown.wait()
    logger.info("shutting down")
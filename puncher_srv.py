import logging
import socket
import sys
import json
import time
import threading

logger = logging.getLogger()
addresses = dict()

class Cleaner(threading.Thread):
    """
    A thread to dispatch a signal if it is emitted in asynchronous mode.
    Like in `async_decorator.async`, here the thread gets the info about it's parent thread and logs it up.
    """

    def __init__(self):
        """
        Sets up necessary parameters like thread name, it's parent's name and id, emitter...
        :param Signal sig: signal reference
        :param args: arguments of the signal call
        :param kwargs: KV arguments of the signal call
        """
        super(Cleaner, self).__init__(name="thread")
        self.daemon = True
        self.start()

    def run(self):
        """
        Thread entry point.
        Logs the thread ancestry.
        Starts the signal.
        Logs exceptions if necessary.
        """
        while True:
            time.sleep(60)
            now5m = time.time() - (5*60)
            for k in list(addresses.keys()):
                if addresses[k]["time"] < now5m:
                    logger.info("removing puncher id %s", k)
                    del addresses[k]

def addr_to_msg(uid, addr):
    return bytes(json.dumps({
        "punch_id": str(uid),
        "addr": addr[0],
        "port": addr[1]
    }), "utf-8")

def main(host='0.0.0.0', port=9999):
    cleaner = Cleaner()
    sock = socket.socket(socket.AF_INET, # Internet
                         socket.SOCK_DGRAM) # UDP
    sock.bind((host, port))
    logger.info("listening on %s:%d", host, port)
    while True:
        datastr, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
        logger.info("connection from: %s", addr)
        try:
            data = json.loads(datastr)
            if "punch_id" in data and isinstance(data["punch_id"], str):
                pid = data["punch_id"]
                logger.info("using punch id %s", pid)
                if pid in addresses:
                    addr2 = addresses[pid]["addr"]

                    logger.info("sending addr %s to %s", addr2, addr)
                    msg = addr_to_msg(pid, addr2)
                    sock.sendto(msg, addr)

                    logger.info("sending addr %s to %s", addr, addr2)
                    msg = addr_to_msg(pid, addr)
                    sock.sendto(msg, addr2)

                    del addresses[pid]
                else:
                    logger.info("saved addr %s", addr)
                    addresses[pid] = {
                        "addr": addr,
                        "time": time.time()
                    }
        except Exception as e:
            logger.exception("failed to process punch")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    main(port=6980)
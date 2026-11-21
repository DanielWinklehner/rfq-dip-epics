"""Fake device for the harness example: TCP port 5000, line protocol with LF.

    VAL?        -> the value, e.g. 42.5
    SET <x>     -> OK, and the value becomes x
"""
import socketserver

value = 42.5


class Device(socketserver.StreamRequestHandler):
    def handle(self):
        global value
        for line in self.rfile:
            cmd = line.decode().strip()
            print("rx", repr(cmd), flush=True)
            if cmd == "VAL?":
                reply = "%g" % value
            elif cmd.startswith("SET "):
                value = float(cmd[4:])
                reply = "OK"
            else:
                reply = "ERR"
            self.wfile.write((reply + "\n").encode())


socketserver.ThreadingTCPServer.allow_reuse_address = True
print("fake device listening on port 5000", flush=True)
socketserver.ThreadingTCPServer(("", 5000), Device).serve_forever()

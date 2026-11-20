import socket
import struct
import uasyncio as asyncio

class MQTTAsyncClient:
    def _init_(self, client_id, host, port=1883, user="", password="", keepalive=30):
        self.client_id = client_id.encode()
        self.host = host
        self.port = port
        self.user = user.encode() if user else b""
        self.password = password.encode() if password else b""
        self.keepalive = keepalive
        self.sock = None
        self.pkt_id = 0

    def _encode_len(self, length):
        out = bytearray()
        while True:
            byte = length % 128
            length //= 128
            if length > 0:
                byte |= 0x80
            out.append(byte)
            if length == 0:
                break
        return out

    async def connect(self):
        self.close()
        addr = socket.getaddrinfo(self.host, self.port)[0][-1]
        self.sock = socket.socket()
        self.sock.setblocking(False)
        try:
            self.sock.connect(addr)
        except OSError:
            pass
        await asyncio.sleep_ms(200)

        flags = 0x02  # Clean session
        payload = struct.pack("!H", len(self.client_id)) + self.client_id
        if self.user:
            flags |= 0x80
            payload += struct.pack("!H", len(self.user)) + self.user
        if self.password:
            flags |= 0x40
            payload += struct.pack("!H", len(self.password)) + self.password

        var_header = b"\x00\x04MQTT\x04" + bytes([flags]) + struct.pack("!H", self.keepalive)
        pkt = b"\x10" + self._encode_len(len(var_header) + len(payload)) + var_header + payload
        await self._send_all(pkt)

        resp = await self._recv_exact(4)
        if resp[0] != 0x20 or resp[3] != 0x00:
            raise OSError("CONNACK invalido")

    async def publish_qos1(self, topic, msg):
        if not self.sock:
            raise OSError("Desconectado")
        self.pkt_id = (self.pkt_id % 65535) + 1
        t_bytes = topic.encode()
        m_bytes = msg.encode() if isinstance(msg, str) else msg

        var_header = struct.pack("!H", len(t_bytes)) + t_bytes + struct.pack("!H", self.pkt_id)
        pkt = b"\x32" + self._encode_len(len(var_header) + len(m_bytes)) + var_header + m_bytes
        await self._send_all(pkt)

        ack = await self._recv_exact(4)
        if ack[0] != 0x40 or ack[1] != 0x02 or struct.unpack("!H", ack[2:4])[0] != self.pkt_id:
            raise OSError("PUBACK invalido")

    async def _send_all(self, data):
        mv = memoryview(data)
        sent = 0
        for _ in range(30):  # timeout ~3s
            try:
                n = self.sock.send(mv[sent:])
                if n:
                    sent += n
                    if sent >= len(data):
                        return
            except OSError:
                pass
            await asyncio.sleep_ms(100)
        raise OSError("Timeout envio MQTT")

    async def _recv_exact(self, size):
        buf = bytearray()
        for _ in range(30):  # timeout ~3s
            try:
                chunk = self.sock.recv(size - len(buf))
                if chunk == b"":
                    raise OSError("Socket fechado")
                if chunk:
                    buf.extend(chunk)
                    if len(buf) >= size:
                        return bytes(buf)
            except OSError as e:
                if e.args and e.args[0] == 104:
                    raise
            await asyncio.sleep_ms(100)
        raise OSError("Timeout leitura MQTT")

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

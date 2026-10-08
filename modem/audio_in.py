#!/usr/bin/env python3
"""
2400-baud FSK audio modem for raw text over an audio cable (PC1 line-out -> PC2 mic/line-in).

Multi-frame, per-frame resync, Reed-Solomon error correction (built in, no extra
package), CRC16 per frame. No compression. Needs numpy; sounddevice only for live audio.

  python audiomodem2400.py send "hello" --wav msg.wav        # write WAV
  python audiomodem2400.py send @story.txt --play --repeat 2 # play now, send twice
  python audiomodem2400.py recv --wav msg.wav                # decode a recording
  python audiomodem2400.py recv --live 90                    # record 90 s from mic, decode
  python audiomodem2400.py test                              # self-test (noise, drift, bursts)
"""
import sys, wave, argparse, binascii
import numpy as np

# ---------------- modem parameters ----------------
FS = 48000                    # sample rate (set the sound cards to 48 kHz too)
BAUD = 2400
SPB = FS // BAUD              # 20 samples per bit (integer on purpose)
F1, F0 = 7200.0, 4800.0       # mark (1) / space (0): 3 and 2 cycles per bit, orthogonal
SYNC = 0xB4E1A55A
PREAMBLE = [1, 0] * 8
PAYLOAD = 200                 # text bytes per frame
NSYM = 16                     # RS parity bytes per frame (fixes up to 8 bad bytes)
HEADER = 5                    # seq(2) total(2) len(1)


# ---------------- Reed-Solomon over GF(256), poly 0x11d ----------------
EXP, LOG = [0] * 512, [0] * 256
_x = 1
for _i in range(255):
    EXP[_i] = _x; LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    EXP[_i] = EXP[_i - 255]


def gmul(a, b):
    return 0 if a == 0 or b == 0 else EXP[LOG[a] + LOG[b]]


def gdiv(a, b):
    return 0 if a == 0 else EXP[(LOG[a] - LOG[b]) % 255]


def _gen_poly(nsym):
    g = [1]                                   # highest degree first
    for i in range(nsym):
        r, ng = EXP[i], [0] * (len(g) + 1)
        for j, c in enumerate(g):
            ng[j] ^= c
            ng[j + 1] ^= gmul(c, r)
        g = ng
    return g


_GEN = _gen_poly(NSYM)


def rs_encode(msg: bytes) -> bytes:
    rem = [0] * NSYM
    for m in msg:
        f = m ^ rem[0]
        rem = rem[1:] + [0]
        if f:
            for i in range(NSYM):
                rem[i] ^= gmul(_GEN[i + 1], f)
    return bytes(msg) + bytes(rem)


def rs_decode(cw: bytes):
    """Return corrected message bytes (without parity) or None if uncorrectable."""
    n = len(cw)
    cw = list(cw)
    synd = []
    for j in range(NSYM):
        s = 0
        for c in cw:
            s = gmul(s, EXP[j]) ^ c
        synd.append(s)
    if not any(synd):
        return bytes(cw[:-NSYM])
    # Berlekamp-Massey (polynomials lowest degree first)
    C, B, L, m, b = [1], [1], 0, 1, 1
    for k in range(NSYM):
        d = synd[k]
        for i in range(1, L + 1):
            if i < len(C):
                d ^= gmul(C[i], synd[k - i])
        if d == 0:
            m += 1
            continue
        T = C[:]
        coef = gdiv(d, b)
        C = C + [0] * (len(B) + m - len(C))
        for i, bc in enumerate(B):
            C[i + m] ^= gmul(coef, bc)
        if 2 * L <= k:
            L, B, b, m = k + 1 - L, T, d, 1
        else:
            m += 1
    if L > NSYM // 2:
        return None
    # Chien search
    pos = []
    for i in range(n):
        xinv = EXP[(255 - (n - 1 - i)) % 255]
        v, xp = 0, 1
        for c in C[:L + 1]:
            v ^= gmul(c, xp)
            xp = gmul(xp, xinv)
        if v == 0:
            pos.append(i)
    if len(pos) != L:
        return None
    # Forney: omega = synd * C mod x^NSYM
    omega = [0] * NSYM
    for i in range(NSYM):
        for j in range(min(i + 1, len(C))):
            omega[i] ^= gmul(C[j], synd[i - j])
    for i in pos:
        X = EXP[n - 1 - i]
        xinv = EXP[(255 - (n - 1 - i)) % 255]
        om, xp = 0, 1
        for c in omega:
            om ^= gmul(c, xp); xp = gmul(xp, xinv)
        dv = 0                                 # formal derivative of C at xinv (odd terms only)
        for j in range(1, min(L, len(C) - 1) + 1, 2):
            dv ^= gmul(C[j], EXP[(LOG[xinv] * (j - 1)) % 255])
        if dv == 0:
            return None
        cw[i] ^= gmul(X, gdiv(om, dv))
    for j in range(NSYM):                       # verify
        s = 0
        for c in cw:
            s = gmul(s, EXP[j]) ^ c
        if s:
            return None
    return bytes(cw[:-NSYM])


# ---------------- bits / frames ----------------
def to_bits(data: bytes):
    return [(b >> i) & 1 for b in data for i in range(7, -1, -1)]


def from_bits(bits):
    return bytes(int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits) - len(bits) % 8, 8))


SYNC_BITS = to_bits(SYNC.to_bytes(4, "big"))
BODY_LEN = HEADER + PAYLOAD + 2               # + CRC16
CW_LEN = BODY_LEN + NSYM
FRAME_BITS = 8 * CW_LEN


def build_frames(data: bytes):
    chunks = [data[i:i + PAYLOAD] for i in range(0, len(data), PAYLOAD)] or [b""]
    total = len(chunks)
    if total > 65535:
        raise ValueError("message too long")
    out = []
    for seq, ch in enumerate(chunks):
        body = (seq.to_bytes(2, "big") + total.to_bytes(2, "big") + bytes([len(ch)])
                + ch.ljust(PAYLOAD, b"\0"))
        body += binascii.crc_hqx(body, 0xFFFF).to_bytes(2, "big")
        out.append(PREAMBLE + SYNC_BITS + to_bits(rs_encode(body)))
    return out


def modulate(bits, amp=0.3, lead=0.5):
    freqs = np.repeat(np.where(np.array(bits) == 1, F1, F0), SPB)
    sig = amp * np.sin(2 * np.pi * np.cumsum(freqs) / FS)
    pad = np.zeros(int(lead * FS))
    return np.concatenate([pad, sig, pad])


def encode_message(text_or_bytes, repeat=1, amp=0.3):
    data = text_or_bytes if isinstance(text_or_bytes, bytes) else text_or_bytes.encode("utf-8")
    bits = []
    for _ in range(repeat):
        for f in build_frames(data):
            bits += f
    return modulate(bits, amp)


# ---------------- receiver ----------------
def soft_values(x):
    t = np.arange(len(x)) / FS
    out = []
    for f in (F0, F1):
        z = x * np.exp(-2j * np.pi * f * t)
        c = np.concatenate([[0], np.cumsum(z)])
        out.append(np.abs(c[SPB:] - c[:-SPB]))
    return out[1] - out[0]


def decode_frames(x):
    """Return (message_bytes_or_None, info dict)."""
    x = np.asarray(x, dtype=float)
    x = x - np.mean(x)
    soft = soft_values(x)
    sign = np.array([1 if b else -1 for b in SYNC_BITS])
    n = len(soft) - SPB * len(SYNC_BITS) - SPB * FRAME_BITS
    info = {"frames_ok": 0, "frames_bad": 0, "total": None, "missing": None}
    if n <= 0:
        return None, info
    score = np.zeros(n)
    for k, s in enumerate(sign):
        score += s * soft[k * SPB: k * SPB + n]
    thr = 0.5 * score.max()
    got, total, pos = {}, None, 0
    while pos < n:
        above = np.nonzero(score[pos:] > thr)[0]
        if len(above) == 0:
            break
        i0 = pos + int(above[0])
        i = i0 + int(np.argmax(score[i0:i0 + 2 * SPB]))
        start = i + SPB * len(SYNC_BITS)
        idx = start + np.arange(FRAME_BITS) * SPB
        if idx[-1] >= len(soft):
            break
        bits = (soft[idx] > 0).astype(int).tolist()
        body = rs_decode(from_bits(bits))
        ok = False
        if body is not None and binascii.crc_hqx(body[:-2], 0xFFFF).to_bytes(2, "big") == body[-2:]:
            seq = int.from_bytes(body[0:2], "big"); tot = int.from_bytes(body[2:4], "big")
            ln = body[4]
            if ln <= PAYLOAD and seq < tot:
                got[seq] = body[HEADER:HEADER + ln]
                total, ok = tot, True
        if ok:
            info["frames_ok"] += 1
            pos = start + SPB * FRAME_BITS - SPB * 4
        else:
            info["frames_bad"] += 1
            pos = i + SPB * 8
    info["total"] = total
    if total is None:
        return None, info
    info["missing"] = [s for s in range(total) if s not in got]
    return b"".join(got.get(s, b"?" * PAYLOAD) for s in range(total)), info


# ---------------- audio I/O ----------------
def write_wav(path, sig):
    pcm = (np.clip(sig, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(FS)
        w.writeframes(pcm.tobytes())


def read_wav(path):
    with wave.open(path, "rb") as w:
        if w.getframerate() != FS:
            raise ValueError(f"WAV must be {FS} Hz")
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
        if w.getnchannels() > 1:
            raw = raw.reshape(-1, w.getnchannels())[:, 0]
    return raw / 32768.0


def report(data, info):
    if data is None:
        print("No valid frames found."); return
    print(f"frames ok: {info['frames_ok']} / {info['total']}  (rejected: {info['frames_bad']})")
    if info["missing"]:
        print("MISSING frames:", info["missing"], "- ask sender to repeat (--repeat 2)")
    print("--- message ---")
    print(data.decode("utf-8", errors="replace"))


# ---------------- self-test ----------------
def selftest():
    rng = np.random.default_rng(1)
    # 1) Reed-Solomon
    for ne in (0, 1, 8):
        msg = bytes(rng.integers(0, 256, BODY_LEN).tolist())
        cw = bytearray(rs_encode(msg))
        for p in rng.choice(len(cw), ne, replace=False):
            cw[p] ^= int(rng.integers(1, 256))
        assert rs_decode(bytes(cw)) == msg, f"RS failed with {ne} errors"
    cw = bytearray(rs_encode(msg))
    for p in range(12):
        cw[p] ^= 0x5A
    assert rs_decode(bytes(cw)) in (None, msg) 
    print("RS ok (0/1/8 errors corrected, 12 errors not silently wrong)")
    # 2) Modem round trips
    text = ("The quick brown fox jumps over the lazy dog. " * 340)[:15000]
    sig = encode_message(text)
    print(f"15000 chars -> {len(sig) / FS:.1f} s of audio ({15000 / (len(sig) / FS) * 60:.0f} chars/min)")
    noisy = sig + rng.normal(0, 0.15, len(sig))
    d, i = decode_frames(noisy); print("noise     :", d.decode() == text, i["frames_ok"], "/", i["total"])
    ratio = 1.0001                                            # 100 ppm clock mismatch
    t = np.arange(int(len(sig) / ratio)) * ratio
    d, i = decode_frames(np.interp(t, np.arange(len(sig)), sig)); print("100ppm    :", d.decode() == text)
    burst = sig.copy(); burst[100000:100000 + 1200] = 0       # 25 ms dropout
    d, i = decode_frames(burst); print("dropout   :", d is not None and d.decode() == text, "missing", i["missing"])
    sig3 = encode_message("héllo ✓ short one")
    d, i = decode_frames(sig3); print("short utf8:", d.decode())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("send"); s.add_argument("text", help="text or @file.txt")
    s.add_argument("--wav"); s.add_argument("--play", action="store_true")
    s.add_argument("--repeat", type=int, default=1); s.add_argument("--amp", type=float, default=0.3)
    r = sub.add_parser("recv"); r.add_argument("--wav"); r.add_argument("--live", type=float, help="seconds to record")
    sub.add_parser("test")
    a = ap.parse_args()
    if a.cmd == "send":
        txt = open(a.text[1:], "rb").read() if a.text.startswith("@") else a.text
        sig = encode_message(txt, a.repeat, a.amp)
        print(f"audio length: {len(sig) / FS:.1f} s")
        if a.wav:
            write_wav(a.wav, sig); print("wrote", a.wav)
        if a.play:
            import sounddevice as sd
            sd.play(sig.astype("float32"), FS); sd.wait()
        if not a.wav and not a.play:
            print("use --wav FILE and/or --play")
    elif a.cmd == "recv":
        if a.live:
            import sounddevice as sd
            print(f"recording {a.live:.0f} s ...")
            x = sd.rec(int(a.live * FS), FS, channels=1, dtype="float32"); sd.wait(); x = x[:, 0]
        elif a.wav:
            x = read_wav(a.wav)
        else:
            sys.exit("use --wav FILE or --live SECONDS")
        report(*decode_frames(x))
    elif a.cmd == "test":
        selftest()
    else:
        ap.print_help()

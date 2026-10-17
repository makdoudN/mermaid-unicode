import random, subprocess, sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))
from mermaid_unicode.unicode_width import str_width, char_width
random.seed(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
interesting = [0x0A, 0x0D, 0x20, 0x41, 0x7F, 0xA0, 0xAD, 0x300, 0x34F, 0x5D0, 0x5DC, 0x622, 0x627, 0x644, 0x64B, 0x6B5, 0x76A, 0x8A6, 0x8C7,
    0x1780, 0x1781, 0x17A4, 0x17B4, 0x17D2, 0x17D8, 0x1A10, 0x1A15, 0x1A17, 0x200D, 0x20E3, 0x2D31, 0x2D65, 0x2D6F, 0x2D7F, 0x3000, 0x4E00,
    0xA4F8, 0xA4FB, 0xA4FC, 0xA4FD, 0xAC00, 0x1160, 0xFE0E, 0xFE0F, 0xFF21, 0x10C03, 0x10C32, 0x1F1E6, 0x1F1E7, 0x1F1FF, 0x1F3F4, 0x1F3FB, 0x1F3FF,
    0x1F468, 0x1F469, 0x1F466, 0x1F600, 0x2764, 0x2600, 0x231A, 0x23E9, 0x261D, 0x26F9, 0x270A, 0x1F385, 0x2A, 0x23, 0x30, 0x39, 0xE007F, 0xE0061, 0xE007A, 0xE0030, 0xE0039, 0xE0100,
    0x0338, 0x003C, 0x003D, 0x003E, 0x2122, 0x00A9, 0x00AE, 0x1F004, 0x1F0CF, 0x1F170, 0x1F1E6, 0x1F200, 0x1F201, 0x1F21A, 0x1F22F, 0x1F232, 0x1F250, 0x1F251, 0x0CC0, 0x1B3B, 0x0605, 0x070F, 0xA8FA, 0x115F, 0x0387]
cases = []
for _ in range(6000):
    n = random.randint(0, 8)
    cps = []
    for _ in range(n):
        r = random.random()
        if r < 0.7: cps.append(random.choice(interesting))
        elif r < 0.9: cps.append(random.randint(0x20, 0x3000))
        else:
            c = random.randint(0x20, 0x10FFFF)
            while 0xD800 <= c <= 0xDFFF: c = random.randint(0x20, 0x10FFFF)
            cps.append(c)
    cases.append(cps)
# also every single codepoint (sampled fully for BMP + SMP sample)
for cp in range(0x20, 0x30000):
    if 0xD800 <= cp <= 0xDFFF: continue
    if cp < 0x3400 or cp % 7 == 0: cases.append([cp])
inp = "\n".join(" ".join(f"{c:x}" for c in cps) for cps in cases) + "\n"
out = subprocess.run([__import__('os').environ.get('UWDUMP_BIN', '/private/tmp/claude-502/-Users-n-makdoud/f54d52cb-5ebc-483b-88cc-fdae8a830856/scratchpad/uwdump/uwdump'), 'strs'], input=inp, capture_output=True, text=True, check=True).stdout.split("\n")
bad = 0
for cps, exp in zip(cases, out):
    s = "".join(chr(c) for c in cps)
    got = str_width(s)
    if got != int(exp):
        bad += 1
        if bad <= 15: print("MISMATCH", [hex(c) for c in cps], "rust", exp, "py", got)
print("cases", len(cases), "mismatches", bad)

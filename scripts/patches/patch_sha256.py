#!/usr/bin/env python3
"""Replace KSU's crypto_shash based SHA-256 with a self-contained one.

Why: `crypto_alloc_shash()` returns a kernel object whose `struct crypto_shash`
layout comes from the *device* kernel. Inlined `crypto_free_shash()` computes
`&tfm->base` with OUR tree's offset, so the kernel's `crypto_destroy_tfm()`
reads a bogus `__crt_alg` and faults (observed: NULL read at 0x168,
lr=ksu_sha256+0xa0). The digest itself is fine - only the free explodes.

A local SHA-256 removes the dependency on that layout (and on sha256_generic
being loadable) entirely. The algorithm below is verified against hashlib.
"""
from pathlib import Path

P = Path("/data/local/tmp/build/bakasu/kernel/manager/apk_sign.c")
MARK = "static int ksu_sha256(const unsigned char *data"

IMPL = r'''
/*
 * Self-contained SHA-256.  The kernel crypto API's struct crypto_shash layout
 * does not match this tree, so crypto_free_shash() faults; do the hash here.
 */
static const u32 ksu_sha256_k[64] = {
	0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
	0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
	0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
	0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
	0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
	0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
	0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
	0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
	0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
	0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
	0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

#define KSU_ROR32(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

static void ksu_sha256_block(u32 *st, const u8 *p)
{
	u32 w[64];
	u32 a, b, c, d, e, f, g, h;
	int i;

	for (i = 0; i < 16; i++)
		w[i] = ((u32)p[i * 4] << 24) | ((u32)p[i * 4 + 1] << 16) |
		       ((u32)p[i * 4 + 2] << 8) | (u32)p[i * 4 + 3];
	for (i = 16; i < 64; i++) {
		u32 s0 = KSU_ROR32(w[i - 15], 7) ^ KSU_ROR32(w[i - 15], 18) ^
			 (w[i - 15] >> 3);
		u32 s1 = KSU_ROR32(w[i - 2], 17) ^ KSU_ROR32(w[i - 2], 19) ^
			 (w[i - 2] >> 10);
		w[i] = w[i - 16] + s0 + w[i - 7] + s1;
	}

	a = st[0]; b = st[1]; c = st[2]; d = st[3];
	e = st[4]; f = st[5]; g = st[6]; h = st[7];
	for (i = 0; i < 64; i++) {
		u32 s1 = KSU_ROR32(e, 6) ^ KSU_ROR32(e, 11) ^ KSU_ROR32(e, 25);
		u32 ch = (e & f) ^ (~e & g);
		u32 t1 = h + s1 + ch + ksu_sha256_k[i] + w[i];
		u32 s0 = KSU_ROR32(a, 2) ^ KSU_ROR32(a, 13) ^ KSU_ROR32(a, 22);
		u32 maj = (a & b) ^ (a & c) ^ (b & c);
		u32 t2 = s0 + maj;

		h = g; g = f; f = e; e = d + t1;
		d = c; c = b; b = a; a = t1 + t2;
	}
	st[0] += a; st[1] += b; st[2] += c; st[3] += d;
	st[4] += e; st[5] += f; st[6] += g; st[7] += h;
}

static int ksu_sha256_sw(const u8 *data, unsigned int len, u8 *out)
{
	u32 st[8] = { 0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
		      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19 };
	u8 tail[128];
	unsigned int full = len / 64, rem = len % 64, tlen, i;
	u64 bits = (u64)len * 8;

	for (i = 0; i < full; i++)
		ksu_sha256_block(st, data + i * 64);

	tlen = (rem < 56) ? 64 : 128;
	memset(tail, 0, tlen);
	if (rem)
		memcpy(tail, data + full * 64, rem);
	tail[rem] = 0x80;
	for (i = 0; i < 8; i++)
		tail[tlen - 1 - i] = (u8)(bits >> (8 * i));

	ksu_sha256_block(st, tail);
	if (tlen == 128)
		ksu_sha256_block(st, tail + 64);

	for (i = 0; i < 8; i++) {
		out[i * 4] = (u8)(st[i] >> 24);
		out[i * 4 + 1] = (u8)(st[i] >> 16);
		out[i * 4 + 2] = (u8)(st[i] >> 8);
		out[i * 4 + 3] = (u8)st[i];
	}
	return 0;
}

'''

NEWFN = """static int ksu_sha256(const unsigned char *data, unsigned int datalen, unsigned char *digest)
{
	return ksu_sha256_sw(data, datalen, digest);
}
"""


def main() -> int:
    src = P.read_text()
    if "ksu_sha256_sw" in src:
        print("already patched")
        return 0
    i = src.index(MARK)
    # the function has no column-0 closing brace inside, so the first "\n}\n"
    # after the header is its own.
    j = src.index("\n}\n", i) + len("\n}\n")
    P.write_text(src[:i] + IMPL.lstrip("\n") + NEWFN + src[j:])
    print("sha256 replaced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

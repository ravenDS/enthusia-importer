# Enthusia importer
# Blender 4.2+ importer for Enthusia Professional Racing (PS2) car and course models
#
# https://github.com/ravenDS
#
# accepted files:
#   pack/carpk/NNNNNNNN.pkd and pack/selcarpk/NNNNNNNN.pkd: car packs (sub-entry 0 is car.vgs, car spec places wheels)
#   pack/mappk/NNN_00.pkd: course packs (sub-entry 0 holds BG06 scene and GS02 streamed texture pages)
#   a bare car.vgs or course 0000.bin (PC container)
#
# all formats are traced from SLUS-209.67 executable
#   CA06 geometry: 16-node LOD sets, packets drawn in up to 4 passes (base + overlays) with VIF-unpacked pools and V4-16 strip records whose w is baked per-vertex shade
#   GS02 textures: one PSMCT32 upload, PSMT4/PSMT8 records with CLUTs, body paint map being an ordinary PSMT4 texture
#   materials: each packet's draw program combines emitter 0x261E88 (groups, modes, paint slots, glass TEST override), VU1 program B (shade 128*(1-P)+w3*P, colour/alpha per routine, sphere and reflection-elevation mapping) and GS MODULATE/ALPHA/TEST/DATE composition
#   paint: car's colour table (selcarpk sub-entry 3) feeds setPaint 0x2616E8 vectors (base, env tint, sky tint, P) of each slot
#   runtime-only inputs (course env/sky renders, lamp colour, brake-glow index) are replaced by Glossy closures of world (LIT) or by "Enthusia Env" node group (GAME)
#   courses: BG06 nodes (sky dome, world-space scenery, object nodes with their placement matrix), packets of per-vertex VIF records (UV, position, ADC flag, RGBA) drawn by VU1 program A, materials from 64-byte BG material records (ALPHA/TEST/routine word), GS02 textures decoded from streamed 8 KB pages and course names from ELF tables

# add-on version
_VERSION = (1, 1, 0)

import struct

# decoder

PKD_MAGIC = 0x1000FC87

B32 = [[0,1,4,5,16,17,20,21],[2,3,6,7,18,19,22,23],
       [8,9,12,13,24,25,28,29],[10,11,14,15,26,27,30,31]]
B4  = [[0,2,8,10],[1,3,9,11],[4,6,12,14],[5,7,13,15],
       [16,18,24,26],[17,19,25,27],[20,22,28,30],[21,23,29,31]]
C32 = [[0,1,4,5,8,9,12,13],[2,3,6,7,10,11,14,15],
       [16,17,20,21,24,25,28,29],[18,19,22,23,26,27,30,31],
       [32,33,36,37,40,41,44,45],[34,35,38,39,42,43,46,47],
       [48,49,52,53,56,57,60,61],[50,51,54,55,58,59,62,63]]
C8 = [
 [0,4,16,20,32,36,48,52,2,6,18,22,34,38,50,54],
 [8,12,24,28,40,44,56,60,10,14,26,30,42,46,58,62],
 [33,37,49,53,1,5,17,21,35,39,51,55,3,7,19,23],
 [41,45,57,61,9,13,25,29,43,47,59,63,11,15,27,31],
 [96,100,112,116,64,68,80,84,98,102,114,118,66,70,82,86],
 [104,108,120,124,72,76,88,92,106,110,122,126,74,78,90,94],
 [65,69,81,85,97,101,113,117,67,71,83,87,99,103,115,119],
 [73,77,89,93,105,109,121,125,75,79,91,95,107,111,123,127],
 [128,132,144,148,160,164,176,180,130,134,146,150,162,166,178,182],
 [136,140,152,156,168,172,184,188,138,142,154,158,170,174,186,190],
 [161,165,177,181,129,133,145,149,163,167,179,183,131,135,147,151],
 [169,173,185,189,137,141,153,157,171,175,187,191,139,143,155,159],
 [224,228,240,244,192,196,208,212,226,230,242,246,194,198,210,214],
 [232,236,248,252,200,204,216,220,234,238,250,254,202,206,218,222],
 [193,197,209,213,225,229,241,245,195,199,211,215,227,231,243,247],
 [201,205,217,221,233,237,249,253,203,207,219,223,235,239,251,255]]
C4 = [
 [0,8,32,40,64,72,96,104,2,10,34,42,66,74,98,106,4,12,36,44,68,76,100,108,6,14,38,46,70,78,102,110],
 [16,24,48,56,80,88,112,120,18,26,50,58,82,90,114,122,20,28,52,60,84,92,116,124,22,30,54,62,86,94,118,126],
 [65,73,97,105,1,9,33,41,67,75,99,107,3,11,35,43,69,77,101,109,5,13,37,45,71,79,103,111,7,15,39,47],
 [81,89,113,121,17,25,49,57,83,91,115,123,19,27,51,59,85,93,117,125,21,29,53,61,87,95,119,127,23,31,55,63],
 [192,200,224,232,128,136,160,168,194,202,226,234,130,138,162,170,196,204,228,236,132,140,164,172,198,206,230,238,134,142,166,174],
 [208,216,240,248,144,152,176,184,210,218,242,250,146,154,178,186,212,220,244,252,148,156,180,188,214,222,246,254,150,158,182,190],
 [129,137,161,169,193,201,225,233,131,139,163,171,195,203,227,235,133,141,165,173,197,205,229,237,135,143,167,175,199,207,231,239],
 [145,153,177,185,209,217,241,249,147,155,179,187,211,219,243,251,149,157,181,189,213,221,245,253,151,159,183,191,215,223,247,255],
 [256,264,288,296,320,328,352,360,258,266,290,298,322,330,354,362,260,268,292,300,324,332,356,364,262,270,294,302,326,334,358,366],
 [272,280,304,312,336,344,368,376,274,282,306,314,338,346,370,378,276,284,308,316,340,348,372,380,278,286,310,318,342,350,374,382],
 [321,329,353,361,257,265,289,297,323,331,355,363,259,267,291,299,325,333,357,365,261,269,293,301,327,335,359,367,263,271,295,303],
 [337,345,369,377,273,281,305,313,339,347,371,379,275,283,307,315,341,349,373,381,277,285,309,317,343,351,375,383,279,287,311,319],
 [448,456,480,488,384,392,416,424,450,458,482,490,386,394,418,426,452,460,484,492,388,396,420,428,454,462,486,494,390,398,422,430],
 [464,472,496,504,400,408,432,440,466,474,498,506,402,410,434,442,468,476,500,508,404,412,436,444,470,478,502,510,406,414,438,446],
 [385,393,417,425,449,457,481,489,387,395,419,427,451,459,483,491,389,397,421,429,453,461,485,493,391,399,423,431,455,463,487,495],
 [401,409,433,441,465,473,497,505,403,411,435,443,467,475,499,507,405,413,437,445,469,477,501,509,407,415,439,447,471,479,503,511]]


# PSMT8 block arrangement within a 128x64 page (16x16-pixel blocks)
# it differs from PSMCT32 arrangement outside top-left quadrant
B8 = (
    (0, 1, 4, 5, 16, 17, 20, 21),
    (2, 3, 6, 7, 18, 19, 22, 23),
    (8, 9, 12, 13, 24, 25, 28, 29),
    (10, 11, 14, 15, 26, 27, 30, 31),
)


class _GSMem:
    def __init__(self):
        self.m = bytearray(4 * 1024 * 1024)

    def w32(self, bp, bw, x, y, v):
        page = bp // 32 + (y // 32) * bw + x // 64
        b = B32[(y % 32) // 8][(x % 64) // 8]
        w = C32[y % 8][x % 8]
        struct.pack_into('<I', self.m,
                         ((page * 2048 + (bp % 32) * 64 + b * 64 + w)
                          % (1024 * 1024)) * 4, v)

    def r32(self, bp, bw, x, y):
        page = bp // 32 + (y // 32) * bw + x // 64
        b = B32[(y % 32) // 8][(x % 64) // 8]
        w = C32[y % 8][x % 8]
        return struct.unpack_from(
            '<I', self.m,
            ((page * 2048 + (bp % 32) * 64 + b * 64 + w) % (1024 * 1024)) * 4)[0]

    def r8(self, bp, bw, x, y):
        pgw = max(1, bw // 2)
        page = bp // 32 + (y // 64) * pgw + x // 128
        b = B8[(y % 64) // 16][(x % 128) // 16]
        c = C8[y % 16][x % 16]
        return self.m[(page * 8192 + (bp % 32) * 256 + b * 256 + c)
                      % (4 * 1024 * 1024)]

    def r4(self, bp, bw, x, y):
        pgw = max(1, bw // 2)
        page = bp // 32 + (y // 128) * pgw + x // 128
        b = B4[(y % 128) // 16][(x % 128) // 32]
        n = C4[y % 16][x % 32]
        a = (page * 16384 + (bp % 32) * 512 + b * 512 + n) % (8 * 1024 * 1024)
        v = self.m[a >> 1]
        return (v >> 4) if (a & 1) else (v & 0xF)


def _clut8(mem, cbp, i):
    j = (i & 0xE7) | ((i & 0x10) >> 1) | ((i & 0x08) << 1)
    return mem.r32(cbp, 1, j % 16, j // 16)


def _clut4(mem, cbp, csa, i):
    return mem.r32(cbp, 1, i % 8 + (csa & 1) * 8, i // 8 + (csa >> 1) * 2)


def _rgba(v):
    a = (v >> 24) & 0xFF
    return (v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, min(255, a * 2))


def parse_pkd(data):
    """split a pkd archive into its sub-entries (None if data is not a pkd)

    header: magic 0x1000FC87, {u32 count, u32 start}, then one {u32 size, u32 end} pair per entry
    """
    if len(data) < 16 or struct.unpack_from('<I', data, 0)[0] != PKD_MAGIC:
        return None
    count, start = struct.unpack_from('<2I', data, 8)
    out, prev = [], start
    for k in range(1, count):
        size, end = struct.unpack_from('<2I', data, 8 + k * 8)
        out.append(data[prev:prev + size])
        prev = end
    return out


def find_spec(entries):
    """find car-spec sub-entry: plain floats [mass, len, width, height, wb, trackF, trackR, ...]"""
    for e in entries:
        if len(e) < 48:
            continue
        f = struct.unpack_from('<7f', e, 0)
        if 300 <= f[0] <= 4000 and 2.0 <= f[1] <= 7.0 and 1.0 <= f[2] <= 2.6 \
           and 0.8 <= f[3] <= 2.5 and 1.5 <= f[4] <= 4.5:
            return dict(mass=f[0], length=f[1], width=f[2], height=f[3],
                        wheelbase=f[4], track_f=f[5], track_r=f[6])
    return None


class VgsModel:
    kind = 'car'

    def __init__(self):
        self.gsmem = None     # filled by _parse_gs for re-slicing
        self.vram_base = 0
        self.shared_off = 0x200
        self.upload_blocks = 0
        self.warnings = []
        self.nodes = []       # dicts
        self.materials = []   # dicts
        self.textures = {}    # recIdx -> dict(w, h, rgba bytes top-down)
        self.composite = set()  # body paint-map record indices (info only)
        self.resident = {}      # recIdx -> dict(w, h, csa) for 0x3FFF records
        self.attach = []
        self.spec = None


def load_vgs(data):
    if data[:2] != b'PC':
        raise ValueError('not a PC container (bad magic)')
    offs = struct.unpack_from('<4I', data, 4)
    ca = bg = gs = None
    for o in offs:
        if not o or o + 4 > len(data):
            continue
        tag = data[o:o + 4]
        if tag == b'CA06':
            ca = o
        elif tag == b'BG06':
            bg = o
        elif tag[:2] == b'GS':
            gs = o
    if bg is not None:
        m = CourseModel()
        _parse_bg(data, bg, m)
        if gs is not None:
            _parse_gs_course(data, gs, m)
        return m
    if ca is None:
        raise ValueError('no CA06/BG06 chunk found')
    m = VgsModel()
    _parse_ca(data, ca, m)
    if gs is not None:
        _parse_gs(data, gs, m)
    return m


def _parse_ca(d, ca, m):
    ncount, mcount = struct.unpack_from('<2H', d, ca + 0x10)
    at_off = struct.unpack_from('<H', d, ca + 0x18)[0]
    mat_off = struct.unpack_from('<I', d, ca + 0x1C)[0]
    size = struct.unpack_from('<I', d, ca + 0x0C)[0]
    for i in range(mcount):
        r = ca + mat_off + i * 0x40
        m.materials.append(dict(
            tex=struct.unpack_from('<h', d, r + 2)[0],
            # +0x20: GS ALPHA register merged at draw time (out = (A-B)*C + D; 0x44 = standard blend, 0x48 = additive)
            alpha_reg=struct.unpack_from('<I', d, r + 0x20)[0],
            # q38 byte 3 low nibble != 0: TEX0 is replaced at load from runtime table at 0x383938 (reflection and resident targets)
            envmap=d[r + 0x3B] & 0x0F,
            # +4: not read by traced draw path, kept for reference
            mat4=d[r + 4],
            # q38 bits 8-11: VU1 routine selector (table 0x372720)
            # 0x0/0xF -> routine 0x7D: standard, UVs from file pool
            # 0xA -> routine 0x1C4: UVs computed on VU by sphere/reflection mapping of vertex normal, file UV pool is not sampled
            vu=(struct.unpack_from('<Q', d, r + 0x38)[0] >> 8) & 0xF,
            # q38 bit 12 -> ABE (bit 6 of GIF PRIM field)
            # alpha blending is enabled per material by this bit, not by texture alpha
            abe=(struct.unpack_from('<Q', d, r + 0x38)[0] >> 12) & 1,
            # +0x28: GS TEST register (ATE/ATST/AREF...), alpha-test definition
            test_reg=struct.unpack_from('<Q', d, r + 0x28)[0],
            # +5 (signed): paint slot 0-3, -1 = none
            # emitter 0x261E88 multiplies vertex colour by model+0x230 + slot*48 + mode*16 (VU0 vmul) and takes shade-blend parameter (VU qw0.w) from model+0x24C + slot*48
            paint=struct.unpack_from('<b', d, r + 5)[0],
            q38=struct.unpack_from('<Q', d, r + 0x38)[0],
            type=d[r + 0x38]))
        mm = m.materials[-1]
        # +6 "mode", rewritten by material merge 0x262D30 from VU nibble (jump table 0x48BBB0):
        #   0xA -> 1 (env, runtime TEX0 *(0x3854E0 + model->0x17E*8))
        #   0xB -> 3
        #   0xC -> file value kept
        #   0xD -> 2 (sky strip, TEX0 *(0x383930))
        #   0xF -> 5 (untextured)
        #   0x0-0x9 and 0xE -> 6 if env nibble is set (TEX0/TEX2 from 0x383938 + nibble*16), else 0
        nib = mm['vu']
        if nib in (0xA, 0xB, 0xD, 0xF):
            mm['mode'] = {0xA: 1, 0xB: 3, 0xD: 2, 0xF: 5}[nib]
        elif nib == 0xC:
            mm['mode'] = struct.unpack_from('<b', d, r + 6)[0]
        else:
            mm['mode'] = 6 if mm['envmap'] else 0
    for i in range(16):
        a = ca + at_off + 16 * i
        x, y, z = struct.unpack_from('<3f', d, a)
        code = struct.unpack_from('<I', d, a + 12)[0]
        if code:
            m.attach.append((x, y, z, code))
    geos = []
    raw = []
    for i in range(ncount):
        n = ca + 0x20 + i * 0x100
        geo = struct.unpack_from('<I', d, n)[0]
        flags = struct.unpack_from('<H', d, n + 0x0C)[0]
        mtx = [struct.unpack_from('<4f', d, n + 0x40 + 16 * r) for r in range(4)]
        bmin = struct.unpack_from('<3f', d, n + 0x80)
        bmax = struct.unpack_from('<3f', d, n + 0x90)
        raw.append((i, geo, flags, mtx, bmin, bmax))
        if geo:
            geos.append(geo)
    geos.append(size)
    geos.sort()
    for i, geo, flags, mtx, bmin, bmax in raw:
        meshes = _parse_geo(d, ca, geo, geos[geos.index(geo) + 1]) if geo else []
        m.nodes.append(dict(index=i, flags=flags, matrix=mtx,
                            bbox_min=bmin, bbox_max=bmax, meshes=meshes))


def _parse_geo(d, ca, geo, end):
    meshes = []
    o = ca + geo
    stop = ca + end
    while o + 0x20 <= stop:
        qwc, t2, t3, mat = struct.unpack_from('<HBBh', d, o)
        # packet header (main emitter 0x261E88): byte 2 == 0xFF ends list
        # byte 3 is number of passes drawn over this geometry, with their material indices at +4, +6, +8, +10 (unused = -1)
        # pass 0 is base material, later passes are overlays (reflection, lamp/state layers) drawn over same vertices
        if t2 == 0xFF or t3 == 0xFF or mat < 0:
            break
        passes = [struct.unpack_from('<h', d, o + 4 + 2 * k)[0]
                  for k in range(min(t3, 4))]
        passes = [x for x in passes if x >= 0]
        p = o + 0x20
        pend = p + qwc * 16
        pool_v = pool_n = pool_u = None
        cur = None
        while p < pend - 3:
            w = struct.unpack_from('<I', d, p)[0]
            cmd = (w >> 24) & 0x7F
            num = (w >> 16) & 0xFF
            imm = w & 0xFFFF
            p += 4
            if cmd >= 0x60:
                vn = (cmd >> 2) & 3
                vl = cmd & 3
                n = num or 256
                bits = (32, 16, 8, 5)[vl]
                comps = vn + 1
                sz = ((2 * n if bits == 5 else (comps * bits // 8) * n) + 3) // 4 * 4
                addr = imm & 0x3FF
                flg = (imm >> 15) & 1
                if comps == 4 and bits == 32 and addr == 0x3FF:
                    pool_v = pool_n = pool_u = None
                elif comps == 3 and bits == 32:
                    pool_v = [struct.unpack_from('<3f', d, p + 12 * i)
                              for i in range(n)]
                elif comps == 3 and bits == 16:
                    # VU converts these with ITOF15 (divide by 32768)
                    pool_n = [tuple(c / 32768.0 for c in
                                    struct.unpack_from('<3h', d, p + 6 * i))
                              for i in range(n)]
                elif comps == 2 and bits == 32:
                    pool_u = [struct.unpack_from('<2f', d, p + 8 * i)
                              for i in range(n)]
                elif comps == 4 and bits == 16 and flg and pool_v:
                    if cur is None or cur['verts'] is not pool_v:
                        cur = dict(verts=pool_v, norms=pool_n, uvs=pool_u,
                                   faces=[], passes=passes)
                        meshes.append((mat, cur))
                    run = 0
                    r2 = r1 = None
                    for i in range(n):
                        rec = struct.unpack_from('<4H', d, p + 8 * i)
                        if (rec[0] >> 15) & 1:
                            run = 0
                            r2, r1 = r1, rec
                            continue
                        run += 1
                        a, b, c = r2, r1, rec
                        # 4th element: record's w field, per-vertex shade (VU routine 0x7D: RGB = matcolor * w3, 128 = neutral)
                        # body pools carry 128, glass and lamp pools carry baked per-vertex shading
                        tri = tuple((r[0] & 0xFFF, r[1] & 0xFFF,
                                     r[2] & 0xFFF, r[3] & 0xFF)
                                    for r in (a, b, c))
                        # stored normals are opposite to drawn winding (screen-space culling handedness)
                        # this parity gives visible side, so winding does not follow normals
                        if run & 1 == 0:
                            tri = (tri[0], tri[2], tri[1])
                        cur['faces'].append(tri)
                        r2, r1 = r1, rec
                p += sz
        o = pend
    out = []
    for mat, cur in meshes:
        if cur['faces']:
            out.append(dict(material=mat, verts=cur['verts'],
                            norms=cur['norms'], uvs=cur['uvs'],
                            faces=cur['faces'], passes=cur['passes']))
    return out


def _parse_gs(d, gs, m):
    cnt = struct.unpack_from('<h', d, gs + 4)[0]
    # gs+0x06: record base offset within upload
    # relocator adds it to every record while upload's DBP only gets area base (upload builder 0x263058)
    # gs+0x0C: offset of flagged (PSMT8/shared) region within upload, in blocks (set per car)
    m.vram_base = struct.unpack_from('<h', d, gs + 6)[0]
    m.shared_off = struct.unpack_from('<H', d, gs + 0x0C)[0]
    img = struct.unpack_from('<I', d, gs + 0x10)[0]
    b = gs + img
    rrw, rrh = struct.unpack_from('<2I', d, b + 0x40)
    # report truncated uploads
    expected = rrw * rrh * 4
    avail = len(d) - (b + 0x70)
    m.upload_blocks = expected // 256
    if avail < expected:
        m.warnings.append(
            'texture stream truncated: the upload declares %dx%d (%d bytes, '
            '%d blocks) but only %d bytes remain in the file, textures in '
            'the missing part will not decode correctly'
            % (rrw, rrh, expected, expected // 256, max(avail, 0)))
    mem = _GSMem()
    n = 0
    blob = d[b + 0x70:b + 0x70 + rrw * rrh * 4]
    if len(blob) < rrw * rrh * 4:
        return
    for y in range(rrh):
        for x in range(rrw):
            mem.w32(0, 1, x, y, struct.unpack_from('<I', blob, n)[0])
            n += 4
    for i in range(cnt):
        r = gs + 0x20 + i * 48
        clut_slot = d[r + 2]
        flag = d[r + 0xF]
        w, h = struct.unpack_from('<2H', d, r + 8)
        q10 = struct.unpack_from('<Q', d, r + 0x10)[0]
        q20 = struct.unpack_from('<Q', d, r + 0x20)[0]
        tbp = q10 & 0x3FFF
        tbw = max(2, (q10 >> 14) & 0x3F)
        psm = (q10 >> 20) & 0x3F
        if tbp == 0x3FFF:
            # runtime-resident record: keep its size and CSA for pvram_001 glass-variant binding
            # CSA indexes five {64x64 gradient + 32x32 flat} window pairs
            q20r = struct.unpack_from('<Q', d, r + 0x20)[0]
            # q20 of a resident record is a PSMT8 (256-colour) CLUT-load TEX0 with a per-record CBP into car's palette area
            # resident textures are shared 8-bit indices tinted through per-car palettes
            # runtime index/palette transform is not traced yet
            m.resident[i] = dict(w=w, h=h, csa=(q10 >> 56) & 0x1F,
                                 cbp=(q20r >> 37) & 0x3FFF,
                                 cpsm=(q20r >> 20) & 0x3F)
            continue
        if not (0 < w <= 512 and 0 < h <= 512):
            continue
        blocks = w * h // (512 if psm == 0x14 else 256)
        if not flag and tbp < 0x40 and blocks >= 64:
            # big unflagged record at start of upload is body paint map (PSMT4, grey ramp + alpha ramp CLUT)
            # it is an ordinary texture whose 4-bit texels overlay atlas bytes (GS reads same VRAM as PSMT4)
            # it is drawn with MODULATE by paint colour, and its alpha becomes framebuffer alpha that weights reflection passes
            m.composite.add(i)
        out = bytearray(w * h * 4)
        k = 0
        if psm == 0x14:                                    # PSMT4
            if flag:
                cbp = (q10 >> 37) & 0x3FFF
                base = tbp + m.vram_base + m.shared_off
            else:
                cbp = (q20 >> 37) & 0x3FFF
                base = tbp + m.vram_base
            if m.upload_blocks and base + blocks > m.upload_blocks:
                m.warnings.append(
                    'rec%02d (%dx%d psm=%02X, flag=%d): VRAM span '
                    '[0x%X..0x%X) extends beyond the %d uploaded blocks, '
                    'partly decoded from unwritten memory'
                    % (i, w, h, psm, flag, base, base + blocks,
                       m.upload_blocks))
            pal = [_rgba(_clut4(mem, cbp, clut_slot >> 4, c)) for c in range(16)]
            for y in range(h):
                for x in range(w):
                    out[k:k + 4] = bytes(pal[mem.r4(base, tbw, x, y)])
                    k += 4
        elif psm == 0x13:                                  # PSMT8
            if flag:
                cbp = (q10 >> 37) & 0x3FFF
                base = tbp + m.vram_base + m.shared_off
            else:
                cbp = (q20 >> 37) & 0x3FFF
                base = tbp + m.vram_base
            if m.upload_blocks and base + blocks > m.upload_blocks:
                m.warnings.append(
                    'rec%02d (%dx%d psm=%02X, flag=%d): VRAM span '
                    '[0x%X..0x%X) extends beyond the %d uploaded blocks, '
                    'partly decoded from unwritten memory'
                    % (i, w, h, psm, flag, base, base + blocks,
                       m.upload_blocks))
            pal = [_rgba(_clut8(mem, cbp, c)) for c in range(256)]
            for y in range(h):
                for x in range(w):
                    out[k:k + 4] = bytes(pal[mem.r8(base, tbw, x, y)])
                    k += 4
        else:
            continue
        m.textures[i] = dict(w=w, h=h, rgba=bytes(out), psm=psm,
                             tbp=base, tbw=tbw, cbp=cbp,
                             csa=clut_slot >> 4)
    m.gsmem = mem


def texture_with_slice(model, rec_idx, csa):
    """decode a PSMT4 texture again through another CLUT slice (CSA)

    used by materials with a slice override (light on/off variants)
    """
    t = model.textures.get(rec_idx)
    if t is None or model.gsmem is None or t['psm'] != 0x14 or csa == t['csa']:
        return t
    mem = model.gsmem
    pal = [_rgba(_clut4(mem, t['cbp'], csa, c)) for c in range(16)]
    w, h = t['w'], t['h']
    out = bytearray(w * h * 4)
    k = 0
    for y in range(h):
        for x in range(w):
            out[k:k + 4] = bytes(pal[mem.r4(t['tbp'], t['tbw'], x, y)])
            k += 4
    return dict(w=w, h=h, rgba=bytes(out), psm=t['psm'], tbp=t['tbp'],
                tbw=t['tbw'], cbp=t['cbp'], csa=csa)


ABCD_MAGIC = b'ABCD'


# car materials whose q38 byte 3 low nibble (env nibble) is set get TEX0/TEX2 from runtime table at 0x383938
# 0x261310 fills that table from loaded pvram_000 ABCD file (*(0x142E60()+0x1020) + 0x20 + idx*32, qwords +0x10/+0x18) with these entry indices
# material's own texture record is replaced, so its size is never used
PVRAM_NIBBLE_ENTRY = {1: 43, 2: 44, 3: 45, 4: 46, 5: 47, 6: 48, 7: 49,
                      8: 36, 9: 35}


def parse_pvram(data):
    """parse etc/etc/pvram_000_a.bin, boot-resident common texture atlas

    ABCD container: +0x00 'ABCD', +0x08 u32 data offset, +0x0C u32 data size, +0x10 u32 entry count
    entries (32 bytes at +0x20): {u16 x, y, w, h, u16 id, u16 flags, u16 count, u16, u64 TEX0 template, u64 TEX2 (CLUT load) template}
    payload: a 640x448 PSMT8H upload (indices in high byte of CT32 words, T4HL/T4HH entries use its low/high nibble), followed by a 64x64 PSMCT32 CLUT sheet
    8-bit entries take their 256-colour CLUT from TEX0.CBP
    4-bit entries load 256-colour CLUT at TEX2.CBP and read 16-colour slice selected by TEX0.CSA (colour = CLUT8[CSA*16 + nibble])
    entries decode in full colour
    """
    if data[:4] != ABCD_MAGIC:
        return None
    cnt = struct.unpack_from('<I', data, 0x10)[0]
    hdr = 0x20 + cnt * 32
    rrw, rrh = struct.unpack_from('<2I', data, hdr + 0x40)
    pay = data[hdr + 0x70: hdr + 0x70 + rrw * rrh]
    if len(pay) < rrw * rrh:
        return None
    # second upload: CLUT sheet (same 0x70-byte header layout)
    mem = None
    c0 = hdr + 0x70 + rrw * rrh
    if c0 + 0x70 <= len(data):
        cw, ch = struct.unpack_from('<2I', data, c0 + 0x40)
        if 0 < cw <= 1024 and 0 < ch <= 1024 \
                and c0 + 0x70 + cw * ch * 4 <= len(data):
            mem = _GSMem()
            cd = data[c0 + 0x70: c0 + 0x70 + cw * ch * 4]
            bw = max(1, cw // 64)
            k = 0
            for yy in range(ch):
                for xx in range(cw):
                    mem.w32(0, bw, xx, yy, struct.unpack_from('<I', cd, k)[0])
                    k += 4
    out = []
    for i in range(cnt):
        e = 0x20 + 32 * i
        x, y, w, h, ident, flags = struct.unpack_from('<6H', data, e)
        q0, q1 = struct.unpack_from('<2Q', data, e + 16)
        psm = (q0 >> 20) & 0x3F
        csa = (q0 >> 56) & 0x1F
        cbp = ((q1 if (psm in (0x24, 0x2C) and q1) else q0) >> 37) & 0x3FFF
        if not (0 < w <= rrw and 0 < h <= rrh and x + w <= rrw and y + h <= rrh):
            continue
        pal = None
        if mem is not None:
            pal = [bytes(_rgba(_clut8(mem, cbp, c))) for c in range(256)]
        px = bytearray(w * h * 4)
        k = 0
        for yy in range(y, y + h):
            row = pay[yy * rrw:]
            for xx in range(x, x + w):
                b = row[xx]
                if psm == 0x24:      # PSMT4HL: low nibble
                    idx = csa * 16 + (b & 0x0F)
                elif psm == 0x2C:    # PSMT4HH: high nibble
                    idx = csa * 16 + (b >> 4)
                else:                # PSMT8H
                    idx = b
                if pal is not None:
                    px[k:k + 4] = pal[idx & 0xFF]
                else:
                    v = (idx & 0x0F) * 17 if psm in (0x24, 0x2C) else idx
                    px[k:k + 4] = bytes((v, v, v, 255))
                k += 4
        out.append(dict(index=i, ident=ident, flags=flags, psm=psm, csa=csa,
                        w=w, h=h, rgba=bytes(px), colour=pal is not None))
    return out


# ---------------------------------------------------------------------------
# paint
#
# paint table: selcarpk/<car>.pkd sub-entry 3
# every carpk header lists same entry as its 6th member (size = selcarpk entry size, offset 0 = not stored in race pack)
# race loader 0x191270 reads it from list+0x14, showroom loader 0x191300 from list+0xC
# layout: u32 count, then count records of 52 bytes:
#   u32 colourId
#   u32 nameOffset (relative to table, cp932 string)
#   4 slots x 11 bytes {R,G,B,A base; Re,Ge,Be env; Rs,Gs,Bs sky; P}
# setCarColour 0x1931B0 -> 0x2D12C8 (race) / 0x2D1148 (showroom) calls setPaint 0x2616E8(model, slot, which, R, G, B, A) for slots 0-3:
#   model+0x230 + slot*48 + which*16 = (R, G, B, A) / 128.0 (floats)
#   which 0 = base RGBA
#   which 1 = (env RGB, P), showroom: (0x50, 0x50, 0x50, P)
#   which 2 = (sky RGB, colourId)
# model setup 0x262AF0 initialises all twelve vectors to 1.0
# icd swatch file (all_icd.bin) is a subset of this table
# ---------------------------------------------------------------------------
def parse_paint_table(data):
    """return a list of {id, name, slots: [{base, env, sky, p} x4]}, or None"""
    if not data or len(data) < 4:
        return None
    n = struct.unpack_from('<I', data, 0)[0]
    if not (0 < n <= 64) or 4 + 52 * n > len(data):
        return None
    cols = []
    for c in range(n):
        r = 4 + 52 * c
        cid, noff = struct.unpack_from('<2I', data, r)
        name = ''
        if noff < len(data):
            e = data.find(b'\0', noff)
            name = data[noff:e if e >= 0 else len(data)].decode('cp932', 'replace')
        slots = []
        for s in range(4):
            b = data[r + 8 + 11 * s: r + 19 + 11 * s]
            slots.append(dict(base=tuple(b[0:4]), env=tuple(b[4:7]),
                              sky=tuple(b[7:10]), p=b[10]))
        cols.append(dict(id=cid, name=name, slots=slots))
    return cols


def find_paint_table(path):
    """paint table for a car pack

    pack's own sub-entry 3 for a selcarpk, otherwise selcarpk/<same file name> next to carpk folder
    """
    import os
    try:
        ents = parse_pkd(open(path, 'rb').read())
    except OSError:
        ents = None
    if ents and len(ents) > 3:
        t = parse_paint_table(ents[3])
        if t:
            return t
    d, f = os.path.split(path)
    for rel in ('../selcarpk', '../../pack/selcarpk', 'selcarpk'):
        q = os.path.normpath(os.path.join(d, rel, f))
        if os.path.isfile(q) and os.path.normcase(q) != os.path.normcase(path):
            try:
                e2 = parse_pkd(open(q, 'rb').read())
            except OSError:
                continue
            if e2 and len(e2) > 3:
                t = parse_paint_table(e2[3])
                if t:
                    return t
    return None


def paint_vectors(colour, showroom=False):
    """twelve vec4 at model+0x230 (index slot*3 + which), in GS units (1.0 = byte 0x80)

    colour None gives load-time default (all 1.0)
    """
    if colour is None:
        return [(1.0, 1.0, 1.0, 1.0)] * 12
    v = []
    for s in colour['slots']:
        v.append(tuple(x / 128.0 for x in s['base']))
        env = (0x50, 0x50, 0x50) if showroom else s['env']
        v.append(tuple(x / 128.0 for x in env) + (s['p'] / 128.0,))
        v.append(tuple(x / 128.0 for x in s['sky']) + (colour['id'] / 128.0,))
    return v


# ---------------------------------------------------------------------------
# draw program: emitter 0x261E88, merge 0x262D30, VU1 program B (uploaded from ELF file offset 0x273834, routine table 0x372720)
#
# each geometry packet is drawn in up to four passes over same strip
# per pass emitter builds a colour qword (VU vf23):
#   group table 0x48BB20 on mat+4 (byte at model+0x1B4+group, groups 0 and 15 are 0x80 after load, all others 0):
#     g0/g1   rgb model+0x1F0 (1.0), w = byte, byte < 4 drops whole packet (output pointer rewound)
#     g6      (1, 1, 1, model+0x1C3 + node[+0x18]&15) (runtime index)
#     g9/g15  rgb model+0x1F0, w = byte
#     others  rgb model+0x210 (lamp colour, runtime), w = byte
#     w < 4 skips pass
#   mode table 0x48BB60 on mat+6 (set by merge from VU nibble):
#     0  w *= 0.99999 (keeps framebuffer alpha below 0x80, see DATE)
#     1  colour = (model+0x200.rgb * model+0x2F0/255, model+0x20C)
#     3  drawn only if model+0x190 != 0
#     5  untextured, skipped if q38 bit 16 is set and model+0x190 == 0
#   paint slot mat+5 >= 0: colour *= model+0x230 + slot*48 + mode*16 (VU0 vmul.xyzw), VU shade parameter P = model+0x24C + slot*48
# VU1 routine (index = nibble + 16 * not-first):
#   first pass: nibble 0/F -> 0x7D, A -> 0x1C4, others -> 0x10 (program end)
#   later passes: 0 -> 0xE2, A -> 0xC1, B -> 0x100, C/D -> 0x130, others -> 0x10
#   shade = max(0, 128*(1-P) + w3*P), computed by first routine (P of first pass) and kept for later passes
#   RGB = colour.rgb * shade (all routines)
#   A = colour.w (0x7D, 0xE2, 0x130) or colour.w*128 (0x1C4, 0xC1)
#   FTOI0 truncates, 0x7D/0x1C4 clamp to 255, later routines wrap (GIF PACKED takes low byte)
#   UV: pool (0x7D/0xE2), sphere map of view normal (0x1C4/0xC1), s = (1 + R.U)/2 and t = 0 with R reflected view vector (0x130)
# textures:
#   nibble A: runtime env, 128x128 PSMCT24 at TBP 0x2E00 (TCC=0: As = vertex A)
#   nibble D: runtime sky strip, 64x32 PSMCT24 at TBP 0x3FE0 (TCC=0)
#   nibble C: material's own file texture through 0x130 mapping
#   nibble F: PRIM TME=0
#   env nibble set: pvram_000 entry, otherwise material's record
# ---------------------------------------------------------------------------
GROUPS_DEFAULT = frozenset((0, 15))
GROUPS_LAMPS = frozenset((2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14))
_ROUTINE_FIRST = {0x0: 'std', 0xA: 'env', 0xF: 'std'}
_ROUTINE_LATER = {0x0: 'std2', 0xA: 'env2', 0xB: 'proj', 0xC: 'elev',
                  0xD: 'elev'}
# materials whose TEST is 0x5060B get mat+7 = 1 in merge
# emitter then writes TEST = model+0x190 ? 0x5060B : 0x5160B (0x190 is 0 after load)
_TEST_GLASS = 0x5060B
_TEST_GLASS_EFF = 0x5160B


def _test_info(t):
    ate = t & 1
    atst = (t >> 1) & 7
    aref = (t >> 4) & 0xFF
    afail = (t >> 12) & 3
    date = (t >> 14) & 1
    datm = (t >> 15) & 1
    return ate, atst, aref, afail, date, datm


def _eq_name(abe, a):
    A, B, C, D = a & 3, (a >> 2) & 3, (a >> 4) & 3, (a >> 6) & 3
    if not abe:
        return 'replace'
    if A == B:
        return 'noop'                     # (X-X)*C+D: colour unchanged
    if (A, B, D) == (0, 1, 1):
        return {0: 'blend', 1: 'blend_dest', 2: 'blend_fix'}[C]
    if (A, B, D) == (0, 2, 1):
        return {0: 'add', 1: 'add_dest', 2: 'add_fix'}[C]
    return 'other'


def pass_constants(col_pre, slot, mode, routine, vecs, env_k=1.0):
    """paint-dependent constants of one pass

    returns (rgb multiplier before shade, vertex alpha byte, VU shade parameter P, rgb clamp)
    env_k is runtime env intensity model+0x200 * model+0x2F0/255 (mode 1)
    """
    col = list(col_pre)
    if mode == 1:
        col = [col[0] * env_k, col[1] * env_k, col[2] * env_k, col[3]]
    p = 1.0
    if slot >= 0:
        k = slot * 3 + mode
        pv = vecs[k] if 0 <= k < 12 else (1.0, 1.0, 1.0, 1.0)
        col = [a * b for a, b in zip(col, pv)]
        p = vecs[slot * 3 + 1][3]
    av = col[3] * (128.0 if routine in ('env', 'env2') else 1.0)
    av = int(av) if av > 0 else 0
    if routine in ('std', 'env'):
        av = min(av, 255)
        rgb_clamp = 255.0 / 128.0
    else:
        av &= 0xFF
        rgb_clamp = None
    return tuple(col[:3]), av, p, rgb_clamp


def draw_program(model, passes, vecs=None, groups=GROUPS_DEFAULT,
                 env_k=1.0, flag190=0):
    """reduce a packet's pass list to passes that reach GS

    each pass carries every constant fragment stage needs
    returns None when packet draws nothing
    """
    if vecs is None:
        vecs = paint_vectors(None)
    out = []
    emitted = 0
    t4 = 0
    p_first = None
    for mi in passes:
        if not (0 <= mi < len(model.materials)):
            continue
        info = model.materials[mi]
        g = info['mat4']
        gb = 0x80 if g in groups else 0
        if g in (0, 1):
            t4 |= 1
            if gb < 4:
                return None                       # packet rewound
        col = [1.0, 1.0, 1.0, float(gb)]
        if gb < 4:
            continue
        mode = info['mode']
        nib = info['vu']
        q38 = info['q38']
        if mode == 0:
            col[3] *= 0.99999
        elif mode == 1:
            col = [1.0, 1.0, 1.0, 1.0]            # * env_k in pass_constants
        elif mode == 3:
            if not flag190:
                continue
            if t4 & 1:
                col[3] *= 0.75
        elif mode == 5:
            if (q38 >> 16) & 1 and not flag190:
                continue
        slot = info['paint']
        first = emitted == 0
        routine = (_ROUTINE_FIRST if first else _ROUTINE_LATER).get(nib)
        emitted += 1
        if routine is None:
            break                                 # VU 0x10: program ends
        rgb, av, p, rgb_clamp = pass_constants(col, slot, mode, routine,
                                               vecs, env_k)
        if first:
            p_first = p
        # texture source
        if nib == 0xA:
            tex, tcc, uv = 'env', 0, 'sphere'
        elif nib == 0xD:
            tex, tcc, uv = 'sky', 0, 'elev'
        elif nib == 0xB:
            tex, tcc, uv = 'runtime', 0, 'proj'
        elif nib == 0xF:
            tex, tcc, uv = None, 0, None
        else:
            uv = 'elev' if nib == 0xC else 'uv'
            tcc = 1
            if mode == 6 and info['envmap']:
                tex = ('pvram', PVRAM_NIBBLE_ENTRY.get(info['envmap']))
            elif info['tex'] in model.textures:
                tex = ('rec', info['tex'])
            else:
                tex = 'missing'
        test = info['test_reg']
        if test == _TEST_GLASS and not flag190:
            test = _TEST_GLASS_EFF
        ate, atst, aref, afail, date, datm = _test_info(test)
        out.append(dict(mi=mi, routine=routine, group=g, slot=slot,
                        mode=mode, nib=nib, tex=tex, tcc=tcc, uv=uv,
                        col_pre=tuple(col), rgb=rgb, rgb_clamp=rgb_clamp,
                        av=av,
                        abe=info['abe'], alpha_reg=info['alpha_reg'],
                        eq=_eq_name(info['abe'], info['alpha_reg']),
                        test=test, ate=ate, atst=atst, aref=aref,
                        afail=afail, date=date, datm=datm))
    if not out:
        return None
    return dict(passes=out, p=p_first if p_first is not None else 1.0)


def write_masks(ps):
    """write masks ('all', 'test' or 'none') for colour and alpha of a pass

    'test': only pixels passing alpha test (ATST/AREF) are written, failing pixels follow AFAIL (KEEP, FB_ONLY, ZB_ONLY, RGB_ONLY)
    """
    if not ps['ate'] or ps['atst'] == 1:                 # off / ALWAYS
        return 'all', 'all'
    fc, fa = {0: (False, False), 1: (True, True), 2: (False, False),
              3: (True, False)}[ps['afail']]
    if ps['atst'] == 0:                                  # NEVER
        return ('all' if fc else 'none'), ('all' if fa else 'none')
    return ('all' if fc else 'test'), ('all' if fa else 'test')


def alpha_test(ps, a):
    """GS ATST of raw source alpha a (0..255, 0x80 = 1.0)"""
    if not ps['ate']:
        return True
    t, r = ps['atst'], ps['aref']
    return (False, True, a < r, a <= r, a == r, a >= r, a > r, a != r)[t]


# ---------------------------------------------------------------------------
# courses (pack/mappk/NNN_NN.pkd sub-entry 0: PC v4 with BG06 + GS02)
#
# BG setup 0x25ECD8 (merge loop at 0x25EE2C), node setup 0x25F560, GS relocator 0x25EA88, per-frame material header 0x133990, node emitter 0x25E7A8, VU1 program A (MPG chain at ELF file offset 0x271554, routine table 0x3704F0)
# ---------------------------------------------------------------------------
class CourseModel:
    kind = 'course'

    def __init__(self):
        self.nodes = []
        self.materials = []
        self.textures = {}
        self.warnings = []
        self.spec = None
        self.attach = []
        self.composite = set()
        self.resident = {}


# course names: mappk/NNN_00.pkd is loaded by map number NNN
# game resolves a map number to its name in 0x197230 -> 0x197338:
#   0x197590: numbers 600-719 and 800-919 become NNN-600
#   these are mode-dependent variants, picked at 0x1B0070 through game-mode switch 0x166260 when listed at 0x47D768 (608 615 620 621 808 815 821)
#   0x197680: index of that number in u16 table at 0x47D778 (built at 0x197260 from 0x49-entry list at 0x47D670 followed by 400..519)
#   name is string pointer table 0x378CC0[index] ('@' before a letter marks an umlaut)
# 2xx maps use same names as their 0xx counterparts
_COURSE_NAME_BY_INDEX = {
    1: 'AUTUMN HILL', 2: 'AUTUMN MOUNTAIN', 3: 'VICTORIA GARDEN',
    4: 'VICTORIA ROAD', 5: 'ROUTE de la SEINE', 7: 'BURGENSCHLUCHT',
    8: 'WINTERTRAUM', 10: 'MARCO STRADA', 11: 'MARCO STRADA',
    12: 'TSUKUBA CIRCUIT', 13: 'TSUKUBA CIRCUIT', 14: 'TSUKUBA CIRCUIT',
    15: 'Nürburgring Nordschleife', 16: 'PACIFIC GATEWAY',
    17: 'LÖWENSEERING', 18: 'REV CITY', 20: 'SPEEDIAPOLIS RING',
    21: 'MYSTIC CAVEWAY', 22: 'EDGE OF THE ROAD', 23: 'DRAGON RANGE',
    26: 'AIRPORT SQUARE', 28: 'OCEAN BRIDGE', 29: 'OCEAN BRIDGE',
    46: 'COSMIC EGGWAY', 47: 'COSMIC WINDING', 48: 'WILD WEST ENDURO',
    99: 'GARAGE', 112: 'MARCO STRADA', 113: 'MARCO STRADA',
    114: 'Nürburgring Nordschleife', 115: 'MARCO STRADA',
    116: 'MIRAGE CROSSING', 117: 'PYLON SLALOM', 118: 'SS CIRCLE',
    119: 'DEMO RUN', 247: 'COSMIC WINDING', 248: 'WILD WEST ENDURO'}
_COURSE_NAME_BY_INDEX.update({n: 'MIRAGE CROSSING' for n in range(30, 46)})
_COURSE_NAME_BY_INDEX.update({200 + n: _COURSE_NAME_BY_INDEX[n]
                              for n in (1, 2, 3, 4, 5, 7, 8, 10, 11, 12, 13,
                                        14, 15, 16, 17, 18, 21, 22, 23)})


def course_name(number):
    """display name of map number NNN (None if game has none)"""
    if 600 <= number < 720 or 800 <= number < 920:
        number -= 600
    return _COURSE_NAME_BY_INDEX.get(number)


# VU1 program A routine table 0x3704F0 (index = q38 bits 8-11), with UV source each routine computes (vf11):
#   0x3BA (nibbles 0, 4, 7, 9, F): uv/512 + vf23 (material UV scroll, runtime)
#   0x3B7 (3): as 0x3BA, colour replaced by VU mem 12 (material animation)
#   0x29B (2): sphere map, (0.5, -0.5) * (view rotation x normal).xy
#   0x276/0x2AF/0x2B7 (1, 6, 8): reflected view vector R, s = .5+.5R.x, t = .5+.5R.z (planar chrome mapping)
#   0x2A5 (5): uv/512 + offset + normal * (-0.25, 0.25) (ripple)
#   0x336 (A): world-position projection through VU mem 4-7 (runtime projector for shadows and lights)
#   0x342/0x357 (B, E): screen-space mapping of projected position (framebuffer effects)
#   0x36D/0x392 (C, D): uv/512, vertex colour plus a distance term from runtime light at VU mem 0-3 (headlights)
_COURSE_UV = {0x0: 'uv', 0x4: 'uv', 0x7: 'uv', 0x9: 'uv', 0xF: 'uv',
              0x3: 'uv', 0xC: 'uv', 0xD: 'uv', 0x5: 'uv',
              0x2: 'sphere', 0x1: 'refl', 0x6: 'refl', 0x8: 'refl',
              0xA: 'proj', 0xB: 'screen', 0xE: 'screen'}


def _course_upload(d, o):
    """parse one prebuilt texture upload

    layout: DMA ref + VIF, GIF A+D x4 (BITBLTBUF, TRXPOS, TRXREG, TRXDIR), IMAGE tag
    returns (dbp, dbw, dpsm, w, h, offset of IMAGE giftag)
    """
    o += 16
    nloop = struct.unpack_from('<I', d, o)[0] & 0x7FFF
    regs = {}
    for k in range(nloop):
        val, reg = struct.unpack_from('<QQ', d, o + 16 + 16 * k)
        regs[reg & 0xFF] = val
    bb = regs.get(0x50, 0)
    tr = regs.get(0x52, 0)
    return ((bb >> 32) & 0x3FFF, max(1, (bb >> 48) & 0x3F), (bb >> 56) & 0x3F,
            tr & 0xFFF, (tr >> 32) & 0xFFF, o + 16 + 16 * nloop)


def _parse_gs_course(d, gs, m):
    """decode course GS02 textures

    header:
      +0x04 s16 record count
      +0x06 s16 CLUT-area size in blocks (texture pages start after it)
      +0x10 -> CLUT upload (64-wide PSMCT32 into CLUT area, relocated to 0x3480)
      +0x14 -> page data (8 KB pages, page P at +0x14 + P*8192)
      +0x1C -> prebuilt per-page uploads (128 bytes each, page P at +0x1C + P*128)
    records (48 bytes at +0x20) match car records up to +0x27, then:
      +0x28 u16 size in blocks
      +0x2A u16 first page
      +0x2C u16 block offset in page (= TBP in file TEX0)
      +0x2E runtime VRAM slot (page % 75)
    at runtime pages are streamed into a 75-page ring, each record is decoded from its own page
    """
    cnt = struct.unpack_from('<h', d, gs + 4)[0]
    p10, p14, p18, p1c = struct.unpack_from('<4I', d, gs + 0x10)
    clut = _GSMem()
    try:
        dbp, dbw, dpsm, rw, rh, io = _course_upload(d, gs + p10)
        src = io + 16
        k = 0
        for y in range(rh):
            for x in range(rw):
                clut.w32(dbp, dbw, x, y, struct.unpack_from('<I', d, src + k)[0])
                k += 4
    except struct.error:
        m.warnings.append('course CLUT upload unreadable')
        return
    pages = {}
    for i in range(cnt):
        r = gs + 0x20 + 48 * i
        flag = d[r + 0xF]
        w, h = struct.unpack_from('<2H', d, r + 8)
        q10, q18, q20 = struct.unpack_from('<3Q', d, r + 16)
        nblk, page, boff = struct.unpack_from('<3H', d, r + 0x28)
        if not (0 < w <= 1024 and 0 < h <= 1024):
            continue
        if page not in pages:
            po = gs + p1c + page * 128
            if po + 128 > len(d) or not any(d[po:po + 128]):
                m.warnings.append('texture %d: page %d has no upload' % (i, page))
                continue
            mem = _GSMem()
            pdbp, pdbw, pdpsm, prw, prh, pio = _course_upload(d, po)
            dref = struct.unpack_from('<I', d, po + 0x74)[0]
            src = gs + p14 + dref
            if src + prw * prh * 4 > len(d):
                m.warnings.append('texture page %d truncated' % page)
                continue
            k = 0
            for y in range(prh):
                for x in range(prw):
                    mem.w32(pdbp, pdbw, x, y,
                            struct.unpack_from('<I', d, src + k)[0])
                    k += 4
            pages[page] = mem
        mem = pages[page]
        tbp = q10 & 0x3FFF
        tbw = max(1, (q10 >> 14) & 0x3F)
        psm = (q10 >> 20) & 0x3F
        csa = (q10 >> 56) & 0x1F
        cbp = ((q10 if flag else q20) >> 37) & 0x3FFF
        out = bytearray(w * h * 4)
        k = 0
        if psm == 0x14:
            pal = [bytes(_rgba(_clut4(clut, cbp, csa, c))) for c in range(16)]
            for y in range(h):
                for x in range(w):
                    out[k:k + 4] = pal[mem.r4(tbp, tbw, x, y)]
                    k += 4
        elif psm == 0x13:
            pal = [bytes(_rgba(_clut8(clut, cbp, c))) for c in range(256)]
            for y in range(h):
                for x in range(w):
                    out[k:k + 4] = pal[mem.r8(tbp, tbw, x, y)]
                    k += 4
        elif psm == 0x00:
            for y in range(h):
                for x in range(w):
                    out[k:k + 4] = bytes(_rgba(mem.r32(tbp, tbw, x, y)))
                    k += 4
        else:
            m.warnings.append('texture %d: PSM 0x%02X not handled' % (i, psm))
            continue
        m.textures[i] = dict(w=w, h=h, rgba=bytes(out), psm=psm,
                             mips=d[r + 0xE])


def _parse_course_batches(d, bg, geo, end):
    """parse a course packet list (node emitter 0x25E7A8)

    32-byte packet header is same as on cars (+0 u16 qwc, +2 0xFF = end, +3 pass count, +4 s16 materials[4]) plus +0x10 u16 draw flags (bit 0: main pass, bit 1: model+0x17E pass)
    VIF data are sent as is: STCYCL 4/1 interleaves one 4-qword record per vertex, [0] V2-16 UV, [1] V3-32 position, [2] S-16 flag (or V4-16 normal 4.12 + flag), [3] V4-8 RGBA
    each MSCNT runs one batch
    flag of vertex 0 holds vertex count in its low byte, bit 15 (negative) = ADC (no triangle for this vertex)
    """
    out = []
    o = bg + geo
    stop = bg + end
    while o + 0x20 <= stop:
        qwc, t2, t3 = struct.unpack_from('<HBB', d, o)
        if t2 == 0xFF:
            break
        passes = [struct.unpack_from('<h', d, o + 4 + 2 * k)[0]
                  for k in range(min(t3, 4))]
        passes = [x for x in passes if x >= 0]
        f10 = struct.unpack_from('<H', d, o + 0x10)[0]
        p = o + 0x20
        pend = p + qwc * 16
        slots = {}
        while p < pend:
            w = struct.unpack_from('<I', d, p)[0]
            p += 4
            cmd = (w >> 24) & 0x7F
            num = (w >> 16) & 0xFF
            imm = w & 0xFFFF
            if cmd >= 0x60:
                vn = (cmd >> 2) & 3
                vl = cmd & 3
                n = num or 256
                bits = (32, 16, 8, 5)[vl]
                comps = vn + 1
                sz = ((2 * n if bits == 5 else (comps * bits // 8) * n) + 3) // 4 * 4
                usn = (imm >> 14) & 1
                addr = imm & 0x3FF
                if bits == 32:
                    fmt = '<%df' % comps
                    step = 4 * comps
                elif bits == 16:
                    fmt = ('<%dH' if usn else '<%dh') % comps
                    step = 2 * comps
                elif bits == 8:
                    fmt = ('<%dB' if usn else '<%db') % comps
                    step = comps
                else:
                    fmt = None
                if fmt:
                    slots[addr] = [struct.unpack_from(fmt, d, p + step * k)
                                   for k in range(n)]
                p += sz
            elif cmd in (0x14, 0x15, 0x17):
                pos = slots.get(1)
                if pos:
                    fl = slots.get(2) or [(0,)] * len(pos)
                    out.append(dict(passes=passes, f10=f10, pos=pos,
                                    uv=slots.get(0) or [(0, 0)] * len(pos),
                                    fl=fl,
                                    col=slots.get(3) or [(128, 128, 128, 128)] * len(pos)))
                slots = {}
        o = pend
    return out


def _parse_bg(d, bg, m):
    ncount, mcount = struct.unpack_from('<2H', d, bg + 0x10)
    mat_off = struct.unpack_from('<I', d, bg + 0x1C)[0]
    size = struct.unpack_from('<I', d, bg + 0x0C)[0]
    for i in range(mcount):
        r = bg + mat_off + i * 0x40
        q38 = struct.unpack_from('<Q', d, r + 0x38)[0]
        nib = (q38 >> 8) & 0xF
        m.materials.append(dict(
            tex=struct.unpack_from('<h', d, r + 2)[0],
            surface=d[r + 4],                 # merge: types 2-7 / 11 -> mask
            alpha_reg=struct.unpack_from('<Q', d, r + 0x20)[0],
            test_reg=struct.unpack_from('<Q', d, r + 0x28)[0],
            q38=q38, vu=nib, abe=(q38 >> 12) & 1,
            # merge: CLAMP = 5 for nibbles 1 and A, 0 (repeat) otherwise
            clamp=5 if nib in (0x1, 0xA) else 0,
            # material header 0x133990: UV scroll speeds, applied at runtime
            scroll=((q38 >> 20) & 0xF, (q38 >> 24) & 0xF),
            anim=struct.unpack_from('<I', d, r + 8)[0] != 0))
    geos = sorted({struct.unpack_from('<I', d, bg + 0x20 + i * 0x100)[0]
                   for i in range(ncount)} | {size})
    for i in range(ncount):
        n = bg + 0x20 + i * 0x100
        geo = struct.unpack_from('<I', d, n)[0]
        flags = struct.unpack_from('<H', d, n + 0x0C)[0]
        oid = struct.unpack_from('<h', d, n + 0x1A)[0]
        rows = [struct.unpack_from('<4f', d, n + 0x40 + 16 * r) for r in range(4)]
        # node setup 0x25F560: nodes with an object id (+0x1A >= 0) render with +0x40 matrix (rotation rows xyz, translation in row 3, node-local vertices)
        # object ids are unique per pack, with one 256-byte record each in fourth PC chunk
        # all other nodes get identity (world-space vertices)
        if oid >= 0:
            mtx = [rows[0][:3], rows[1][:3], rows[2][:3], rows[3][:3]]
        else:
            mtx = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, 0)]
        bmin = struct.unpack_from('<3f', d, n + 0x80)
        bmax = struct.unpack_from('<3f', d, n + 0x90)
        batches = []
        if geo:
            batches = _parse_course_batches(d, bg, geo,
                                            geos[geos.index(geo) + 1])
        m.nodes.append(dict(index=i, flags=flags, object_id=oid, matrix=mtx,
                            bbox_min=bmin, bbox_max=bmax, batches=batches,
                            sky=(i == 0)))


def course_program(model, passes, groups=None):
    """draw program of a course packet

    same fragment semantics as cars (MODULATE, ALPHA, TEST, DATE), with per-vertex RGBA from data and UV source of material's routine
    vertex colour is multiplied by VU vf19.w / vf18.w = node+0xB8 (1.0 at load)
    """
    out = []
    for mi in passes:
        if not (0 <= mi < len(model.materials)):
            continue
        info = model.materials[mi]
        uv = _COURSE_UV.get(info['vu'], 'uv')
        if uv in ('proj', 'screen'):
            continue                      # runtime projector / framebuffer
        tex = ('rec', info['tex']) if info['tex'] in model.textures else \
            ('missing' if info['tex'] >= 0 else None)
        test = info['test_reg']
        ate, atst, aref, afail, date, datm = _test_info(test)
        out.append(dict(mi=mi, routine='course', group=15, slot=-1, mode=0,
                        nib=info['vu'], tex=tex, tcc=1, uv=uv,
                        col_pre=(1.0, 1.0, 1.0, 1.0), rgb=(1.0, 1.0, 1.0),
                        rgb_clamp=None, av=128, vcol=True,
                        clamp=info['clamp'],
                        abe=info['abe'], alpha_reg=info['alpha_reg'],
                        eq=_eq_name(info['abe'], info['alpha_reg']),
                        test=test, ate=ate, atst=atst, aref=aref,
                        afail=afail, date=date, datm=datm))
    if not out:
        return None
    return dict(passes=out, p=1.0)


def course_extent(model):
    """world-space extent of course, sky excluded

    static nodes count with their bbox, object nodes with their bbox corners through node matrix
    returns (lo, hi, base), base being lowest static geometry
    """
    lo = [1e30] * 3
    hi = [-1e30] * 3
    base = 1e30
    for node in model.nodes:
        if node['sky'] or not node['batches']:
            continue
        b0, b1 = node['bbox_min'], node['bbox_max']
        if node['object_id'] < 0:
            pts = [b0, b1]
            base = min(base, b0[1])
        else:
            r0, r1, r2, t = node['matrix']
            pts = []
            for x in (b0[0], b1[0]):
                for y in (b0[1], b1[1]):
                    for z in (b0[2], b1[2]):
                        pts.append(tuple(x * r0[k] + y * r1[k] + z * r2[k] + t[k]
                                         for k in range(3)))
        for p in pts:
            for k in range(3):
                lo[k] = min(lo[k], p[k])
                hi[k] = max(hi[k], p[k])
    if base > 1e29:
        base = lo[1]
    return lo, hi, base


def course_triangles(batch):
    """convert a strip to triangles

    ADC (negative flag) suppresses a vertex's triangle
    two ADC vertices in a row start a new strip, and winding parity is counted from that start
    """
    fl = [f[-1] for f in batch['fl']]
    tris = []
    start = 0
    for k in range(len(fl)):
        if k >= 1 and fl[k] < 0 and fl[k - 1] < 0:
            start = k - 1
        if k < 2 or fl[k] < 0:
            continue
        if (k - start) & 1:
            tris.append((k - 1, k - 2, k))
        else:
            tris.append((k - 2, k - 1, k))
    return tris


def load_file(path):
    """load a .pkd pack or a bare PC container and return decoded model"""
    data = open(path, 'rb').read()
    entries = parse_pkd(data)
    if entries:
        if not entries[0]:
            raise ValueError('pkd sub-entry 0 is empty: this pack holds no model')
        model = load_vgs(entries[0])
        model.spec = find_spec(entries[1:]) if model.kind == 'car' else None
    else:
        model = load_vgs(data)
    return model


# -------------
# blender side
# -------------
try:
    import bpy
    import bmesh  # noqa: F401
    from bpy_extras.io_utils import ImportHelper
    from mathutils import Matrix, Vector
    _IN_BLENDER = True
except ImportError:
    _IN_BLENDER = False

SLOT_NAMES = {0: 'body', 1: 'wheel_FL', 2: 'wheel_FR', 3: 'wheel_RL',
              4: 'wheel_RR', 5: 'brake_FL', 6: 'brake_FR', 7: 'brake_RL',
              8: 'brake_RR', 9: 'light_L', 10: 'light_R', 14: 'cockpit',
              15: 'shadow'}


def _wheel_face_x(node):
    """return which x side wheel's visible face points to (+1.0 or -1.0, 0.0 without normals)

    decided by stored vertex normals (file data, independent of winding): majority sign of x-dominant normals
    odd slots face -x, even slots +x
    """
    import math as _math
    npos = nneg = 0
    for msh in node['meshes']:
        N = msh['norms']
        if not N:
            continue
        for nx, ny, nz in N:
            l = _math.sqrt(nx * nx + ny * ny + nz * nz)
            if l < 1e-9 or abs(nx) / l <= 0.6:
                continue
            if nx > 0:
                npos += 1
            else:
                nneg += 1
    if npos == nneg == 0:
        return 0.0
    return 1.0 if npos >= nneg else -1.0

# PS2 (x right, y up, z forward) -> Blender (x right, y back, z up)
_PS2_TO_BL = ((1, 0, 0), (0, 0, -1), (0, 1, 0))


def _cnv(v):
    return (v[0], -v[2], v[1])


if _IN_BLENDER:
    import json as _json

    def _make_image(name, tex, raw=False):
        # never reuse an existing image of same name: names repeat for every import of a car, so reusing one would keep pixels of an earlier import
        # blender makes new name unique (.001)
        img = bpy.data.images.new(name, tex['w'], tex['h'], alpha=True)
        w, h, rgba = tex['w'], tex['h'], tex['rgba']
        # img.pixels is a scene-linear buffer and decoded texels are sRGB-encoded, so they are converted here (written raw, display transform would be applied twice)
        # alpha stays linear
        s2l = [0.0] * 256
        for c in range(256):
            f = c / 255.0
            s2l[c] = f / 12.92 if f <= 0.04045 \
                else ((f + 0.055) / 1.055) ** 2.4
        px = [0.0] * (w * h * 4)
        for y in range(h):                       # blender rows are bottom-up
            src = (h - 1 - y) * w * 4
            dst = y * w * 4
            for k in range(0, w * 4, 4):
                px[dst + k] = s2l[rgba[src + k]]
                px[dst + k + 1] = s2l[rgba[src + k + 1]]
                px[dst + k + 2] = s2l[rgba[src + k + 2]]
                px[dst + k + 3] = rgba[src + k + 3] / 255.0
        if raw:
            # GAME shading composes in display space: keep texels as stored and mark image Non-Color
            for y in range(h):
                src = (h - 1 - y) * w * 4
                dst = y * w * 4
                for k in range(w * 4):
                    px[dst + k] = rgba[src + k] / 255.0
            try:
                img.colorspace_settings.name = 'Non-Color'
            except Exception:
                pass
        img.pixels = px
        img.pack()
        return img

    def _set_blend(mat, mode):
        try:
            mat.blend_method = mode            # <= 4.1
        except Exception:
            pass
        if hasattr(mat, 'surface_render_method'):   # 4.2+ EEVEE Next
            mat.surface_render_method = \
                'BLENDED' if mode in ('BLEND', 'CLIP') else 'DITHERED'

    class _NB:
        """small node-tree builder (column layout, inputs can be constants or sockets)"""

        def __init__(self, nt):
            self.nt = nt
            self.rows = {}

        def new(self, kind, col, name=None, label=None):
            n = self.nt.nodes.new(kind)
            y = self.rows.get(col, 0)
            n.location = (col * 240.0, -y)
            self.rows[col] = y + 180
            if name:
                n.name = name
            if label:
                n.label = label
            return n

        def put(self, sock, v):
            if isinstance(v, (int, float)):
                sock.default_value = float(v)
            elif isinstance(v, tuple):
                sock.default_value = v
            else:
                self.nt.links.new(v, sock)

        def math(self, op, a, b=None, c=None, col=0):
            n = self.new('ShaderNodeMath', col)
            n.operation = op
            self.put(n.inputs[0], a)
            if b is not None:
                self.put(n.inputs[1], b)
            if c is not None:
                self.put(n.inputs[2], c)
            return n.outputs[0]

        def mul(self, a, b, col=0):
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                return float(a) * float(b)
            if isinstance(a, (int, float)) and a == 1.0:
                return b
            if isinstance(b, (int, float)) and b == 1.0:
                return a
            return self.math('MULTIPLY', a, b, col=col)

        def value(self, v, col, name=None, label=None):
            n = self.new('ShaderNodeValue', col, name=name, label=label)
            n.outputs[0].default_value = float(v)
            return n.outputs[0]

        def vec(self, xyz, col, name=None, label=None):
            n = self.new('ShaderNodeCombineXYZ', col, name=name, label=label)
            for i in range(3):
                n.inputs[i].default_value = float(xyz[i])
            return n.outputs[0]

        def vmath(self, op, a, b=None, col=0, scale=None):
            n = self.new('ShaderNodeVectorMath', col)
            n.operation = op
            self.put(n.inputs[0], a)
            if b is not None:
                self.put(n.inputs[1], b)
            if scale is not None:
                self.put(n.inputs['Scale'], scale)
            return n.outputs[0]

        def gamma(self, c, col):
            n = self.new('ShaderNodeGamma', col)
            self.put(n.inputs['Color'], c)
            n.inputs['Gamma'].default_value = 2.2
            return n.outputs[0]

        def pow22(self, f, col):
            if isinstance(f, (int, float)):
                return max(0.0, float(f)) ** 2.2
            return self.math('POWER', f, 2.2, col=col)

        def shader(self, kind, col):
            return self.new(kind, col)

        def mix(self, fac, a, b, col):
            n = self.new('ShaderNodeMixShader', col)
            self.put(n.inputs[0], fac)
            self.nt.links.new(a, n.inputs[1])
            self.nt.links.new(b, n.inputs[2])
            return n.outputs[0]

        def add(self, a, b, col):
            n = self.new('ShaderNodeAddShader', col)
            self.nt.links.new(a, n.inputs[0])
            self.nt.links.new(b, n.inputs[1])
            return n.outputs[0]

    def _glossy_node(nb, col):
        for kind in ('ShaderNodeBsdfGlossy', 'ShaderNodeBsdfAnisotropic'):
            try:
                return nb.new(kind, col)
            except Exception:
                continue
        return None

    def _surface(nb, colour, col, ctx):
        """opaque-looking surface for a drawn colour (linear socket)"""
        if ctx['shading'] == 'GAME' or ctx.get('unlit'):
            e = nb.shader('ShaderNodeEmission', col)
            nb.put(e.inputs['Color'], colour)
            e.inputs['Strength'].default_value = 1.0
            return e.outputs[0]
        b = nb.shader('ShaderNodeBsdfPrincipled', col)
        nb.put(b.inputs['Base Color'], colour)
        b.inputs['Roughness'].default_value = 1.0
        for nm in ('Specular IOR Level', 'Specular'):
            if nm in b.inputs:
                b.inputs[nm].default_value = 0.0
                break
        if 'Metallic' in b.inputs:
            b.inputs['Metallic'].default_value = 0.0
        return b.outputs[0]

    def _emission(nb, colour, col):
        e = nb.shader('ShaderNodeEmission', col)
        nb.put(e.inputs['Color'], colour)
        e.inputs['Strength'].default_value = 1.0
        return e.outputs[0]

    def _transparent(nb, col):
        return nb.shader('ShaderNodeBsdfTransparent', col).outputs[0]

    def _tex_node(nb, img, uv, col, interp='Closest', clamp=0):
        t = nb.new('ShaderNodeTexImage', col)
        t.image = img
        t.interpolation = interp
        if uv in ('sphere', 'refl'):
            # course env routines (program A): 'sphere' is view-space normal (0x29B), 'refl' reflected view vector with s = .5+.5R.x, t = .5+.5R.z (0x276/0x2AF/0x2B7)
            # in Blender: camera-space normal and world reflection (game z = -Blender y)
            t.extension = 'EXTEND' if clamp else 'REPEAT'
            sep = nb.new('ShaderNodeSeparateXYZ', col - 2)
            if uv == 'sphere':
                geo = nb.new('ShaderNodeNewGeometry', col - 3)
                vt = nb.new('ShaderNodeVectorTransform', col - 3)
                vt.vector_type = 'NORMAL'
                vt.convert_from = 'WORLD'
                vt.convert_to = 'CAMERA'
                nb.nt.links.new(geo.outputs['Normal'], vt.inputs[0])
                nb.nt.links.new(vt.outputs[0], sep.inputs[0])
            else:
                tc = nb.new('ShaderNodeTexCoord', col - 3)
                nb.nt.links.new(tc.outputs['Reflection'], sep.inputs[0])
            u = nb.math('MULTIPLY_ADD', sep.outputs[0], 0.5, 0.5, col=col - 1)
            v = nb.math('MULTIPLY_ADD', sep.outputs[1], 0.5, 0.5, col=col - 1)
            cmb = nb.new('ShaderNodeCombineXYZ', col - 1)
            nb.put(cmb.inputs[0], u)
            nb.put(cmb.inputs[1], v)
            nb.nt.links.new(cmb.outputs[0], t.inputs['Vector'])
            return t
        if uv == 'elev':
            # VU1 routine 0x130: s = (1 + R.U)/2, t = 0, with R reflected view vector and U per-frame axis uploaded at VU 300-302 (vertical in shipped streak textures, bright end up)
            # CLAMP register 5 for nibbles C/D clamps both axes
            t.extension = 'EXTEND'
            tc = nb.new('ShaderNodeTexCoord', col - 3)
            sep = nb.new('ShaderNodeSeparateXYZ', col - 2)
            nb.nt.links.new(tc.outputs['Reflection'], sep.inputs[0])
            s = nb.math('MULTIPLY_ADD', sep.outputs[2], 0.5, 0.5, col=col - 1)
            cmb = nb.new('ShaderNodeCombineXYZ', col - 1)
            nb.put(cmb.inputs[0], s)
            cmb.inputs[1].default_value = 1.0 - 0.5 / max(1, img.size[1])
            nb.nt.links.new(cmb.outputs[0], t.inputs['Vector'])
        else:
            # merge: CLAMP 0 (repeat) for plain materials, 5 (clamp) for course nibble 1/A materials
            t.extension = 'EXTEND' if clamp == 5 else 'REPEAT'
        return t

    def _test_node(nb, ps, As, col):
        """1.0 where GS alpha test passes (As in 1.0 = 0x80 units)"""
        t, r = ps['atst'], ps['aref'] / 128.0
        h = 0.5 / 128.0
        if t == 0:
            return 0.0
        if t == 1:
            return 1.0
        if isinstance(As, float):
            a = As * 128.0
            return 1.0 if alpha_test(ps, int(round(a))) else 0.0
        if t == 2:
            return nb.math('LESS_THAN', As, r - h, col=col)
        if t == 3:
            return nb.math('LESS_THAN', As, r + h, col=col)
        if t == 5:
            return nb.math('GREATER_THAN', As, r - h, col=col)
        if t == 6:
            return nb.math('GREATER_THAN', As, r + h, col=col)
        eqn = nb.math('COMPARE', As, r, h, col=col)
        if t == 4:
            return eqn
        return nb.math('SUBTRACT', 1.0, eqn, col=col)

    def _env_group():
        """shared stand-in for runtime env (nibble A) and sky (nibble D) textures in GAME shading

        display-space colours looked up by reflected view direction
        game renders these per course at runtime, edit this group (with an Environment Texture for instance) to change what paint reflects
        """
        name = 'Enthusia Env'
        g = bpy.data.node_groups.get(name)
        if g is not None and g.bl_idname == 'ShaderNodeTree':
            return g
        g = bpy.data.node_groups.new(name, 'ShaderNodeTree')
        try:
            g.interface.new_socket('Vector', in_out='INPUT',
                                   socket_type='NodeSocketVector')
            g.interface.new_socket('Env', in_out='OUTPUT',
                                   socket_type='NodeSocketColor')
            g.interface.new_socket('Sky', in_out='OUTPUT',
                                   socket_type='NodeSocketColor')
        except AttributeError:                      # blender < 4.0
            g.inputs.new('NodeSocketVector', 'Vector')
            g.outputs.new('NodeSocketColor', 'Env')
            g.outputs.new('NodeSocketColor', 'Sky')
        gi = g.nodes.new('NodeGroupInput')
        go = g.nodes.new('NodeGroupOutput')
        gi.location = (-600, 0)
        go.location = (300, 0)
        sep = g.nodes.new('ShaderNodeSeparateXYZ')
        sep.location = (-400, 0)
        g.links.new(gi.outputs[0], sep.inputs[0])
        mr = g.nodes.new('ShaderNodeMapRange')
        mr.location = (-200, 0)
        mr.inputs['From Min'].default_value = -1.0
        mr.inputs['From Max'].default_value = 1.0
        g.links.new(sep.outputs[2], mr.inputs['Value'])
        ramp = g.nodes.new('ShaderNodeValToRGB')
        ramp.location = (0, 0)
        cr = ramp.color_ramp
        # display-space values (game composes in display space)
        # neutral stand-in, not game data: dark ground, mid-grey horizon, slightly blue zenith
        cr.elements[0].position = 0.0
        cr.elements[0].color = (0.06, 0.06, 0.06, 1.0)      # ground
        cr.elements[1].position = 1.0
        cr.elements[1].color = (0.30, 0.36, 0.46, 1.0)      # zenith
        e = cr.elements.new(0.48)
        e.color = (0.12, 0.12, 0.12, 1.0)
        e = cr.elements.new(0.52)
        e.color = (0.40, 0.40, 0.42, 1.0)                   # horizon
        g.links.new(mr.outputs[0], ramp.inputs[0])
        g.links.new(ramp.outputs[0], go.inputs[0])
        g.links.new(ramp.outputs[0], go.inputs[1])
        return g

    def _build_material(name, prog, ctx):
        """one Blender material per distinct pass list

        each pass computes Cs/As from its texture and vertex colour (MODULATE), and its ALPHA register composes it over running result
        framebuffer alpha Ad is tracked through passes for destination-alpha reflection passes and DATE test

        shading 'GAME': colours stay in display space and are composed with GS equations (exact for opaque surfaces), emitted unlit
        runtime env/sky maps come from 'Enthusia Env' node group
        shading 'LIT': linear colours on a Principled base, overlays as Mix/Add shaders, runtime reflections as Glossy closures of world (alpha factors linear, colours converted with gamma 2.2)
        """
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        nb = _NB(nt)
        game = ctx['shading'] == 'GAME'
        refl_on = ctx['reflections']
        # shade (VU: 128*(1-P) + w3*P from first pass)
        if ctx['apply_shade']:
            attr = nb.new('ShaderNodeAttribute', 0, label='EnthusiaShade')
            attr.attribute_name = 'EnthusiaShade'
            p = nb.value(prog['p'], 0, name='ENT_p', label='VU shade P')
            omp = nb.math('SUBTRACT', 1.0, p, col=1)
            sh = nb.math('MULTIPLY_ADD', attr.outputs['Fac'], p, omp, col=1)
            shade = nb.math('MAXIMUM', sh, 0.0, col=2)
        else:
            shade = 1.0
        refl_vec = None
        env_out = None
        if game:
            tc = nb.new('ShaderNodeTexCoord', 0)
            refl_vec = tc.outputs['Reflection']
            grp = nb.new('ShaderNodeGroup', 1, label='Enthusia Env')
            grp.node_tree = _env_group()
            nt.links.new(refl_vec, grp.inputs[0])
            env_out = grp

        def to_lin(c, col):
            return nb.gamma(c, col)

        # running state
        S = None             # closure (LIT, or GAME transparent base)
        C = None             # display colour (GAME)
        cover = 1.0          # GAME coverage of C
        Cadd = None          # GAME additive terms over a non-opaque base
        Ad = 0.0
        transparent = False
        stored = []
        col = 3
        for k, ps in enumerate(prog['passes']):
            stored.append(dict(col_pre=list(ps['col_pre']), slot=ps['slot'],
                               mode=ps['mode'], routine=ps['routine']))
            cm, am = write_masks(ps)
            tex = ps['tex']
            if (cm == 'none' and am == 'none') or tex == 'runtime':
                continue
            c0 = col
            col += 6
            # vertex colour (display space, 1.0 = 0x80)
            if ps.get('vcol'):
                # courses: per-vertex RGBA from data (1.0 = 0x80)
                va = nb.new('ShaderNodeAttribute', c0, label='EnthusiaColor')
                va.attribute_name = 'EnthusiaColor'
                vc = va.outputs['Color']
                av = va.outputs['Alpha']
            else:
                rgb = nb.vec(ps['rgb'], c0, name='ENT_%d_rgb' % k,
                             label='pass %d rgb (m%d)' % (k, ps['mi']))
                vc = nb.vmath('SCALE', rgb, col=c0 + 1, scale=shade)
                if ps['rgb_clamp']:
                    cl = ps['rgb_clamp']
                    vc = nb.vmath('MINIMUM', vc, (cl, cl, cl), col=c0 + 1)
                av = nb.value(ps['av'] / 128.0, c0, name='ENT_%d_av' % k,
                              label='pass %d vertex A' % k)
            # Cs (display space for GAME, linear for LIT) and As
            runtime_refl = tex in ('env', 'sky')
            img = ctx['image'](tex) if isinstance(tex, tuple) else None
            if runtime_refl:
                As = av                          # TCC=0: As = vertex alpha
                if game:
                    Cs = nb.vmath('MULTIPLY',
                                  env_out.outputs['Env' if tex == 'env'
                                                  else 'Sky'],
                                  vc, col=c0 + 3)
                else:
                    Cs = to_lin(vc, c0 + 2)      # glossy tint
            elif img is not None:
                t = _tex_node(nb, img, ps['uv'], c0 + 1,
                              ctx.get('interp', 'Closest'),
                              ps.get('clamp', 0))
                Ct = t.outputs['Color']
                if game:
                    Cs = nb.vmath('MULTIPLY', Ct, vc, col=c0 + 3)
                else:
                    Cs = nb.vmath('MULTIPLY', Ct, to_lin(vc, c0 + 2),
                                  col=c0 + 3)
                As = nb.mul(t.outputs['Alpha'], av, col=c0 + 3)
            else:
                # untextured (PRIM TME=0): Cs is vertex colour byte
                # runtime-resident records (TBP 0x3FFF) have no texels in file and get a neutral 0.18 stand-in
                f = 128.0 / 255.0 if tex is None else 0.18
                cd = nb.vmath('SCALE', vc, col=c0 + 2, scale=f)
                Cs = cd if game else to_lin(cd, c0 + 2)
                As = av
                if tex not in (None,):
                    mat['enthusia_resident'] = 1
            if game:
                Cs = nb.vmath('MINIMUM', Cs, (1.0, 1.0, 1.0), col=c0 + 3)
            # write masks
            keep = 1.0
            if 'test' in (cm, am):
                keep = _test_node(nb, ps, As, c0 + 4)
            gate = 1.0
            if ps['date']:
                if isinstance(Ad, float):
                    hit = (Ad * 128.0) >= 128.0
                    gate = 1.0 if (hit == bool(ps['datm'])) else 0.0
                else:
                    gate = nb.math('LESS_THAN' if not ps['datm'] else
                                   'GREATER_THAN', Ad, 127.5 / 128.0,
                                   col=c0 + 4)
            cw = 0.0 if cm == 'none' else \
                nb.mul(keep if cm == 'test' else 1.0, gate, col=c0 + 4)
            eq = ps['eq']
            skip_colour = isinstance(cw, float) and cw == 0.0
            if runtime_refl and not refl_on:
                skip_colour = True
            if eq in ('add', 'add_dest', 'blend', 'blend_dest'):
                fsrc = As if eq in ('add', 'blend') else Ad
                f = nb.mul(fsrc, cw, col=c0 + 4) if not skip_colour else 0.0
            else:
                f = cw
            # colour composition
            if not skip_colour:
                if game:
                    first = C is None and S is None
                    if first:
                        if eq == 'replace' and isinstance(f, float) \
                                and f == 1.0:
                            C, cover = Cs, 1.0
                        elif eq in ('replace', 'blend'):
                            C, cover = Cs, f
                            transparent = True
                        elif eq == 'add':
                            Cadd = nb.vmath('SCALE', Cs, col=c0 + 5, scale=f)
                            C, cover = (0.0, 0.0, 0.0), 0.0
                            transparent = True
                        else:                 # dest-alpha first: no-op
                            C, cover = (0.0, 0.0, 0.0), 0.0
                            transparent = True
                    elif eq in ('replace', 'blend', 'blend_dest'):
                        d = nb.vmath('SUBTRACT', Cs, C, col=c0 + 5)
                        d = nb.vmath('SCALE', d, col=c0 + 5, scale=f)
                        C = nb.vmath('ADD', C, d, col=c0 + 5)
                        if not (isinstance(cover, float) and cover == 1.0):
                            omc = nb.math('SUBTRACT', 1.0, cover, col=c0 + 5)
                            cover = nb.math('MULTIPLY_ADD', omc, f, cover,
                                            col=c0 + 5)
                    elif eq in ('add', 'add_dest'):
                        term = nb.vmath('SCALE', Cs, col=c0 + 5, scale=f)
                        if isinstance(cover, float) and cover == 1.0:
                            C = nb.vmath('ADD', C, term, col=c0 + 5)
                        else:
                            Cadd = term if Cadd is None else \
                                nb.vmath('ADD', Cadd, term, col=c0 + 5)
                    if C is not None and not isinstance(C, tuple):
                        C = nb.vmath('MINIMUM', C, (1.0, 1.0, 1.0),
                                     col=c0 + 6)       # COLCLAMP
                else:
                    if runtime_refl:
                        if eq in ('add', 'add_dest'):
                            if S is None:
                                S = _transparent(nb, c0 + 5)
                                transparent = True
                            g = _glossy_node(nb, c0 + 5)
                            if g is not None:
                                gc = nb.vmath('SCALE', Cs, col=c0 + 5,
                                              scale=f)
                                nb.put(g.inputs['Color'], gc)
                                g.inputs['Roughness'].default_value = \
                                    ctx['refl_roughness']
                                S = nb.add(S, g.outputs[0], c0 + 6)
                    elif S is None:
                        if eq == 'replace':
                            S = _surface(nb, Cs, c0 + 5, ctx)
                            if not (isinstance(f, float) and f == 1.0):
                                S = nb.mix(f, _transparent(nb, c0 + 5), S,
                                           c0 + 6)
                                transparent = True
                        elif eq == 'blend':
                            S = nb.mix(f, _transparent(nb, c0 + 5),
                                       _surface(nb, Cs, c0 + 5, ctx), c0 + 6)
                            transparent = True
                        elif eq == 'add':
                            e = _emission(nb, nb.vmath('SCALE', Cs,
                                                       col=c0 + 5, scale=f),
                                          c0 + 5)
                            S = nb.add(_transparent(nb, c0 + 5), e, c0 + 6)
                            transparent = True
                        else:
                            S = _transparent(nb, c0 + 5)
                            transparent = True
                    else:
                        if eq in ('replace', 'blend', 'blend_dest'):
                            S = nb.mix(f, S, _surface(nb, Cs, c0 + 5, ctx),
                                       c0 + 6)
                        elif eq in ('add', 'add_dest'):
                            e = _emission(nb, nb.vmath('SCALE', Cs,
                                                       col=c0 + 5, scale=f),
                                          c0 + 5)
                            S = nb.add(S, e, c0 + 6)
            elif game and C is None and S is None and eq == 'noop':
                C, cover = (0.0, 0.0, 0.0), 0.0
                transparent = True
            # framebuffer alpha
            if am != 'none':
                wa = nb.mul(keep if am == 'test' else 1.0, gate, col=c0 + 4)
                if isinstance(wa, float) and wa == 1.0:
                    Ad = As
                elif not (isinstance(wa, float) and wa == 0.0):
                    if isinstance(Ad, float) and isinstance(As, float) \
                            and isinstance(wa, float):
                        Ad = Ad + (As - Ad) * wa
                    else:
                        n = nb.new('ShaderNodeMix', c0 + 5)
                        n.data_type = 'FLOAT'
                        nb.put(n.inputs['Factor'], wa)
                        nb.put(n.inputs[2], Ad)
                        nb.put(n.inputs[3], As)
                        Ad = n.outputs[0]
        # final shader
        if game:
            if C is None:
                S = _transparent(nb, col)
                transparent = True
            else:
                if isinstance(C, tuple):
                    C = nb.vec(C, col)
                e = _emission(nb, to_lin(C, col), col + 1)
                if isinstance(cover, float) and cover == 1.0:
                    S = e
                else:
                    S = nb.mix(cover, _transparent(nb, col + 1), e, col + 2)
                if Cadd is not None:
                    S = nb.add(S, _emission(nb, to_lin(nb.vmath(
                        'MINIMUM', Cadd, (1.0, 1.0, 1.0), col=col),
                        col + 1), col + 1), col + 2)
        elif S is None:
            S = _transparent(nb, col)
            transparent = True
        # one-sided as on PS2 (VU1 culls back faces by screen winding)
        # EEVEE also honours use_backface_culling, Cycles needs this mix
        # ctx cull False (course option) keeps both sides
        cull = ctx.get('cull', True)
        if cull:
            geo = nb.new('ShaderNodeNewGeometry', col + 2)
            S = nb.mix(geo.outputs['Backfacing'], S,
                       _transparent(nb, col + 2), col + 3)
        out = nb.new('ShaderNodeOutputMaterial', col + 4)
        nt.links.new(S, out.inputs['Surface'])
        mat.use_backface_culling = cull
        _set_blend(mat, 'BLEND' if transparent else 'OPAQUE')
        if cull:
            try:
                mat.show_transparent_back = False
            except Exception:
                pass
        mat['enthusia_prog'] = _json.dumps(stored)
        mat['enthusia_passes'] = ' '.join(
            'm%d:%s/%s' % (ps['mi'], ps['routine'], ps['eq'])
            for ps in prog['passes'])
        return mat

    def _update_material_paint(mat, vecs, env_k):
        """rewrite paint-dependent constants of an imported material (pass rgb, vertex alpha, shade P) for another paint colour"""
        try:
            stored = _json.loads(mat.get('enthusia_prog', '[]'))
        except Exception:
            return False
        nodes = mat.node_tree.nodes if mat.node_tree else None
        if not nodes or not stored:
            return False
        for k, st in enumerate(stored):
            rgb, av, p, _ = pass_constants(st['col_pre'], st['slot'],
                                           st['mode'], st['routine'],
                                           vecs, env_k)
            n = nodes.get('ENT_%d_rgb' % k)
            if n is not None:
                for i in range(3):
                    n.inputs[i].default_value = rgb[i]
            n = nodes.get('ENT_%d_av' % k)
            if n is not None:
                n.outputs[0].default_value = av / 128.0
            if k == 0:
                n = nodes.get('ENT_p')
                if n is not None:
                    n.outputs[0].default_value = p
        return True

    def _build_node_object(model, node, prefix, coll, ctx, mirror=False):
        merged_v = []
        faces = []
        face_mats = []
        keys = []
        vbase = 0
        sx = -1.0 if mirror else 1.0
        for msh in node['meshes']:
            key = tuple(msh['passes'])
            prog = ctx['program'](key)
            vs = msh['verts']
            merged_v.extend(_cnv((v[0] * sx, v[1], v[2])) for v in vs)
            if prog is not None:
                if key not in keys:
                    keys.append(key)
                slot = keys.index(key)
                for tri in msh['faces']:
                    idx = []
                    for corner in tri:
                        pi, ni, ti = corner[0], corner[1], corner[2]
                        w3 = corner[3] if len(corner) > 3 else 128
                        if pi >= len(vs):
                            idx = None
                            break
                        n = msh['norms'][ni] if msh['norms'] and ni < len(msh['norms']) else None
                        if n is not None and mirror:
                            n = (-n[0], n[1], n[2])
                        uv = msh['uvs'][ti] if msh['uvs'] and ti < len(msh['uvs']) else (0.0, 0.0)
                        idx.append((vbase + pi, n, uv, w3))
                    if not idx:
                        continue
                    a, b, c = idx
                    if mirror:
                        a, c = c, a               # keep winding after mirror
                    if a[0] == b[0] or b[0] == c[0] or a[0] == c[0]:
                        continue                      # degenerate
                    faces.append((a, b, c))
                    face_mats.append(slot)
            vbase += len(vs)
        if not faces:
            return None
        # drop vertices no drawn face uses
        used = sorted({l[0] for f in faces for l in f})
        remap = {o: i for i, o in enumerate(used)}
        mesh = bpy.data.meshes.new('%s_%s' % (prefix, node['name']))
        mesh.from_pydata([merged_v[i] for i in used], [],
                         [tuple(remap[l[0]] for l in f) for f in faces])
        mesh.update()
        uvl = mesh.uv_layers.new(name='UVMap')
        loop_normals = [(0.0, 0.0, 0.0)] * len(mesh.loops)
        shades = [1.0] * len(mesh.loops)
        for poly in mesh.polygons:
            if poly.index >= len(faces):
                break
            f = faces[poly.index]
            poly.material_index = face_mats[poly.index]
            for k in range(min(poly.loop_total, len(f))):
                li = poly.loop_start + k
                l = f[k]
                uvl.data[li].uv = (l[2][0], 1.0 - l[2][1])
                nn = l[1]
                # stored normals point into surface (opposite to drawn winding), so they are negated for Blender's shading normals
                # they are stored at length 0.5 and normalised here, as some Blender versions encode non-unit custom normals wrongly
                if nn:
                    nl_ = (nn[0] * nn[0] + nn[1] * nn[1] +
                           nn[2] * nn[2]) ** 0.5
                    loop_normals[li] = tuple(-x / nl_ for x in _cnv(nn)) \
                        if nl_ > 1e-9 else (0.0, 0.0, 0.0)
                else:
                    loop_normals[li] = (0.0, 0.0, 0.0)
                shades[li] = (l[3] if len(l) > 3 else 128) / 128.0
        # per-vertex prelit shade w3/128 (strip record w field, 128 = neutral)
        # materials apply VU blend 1-P + w3/128*P
        try:
            att = mesh.color_attributes.new('EnthusiaShade',
                                            'FLOAT_COLOR', 'CORNER')
            for li, s in enumerate(shades):
                att.data[li].color = (s, s, s, 1.0)
        except Exception:
            pass
        if any(n != (0.0, 0.0, 0.0) for n in loop_normals):
            try:
                if hasattr(mesh, 'use_auto_smooth'):      # < 4.1
                    mesh.use_auto_smooth = True
                # one normal per corner, as stored: with every face smooth and every edge sharp, each corner is its own fan and Blender does not average custom normals
                mesh.polygons.foreach_set('use_smooth',
                                          [True] * len(mesh.polygons))
                mesh.edges.foreach_set('use_edge_sharp',
                                       [True] * len(mesh.edges))
                mesh.normals_split_custom_set(loop_normals)
            except Exception:
                pass
        for key in keys:
            mesh.materials.append(ctx['material'](key))
        obj = bpy.data.objects.new(mesh.name, mesh)
        coll.objects.link(obj)
        return obj

    def _build_course_node(model, node, prefix, coll, ctx, name, want):
        """build one object per course node

        want(f10) selects packets by their draw flags (+0x10)
        vertices stay in node space, object gets node render matrix
        """
        verts = []
        faces = []
        face_mats = []
        loops = []          # (uv, rgba) per face corner
        keys = []
        for b in node['batches']:
            if not want(b['f10']):
                continue
            key = tuple(b['passes'])
            prog = ctx['program'](key)
            if prog is None:
                continue
            if key not in keys:
                keys.append(key)
            slot = keys.index(key)
            base = len(verts)
            verts.extend(_cnv(p) for p in b['pos'])
            for tri in course_triangles(b):
                ia, ib, ic = tri
                pa, pb, pc = b['pos'][ia], b['pos'][ib], b['pos'][ic]
                if pa == pb or pb == pc or pa == pc:
                    continue
                faces.append((base + ia, base + ib, base + ic))
                face_mats.append(slot)
                loops.append(tuple((b['uv'][j], b['col'][j]) for j in tri))
        if not faces:
            return None
        used = sorted({i for f in faces for i in f})
        remap = {o: i for i, o in enumerate(used)}
        mesh = bpy.data.meshes.new('%s_%s' % (prefix, name))
        mesh.from_pydata([verts[i] for i in used], [],
                         [tuple(remap[i] for i in f) for f in faces])
        mesh.update()
        # per-corner data, filled in face order (one loop per corner)
        npoly = len(mesh.polygons)
        nloop = len(mesh.loops)
        starts = [0] * npoly
        mesh.polygons.foreach_get('loop_start', starts)
        uvs = [0.0] * (2 * nloop)
        cols = [1.0] * (4 * nloop)
        for fi in range(min(npoly, len(faces))):
            li = starts[fi]
            for (u, v), c in loops[fi]:
                # VU routine 0x3BA: uv = integer / 512 (+ runtime scroll)
                uvs[2 * li] = u / 512.0
                uvs[2 * li + 1] = 1.0 - v / 512.0
                o = 4 * li
                cols[o] = c[0] / 128.0
                cols[o + 1] = c[1] / 128.0
                cols[o + 2] = c[2] / 128.0
                cols[o + 3] = c[3] / 128.0
                li += 1
        mats = face_mats[:npoly] + [0] * max(0, npoly - len(face_mats))
        mesh.polygons.foreach_set('material_index', mats)
        # create every corner layer first, then look layers up by name before writing
        # adding a layer can reallocate corner data, so a reference taken earlier may point at freed memory
        mesh.uv_layers.new(name='UVMap')
        has_col = True
        try:
            mesh.color_attributes.new('EnthusiaColor', 'FLOAT_COLOR',
                                      'CORNER')
        except Exception:
            has_col = False
        mesh.uv_layers['UVMap'].data.foreach_set('uv', uvs)
        if has_col:
            mesh.color_attributes['EnthusiaColor'].data.foreach_set(
                'color', cols)
        for key in keys:
            mesh.materials.append(ctx['material'](key))
        obj = bpy.data.objects.new(mesh.name, mesh)
        coll.objects.link(obj)
        m = node['matrix']
        if m != [(1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, 0)]:
            # row-vector matrix in game space -> Blender (C * M * C^-1)
            C = Matrix(_PS2_TO_BL)
            R = Matrix((m[0], m[1], m[2])).transposed()
            Rb = C @ R @ C.transposed()
            M4 = Rb.to_4x4()
            M4.translation = Vector(_cnv(m[3]))
            obj.matrix_world = M4
        return obj

    def _import_course(op, context, model, stem, prefix):
        images = {}
        raw = op.shading == 'GAME'
        for i, tex in model.textures.items():
            images[i] = _make_image('%s_tex%03d' % (prefix, i), tex, raw)

        def image_for(ref):
            kind, idx = ref
            return images.get(idx) if kind == 'rec' else None

        prog_cache = {}
        mat_cache = {}

        def program(key):
            if key not in prog_cache:
                prog_cache[key] = course_program(model, list(key))
            return prog_cache[key]

        ctx = dict(image=image_for, program=program,
                   reflections=op.reflections,
                   refl_roughness=op.refl_roughness,
                   shading=op.shading, apply_shade=False, interp='Linear',
                   cull=op.course_cull)

        def material(key):
            if key not in mat_cache:
                mat_cache[key] = _build_material(
                    '%s_m%s' % (prefix, '_'.join(str(x) for x in key)),
                    program(key), ctx)
            return mat_cache[key]
        ctx['material'] = material
        # sky dome is a backdrop: unlit in LIT mode too (in Cycles it then also lights course like an environment)
        sky_ctx = dict(ctx, unlit=True)

        def sky_material(key):
            if ctx['shading'] == 'GAME':
                return material(key)
            k2 = ('sky',) + key
            if k2 not in mat_cache:
                mat_cache[k2] = _build_material(
                    '%s_sky_m%s' % (prefix, '_'.join(str(x) for x in key)),
                    program(key), sky_ctx)
            return mat_cache[k2]
        sky_ctx['material'] = sky_material

        import re
        mnum = re.match(r'^(\d{3})(?:_\d+)?$', stem)
        cname = course_name(int(mnum.group(1))) if mnum else None
        root = bpy.data.collections.new(
            '%s %s' % (stem, cname) if cname else stem)
        context.scene.collection.children.link(root)
        root['enthusia_course'] = prefix
        if cname:
            root['enthusia_course_name'] = cname
        n_obj = 0
        groups = [('main', lambda f: f & 1, root)]
        if op.course_extra:
            extra = bpy.data.collections.new('%s_other_passes' % prefix)
            root.children.link(extra)
            groups.append(('alt', lambda f: not (f & 1), extra))
        lo, hi, base = course_extent(model)
        for node in model.nodes:
            if node['sky'] and not op.course_sky:
                continue
            for tag, want, coll in groups:
                name = 'sky' if node['sky'] else 'n%03d' % node['index']
                if tag != 'main':
                    name += '_' + tag
                obj = _build_course_node(model, node, prefix, coll,
                                         sky_ctx if node['sky'] else ctx,
                                         name, want)
                if obj is None:
                    continue
                obj['enthusia_node'] = node['index']
                obj['enthusia_flags'] = node['flags']
                if node['object_id'] >= 0:
                    obj['enthusia_object_id'] = node['object_id']
                if node['sky']:
                    # a backdrop: let sun through (dome encloses course) while still lighting course as an environment
                    try:
                        obj.visible_shadow = False
                    except AttributeError:
                        pass
                    for msl in obj.material_slots:
                        if msl.material is not None and \
                                hasattr(msl.material, 'shadow_method'):
                            try:
                                msl.material.shadow_method = 'NONE'
                            except Exception:
                                pass
                if node['sky'] and op.course_sky_fit and lo[0] < hi[0]:
                    # game draws node 0 centred on camera with view rotation only
                    # for a static scene it is centred on course with its horizon at lowest static geometry, and scaled until it encloses every node
                    r_sky = min(max(abs(node['bbox_min'][0]), node['bbox_max'][0],
                                    abs(node['bbox_min'][2]), node['bbox_max'][2]),
                                node['bbox_max'][1])
                    cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
                    reach = (max(hi[0] - cx, cx - lo[0]) ** 2 +
                             max(hi[2] - cz, cz - lo[2]) ** 2 +
                             max(hi[1] - base, 0.0) ** 2) ** 0.5
                    f = max(1.0, 1.02 * reach / max(r_sky, 1e-3))
                    obj.scale = (f, f, f)
                    obj.location = Vector(_cnv((cx, base, cz)))
                    obj['enthusia_sky_scale'] = f
                n_obj += 1
        # courses span kilometres (fitted sky even more): raise 3D views' clip end if it would cut scene off (never lowered)
        if lo[0] < hi[0]:
            span = 2.0 * max(hi[0] - lo[0], hi[2] - lo[2])
            try:
                for area in context.screen.areas:
                    if area.type != 'VIEW_3D':
                        continue
                    for space in area.spaces:
                        if space.type == 'VIEW_3D' and space.clip_end < span:
                            space.clip_end = span
            except AttributeError:
                pass
        for wmsg in model.warnings:
            op.report({'WARNING'}, wmsg)
        ver = '.'.join(str(x) for x in _VERSION)
        op.report({'INFO'}, 'Enthusia v%s course %s%s: %d objects, %d textures, '
                  '%d materials' % (ver, prefix,
                                    ' (%s)' % cname if cname else '',
                                    n_obj, len(model.textures),
                                    len(mat_cache)))
        return {'FINISHED'}


    class ImportEnthusiaVgs(bpy.types.Operator, ImportHelper):
        """Import an Enthusia Professional Racing car (carpk, selcarpk) or course (mappk) pack"""
        bl_idname = 'import_scene.enthusia_vgs'
        bl_label = 'Import Enthusia car / course'
        bl_options = {'UNDO'}
        filename_ext = '.pkd'
        filter_glob: bpy.props.StringProperty(
            default='*.pkd;*.vgs;*.bin', options={'HIDDEN'})

        all_lods: bpy.props.BoolProperty(
            name='Import all LODs',
            description='Import LOD1-3 in extra collections',
            default=False)
        place_parts: bpy.props.BoolProperty(
            name='Place wheels & brakes',
            description='Position wheel/brake nodes from the car spec '
                        '(wheelbase/track); otherwise leave them at origin',
            default=True)
        skip_shadow: bpy.props.BoolProperty(
            name='Skip shadow mesh', default=True)
        paint_index: bpy.props.IntProperty(
            name='Paint colour',
            description='Index into the car\'s official colour list (paint '
                        'table in selcarpk, sub-entry 3). Can be changed '
                        'after import in the 3D view sidebar (Enthusia tab)',
            default=0, min=0, max=63)
        reflections: bpy.props.BoolProperty(
            name='Reflections',
            description='Reproduce the destination-alpha reflection passes '
                        '(runtime env/sky maps) as glossy closures that '
                        'reflect the Blender world, weighted as in the game '
                        '(paint alpha, texture alpha, DATE test, paint '
                        'env/sky tints)',
            default=True)
        env_strength: bpy.props.FloatProperty(
            name='Env intensity',
            description='Runtime env-map intensity (model+0x200 x '
                        'model+0x2F0/255, set by the race code). 1.0 = '
                        'full', default=1.0, min=0.0, max=4.0)
        refl_roughness: bpy.props.FloatProperty(
            name='Reflection roughness',
            description='Roughness of the glossy closure standing in for '
                        'the runtime env/sky textures', default=0.0,
            min=0.0, max=1.0)
        show_lamps: bpy.props.BoolProperty(
            name='Lamp & glow layers',
            description='Draw material groups 2-8 and 10-14 (lamp glows, '
                        'brake-disc glow). At load the game enables only '
                        'groups 0 and 15', default=False)
        shading: bpy.props.EnumProperty(
            name='Shading',
            items=(('GAME', 'Game (unlit, exact GS math)', 'No dynamic '
                    'lighting, as in the game (baked per-vertex shade '
                    'only). Passes composed with the GS equations in '
                    'display space; the runtime env/sky maps come from the '
                    'editable "Enthusia Env" node group'),
                   ('LIT', 'Lit (Principled)', 'Diffuse surfaces lit by '
                    'the scene; reflections are Glossy closures of the '
                    'world; GS passes approximated in linear space')),
            default='GAME')
        apply_shade: bpy.props.BoolProperty(
            name='Apply baked vertex shading',
            description='VU shade 128*(1-P) + w3*P from the strip records '
                        '(EnthusiaShade attribute keeps the raw w3/128)',
            default=True)
        course_sky: bpy.props.BoolProperty(
            name='Course: sky dome',
            description='Import node 0, the sky dome the game draws centred '
                        'on the camera (no translation); it imports at the '
                        'course origin at its stored size',
            default=True)
        course_sky_fit: bpy.props.BoolProperty(
            name='Course: fit sky to course',
            description='Centre the sky dome on the course and scale it to '
                        'surround it (the game keeps it centred on the '
                        'camera); off = stored size at the origin',
            default=True)
        course_extra: bpy.props.BoolProperty(
            name='Course: other-pass geometry',
            description='Also import packets without draw flag bit 0 (not '
                        'drawn by the main course pass) into a separate '
                        'collection', default=False)
        course_cull: bpy.props.BoolProperty(
            name='Course: backface culling',
            description='Hide back faces as the game does (VU1 culls them '
                        'by screen winding); off shows both sides of every '
                        'face', default=True)
        load_pvram: bpy.props.BoolProperty(
            name='Load common textures (pvram)',
            description='Decode etc/etc/pvram_000_a.bin in colour for the '
                        'env-nibble materials (tyre sidewall/treads, '
                        'glare and glow sprites)', default=True)

        def draw(self, context):
            lay = self.layout
            lay.prop(self, 'shading')
            box = lay.box()
            box.label(text='Car (carpk / selcarpk)')
            for name in ('all_lods', 'place_parts', 'skip_shadow',
                         'paint_index', 'reflections', 'env_strength',
                         'refl_roughness', 'show_lamps', 'apply_shade',
                         'load_pvram'):
                box.prop(self, name)
            box = lay.box()
            box.label(text='Course (mappk)')
            for name in ('course_sky', 'course_sky_fit', 'course_extra',
                         'course_cull'):
                box.prop(self, name)

        def execute(self, context):
            try:
                model = load_file(self.filepath)
            except Exception as e:
                self.report({'ERROR'}, 'decode failed: %s' % e)
                return {'CANCELLED'}

            import os
            import re
            stem = os.path.splitext(os.path.basename(self.filepath))[0]
            if getattr(model, 'kind', 'car') == 'course':
                # enthusia_extract.py names map packs "NNN_00_Track Name.pkd"
                mcrs = re.match(r'^(\d{3}_\d{2})_.+$', stem)
                if mcrs:
                    stem = mcrs.group(1)
                return _import_course(self, context, model, stem, stem)
            # enthusia_extract.py names car packs "NNNNNNNN_Car Name.pkd"
            mname = re.match(r'^(\d{4,8})_(.+)$', stem)
            prefix = mname.group(1) if mname else stem
            car_name = mname.group(2) if mname else ''
            images = {}
            raw = self.shading == 'GAME'
            for i, tex in model.textures.items():
                images[i] = _make_image('%s_tex%02d' % (prefix, i), tex, raw)

            pv_entries = {}
            pv_images = {}
            if self.load_pvram:
                base = os.path.dirname(self.filepath)
                for rel in ('../../etc/etc/pvram_000_a.bin',
                            '../etc/etc/pvram_000_a.bin',
                            'pvram_000_a.bin'):
                    pth = os.path.normpath(os.path.join(base, rel))
                    if os.path.isfile(pth):
                        try:
                            ents = parse_pvram(open(pth, 'rb').read())
                        except Exception:
                            ents = None
                        for ent in ents or ():
                            pv_entries[ent['index']] = ent
                        break

            def image_for(ref):
                kind, idx = ref
                if kind == 'rec':
                    return images.get(idx)
                if kind == 'pvram':
                    if idx not in pv_images and idx in pv_entries:
                        pv_images[idx] = _make_image('pvram_%02d' % idx,
                                                     pv_entries[idx], raw)
                    return pv_images.get(idx)
                return None

            table = find_paint_table(self.filepath)
            colour = None
            if table:
                colour = table[min(self.paint_index, len(table) - 1)]
            vecs = paint_vectors(colour)
            groups = set(GROUPS_DEFAULT)
            if self.show_lamps:
                groups |= GROUPS_LAMPS
            prog_cache = {}
            mat_cache = {}

            def program(key):
                if key not in prog_cache:
                    prog_cache[key] = draw_program(
                        model, list(key), vecs, groups, self.env_strength)
                return prog_cache[key]

            ctx = dict(image=image_for, program=program,
                       reflections=self.reflections,
                       refl_roughness=self.refl_roughness,
                       shading=self.shading, apply_shade=self.apply_shade)

            def material(key):
                if key not in mat_cache:
                    mat_cache[key] = _build_material(
                        '%s_m%s' % (prefix, '_'.join(str(x) for x in key)),
                        program(key), ctx)
                return mat_cache[key]
            ctx['material'] = material

            root = bpy.data.collections.new(stem)
            context.scene.collection.children.link(root)
            if car_name:
                root['enthusia_car_name'] = car_name
                try:
                    root['enthusia_car_number'] = int(prefix)
                except ValueError:
                    pass
            if table:
                root['enthusia_paint_table'] = _json.dumps(table)
                root['enthusia_paint_index'] = table.index(colour)
                root['enthusia_paint_name'] = colour['name']
            root['enthusia_env_strength'] = self.env_strength

            spec = model.spec
            wheel_sides = {}
            n_lods = 4 if self.all_lods else 1
            for lod in range(n_lods):
                coll = root
                if self.all_lods:
                    coll = bpy.data.collections.new('%s_LOD%d' % (prefix, lod))
                    root.children.link(coll)
                for node in model.nodes:
                    if node['index'] // 16 != lod:
                        continue
                    slot = node['index'] % 16
                    if not node['meshes']:
                        continue
                    if self.skip_shadow and slot == 15:
                        continue
                    node['name'] = 'n%02d_%s' % (
                        node['index'], SLOT_NAMES.get(slot, 'part%d' % slot))
                    mtx = node['matrix']
                    # +/-1 mirror on X, not applied to wheel/brake nodes (slots 1-8)
                    # their pools are already mirrored per side, and some cars also set m00 = -1 on right-side nodes
                    # game replaces that matrix with dynamic spin transforms, so applying it would mirror mesh twice
                    mirror = mtx[0][0] < 0 and slot not in (
                        1, 2, 3, 4, 5, 6, 7, 8)
                    obj = _build_node_object(model, node, prefix, coll, ctx,
                                             mirror=mirror)
                    if obj is None:
                        continue
                    loc = Vector(_cnv(mtx[3][:3]))
                    if self.place_parts and spec:
                        # model origin sits on rear axle (rear wheel-arch centres are at z = 0)
                        z_r = 0.0
                        z_f = spec['wheelbase']
                        radius = node['bbox_max'][1]
                        if slot in (1, 2, 3, 4, 5, 6, 7, 8):
                            front = slot in (1, 2, 5, 6)
                            tr = spec['track_f'] if front else spec['track_r']
                            fx = _wheel_face_x(node)
                            if fx == 0.0 and slot in (5, 6, 7, 8):
                                fx = wheel_sides.get(slot - 4, fx)
                            # visible wheel face is opposite to stored normals (same relation as drawn winding)
                            side = -1.0 if fx > 0 else 1.0
                            if slot in (1, 2, 3, 4):
                                wheel_sides[slot] = fx
                            x = side * tr / 2
                            z = z_f if front else z_r
                            loc = Vector(_cnv((x, radius, z)))
                            node['name'] = 'n%02d_%s_%s%s' % (
                                node['index'],
                                'wheel' if slot <= 4 else 'brake',
                                'F' if front else 'R',
                                'L' if side > 0 else 'R')
                            obj.name = node['name']
                            obj.data.name = '%s_%s' % (prefix, node['name'])
                    obj.location = loc
                    obj['enthusia_node'] = node['index']
                    obj['enthusia_flags'] = node['flags']

            for (x, y, z, code) in model.attach:
                e = bpy.data.objects.new(
                    '%s_attach_%03x' % (prefix, code), None)
                e.empty_display_type = 'SPHERE'
                e.empty_display_size = 0.06
                e.location = Vector(_cnv((x, y, z)))
                root.objects.link(e)

            for wmsg in model.warnings:
                self.report({'WARNING'}, wmsg)
                print('[Enthusia]  WARNING: %s' % wmsg)
            ver = '.'.join(str(x) for x in _VERSION)
            self.report({'INFO'},
                        'Enthusia v%s: %d nodes, %d textures, %d materials, '
                        'paint: %s'
                        % (ver, sum(1 for n in model.nodes if n['meshes']),
                           len(model.textures), len(mat_cache),
                           colour['name'] if colour else
                           'no paint table found (neutral)'))
            return {'FINISHED'}

    def _car_root(obj):
        if obj is None:
            return None
        for c in bpy.data.collections:
            if 'enthusia_paint_table' in c and obj.name in c.all_objects:
                return c
        return None

    class EnthusiaSetPaint(bpy.types.Operator):
        bl_idname = 'enthusia.set_paint'
        bl_label = 'Set Enthusia paint colour'
        bl_options = {'UNDO'}
        index: bpy.props.IntProperty(default=0, min=0)
        collection: bpy.props.StringProperty()

        def execute(self, context):
            root = bpy.data.collections.get(self.collection) \
                or _car_root(context.active_object)
            if root is None:
                self.report({'ERROR'}, 'no imported Enthusia car selected')
                return {'CANCELLED'}
            table = _json.loads(root['enthusia_paint_table'])
            colour = table[min(self.index, len(table) - 1)]
            vecs = paint_vectors(colour)
            env_k = float(root.get('enthusia_env_strength', 1.0))
            mats = set()
            for ob in root.all_objects:
                for ms in getattr(ob, 'material_slots', ()):
                    if ms.material is not None:
                        mats.add(ms.material)
            n = sum(1 for m in mats if _update_material_paint(m, vecs, env_k))
            root['enthusia_paint_index'] = table.index(colour)
            root['enthusia_paint_name'] = colour['name']
            self.report({'INFO'}, '%s: %d materials updated'
                        % (colour['name'], n))
            return {'FINISHED'}

    class ENTHUSIA_PT_paint(bpy.types.Panel):
        bl_label = 'Enthusia paint'
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = 'Enthusia'

        def draw(self, context):
            root = _car_root(context.active_object)
            lay = self.layout
            if root is None:
                lay.label(text='Select an imported Enthusia car')
                return
            lay.label(text=root.get('enthusia_car_name', root.name))
            table = _json.loads(root['enthusia_paint_table'])
            cur = root.get('enthusia_paint_index', 0)
            for i, c in enumerate(table):
                op = lay.operator('enthusia.set_paint',
                                  text=c['name'] or ('colour %d' % i),
                                  depress=(i == cur))
                op.index = i
                op.collection = root.name

    def menu_func_import(self, context):
        self.layout.operator(ImportEnthusiaVgs.bl_idname,
                             text='Enthusia car / course (.pkd/.vgs)')

    _CLASSES = (ImportEnthusiaVgs, EnthusiaSetPaint, ENTHUSIA_PT_paint)

    def register():
        print('[Enthusia] importer v%s registered'
              % '.'.join(str(x) for x in _VERSION))
        for c in _CLASSES:
            bpy.utils.register_class(c)
        bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    def unregister():
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
        for c in reversed(_CLASSES):
            bpy.utils.unregister_class(c)

    if __name__ == '__main__':
        register()

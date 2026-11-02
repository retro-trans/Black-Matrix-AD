"""MODE1/2352 EDC and P/Q parity, vectorised across independent sectors.

Same standard GF(256) arithmetic used by the local Rayblade disc builder.
Only bytes2064..2351 are regenerated; header and2048 user bytes stay exact.
"""
import numpy as np

EDC=[]
FORWARD=[]
BACKWARD=[0]*256
for i in range(256):
    x=i
    for _ in range(8):x=(x>>1)^(0xd8018001 if x&1 else 0)
    EDC.append(x)
    y=i<<1
    if y&256:y^=0x11d
    FORWARD.append(y);BACKWARD[i^y]=i
EDC=np.array(EDC,dtype=np.uint32)
FORWARD=np.array(FORWARD,dtype=np.uint8)
BACKWARD=np.array(BACKWARD,dtype=np.uint8)
SYNC=bytes.fromhex('00ffffffffffffffffffff00')


def _ecc(out,major_count,minor_count,major_mult,minor_inc):
    size=major_count*minor_count
    major=np.arange(major_count);index=(major>>1)*major_mult+(major&1)
    a=np.zeros((len(out),major_count),dtype=np.uint8);b=a.copy()
    for _ in range(minor_count):
        value=out[:,12+index];a^=value;b^=value;a=FORWARD[a]
        index=(index+minor_inc)%size
    a=BACKWARD[FORWARD[a]^b]
    return np.concatenate((a,a^b),axis=1)


def regenerate(raw):
    if not raw or len(raw)%2352:raise ValueError('Expected complete raw MODE1 sectors')
    out=np.frombuffer(raw,dtype=np.uint8).reshape(-1,2352).copy()
    if not np.all(out[:,:12]==np.frombuffer(SYNC,dtype=np.uint8)) or not np.all(out[:,15]==1):
        raise ValueError('Unexpected sector sync/mode')
    checksum=np.zeros(len(out),dtype=np.uint32)
    for i in range(2064):checksum=(checksum>>8)^EDC[(checksum^out[:,i])&255]
    out[:,2064:2068]=checksum.astype('<u4').view(np.uint8).reshape(-1,4)
    out[:,2068:2076]=0
    out[:,2076:2248]=_ecc(out,86,24,2,86)
    out[:,2248:2352]=_ecc(out,52,43,86,88)
    return out.tobytes()

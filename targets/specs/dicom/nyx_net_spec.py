import sys, os 
sys.path.insert(1, os.getenv("NYX_INTERPRETER_BUILD_PATH"))

from spec_lib.graph_spec import *
from spec_lib.data_spec import *
from spec_lib.graph_builder import *
from spec_lib.generators import opts,flags,limits,regex

import jinja2


s = Spec()
s.use_std_lib = False
s.includes.append("\"custom_includes.h\"")
s.includes.append("\"nyx.h\"")
s.interpreter_user_data_type = "socket_state_t*"

with open("send_code.include.c") as f:
    send_code = f.read() 

with open("send_code_raw.include.c") as f:
    send_code_raw = f.read() 

d_byte = s.data_u8("u8", generators=[limits(0x0, 0xff)])

d_bytes = s.data_vec("pkt_content", d_byte, size_range=(0,1<<12), generators=[]) #regex(pkt)

#n_pkt = s.node_type("packet", interact=True, data=d_bytes, code=send_code)
n_pkt = s.node_type("packet_raw", interact=True, data=d_bytes, code=send_code_raw)

snapshot_code="""
//hprintf("ASKING TO CREATE SNAPSHOT\\n");
kAFL_hypercall(HYPERCALL_KAFL_CREATE_TMP_SNAPSHOT, 0);
kAFL_hypercall(HYPERCALL_KAFL_USER_FAST_ACQUIRE, 0);
//hprintf("RETURNING FROM SNAPSHOT\\n");
vm->ops_i -= OP_CREATE_TMP_SNAPSHOT_SIZE;
"""
n_close = s.node_type("create_tmp_snapshot", code=snapshot_code)

s.build_interpreter()

import msgpack
serialized_spec = s.build_msgpack()
with open("nyx_net_spec.msgp","wb") as f:
    f.write(msgpack.packb(serialized_spec))


def split_packets(data):   
    i = 0
    res = []
    while i+6 < len(data):
        tt,content_len = struct.unpack(">2sI",data[i:i+6])  
        res.append( ["dicom", data[i:i+content_len+6]] )
        print(repr((tt, content_len , data[i:i+content_len])))
        i+=(content_len+6)
    return res

import pyshark
import glob

def stream_to_bin(path,stream):
    nodes = split_packets(stream)

    for (ntype, content) in nodes:
        b.packet(content)
    b.write_to_file(path+"2.bin")

def stream_to_bin2(path,stream):
    nodes = split_packets(stream)

    for (ntype, content) in nodes:
        b.packet_raw(content)
    b.write_to_file(path+"1.bin")

def stream_to_bin3(path,stream):
    nodes = split_packets(stream)
    #for (ntype, content) in nodes:
    #    b.packet_raw(content)
    b.packet_raw(stream)
    b.write_to_file(path+"2.bin")

# convert existing pcaps
for path in glob.glob("pcaps/*.pcap"):
    b = Builder(s)
    cap = pyshark.FileCapture(path, display_filter="tcp.dstport eq 5158")

    #ipdb.set_trace()
    stream = b""
    for pkt in cap:
        #print("LEN: ", repr((pkt.tcp.len, int(pkt.tcp.len))))
        if int(pkt.tcp.len) > 0:
            stream+=pkt.tcp.payload.binary_value
    stream_to_bin(path, stream)
    cap.close()

# convert afl net samples
for path in glob.glob("raw_streams/*.raw"):
    b = Builder(s)
    #with open(path,mode='rb') as f:
    #    stream_to_bin(path, f.read())
    with open(path,mode='rb') as f:
        stream_to_bin2(path, f.read())
    b = Builder(s)
    with open(path,mode='rb') as f:
        stream_to_bin3(path, f.read())

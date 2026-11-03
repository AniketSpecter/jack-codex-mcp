import ctypes as ct
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import native_bridge as b


class NativeProtocolTests(unittest.TestCase):
    def endpoint(self):
        return dict(protocol=1,pid=123,session_id="a"*32,token="b"*64,
                    pipe=rf"\\.\pipe\JACKCodex-123-{'a'*32}",exe_sha256=b.EXPECTED_EXE)

    def test_reject_remote_or_substituted_pipe(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"ep.json";ep=self.endpoint();p.write_text(json.dumps(ep))
            self.assertEqual(b._load_endpoint(p)["pid"],123)
            for name,value in [("pipe",r"\\remote\pipe\JACKCodex"),("pid",True),
                               ("token","wrong"),("exe_sha256","wrong")]:
                bad=dict(ep);bad[name]=value;p.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):b._load_endpoint(p)

    def test_response_identity_and_size(self):
        good=dict(id="r1",session_id="s1",result={"ok":True})
        self.assertTrue(b._decode_reply(json.dumps(good).encode(),"r1","s1")["ok"])
        for raw in [json.dumps(good).encode(),b"",b"x"*(b.MAX_RESPONSE+1),b'{}']:
            with self.assertRaises(ValueError):b._decode_reply(raw,"wrong","s1")

    def test_mutation_rejected_before_transport(self):
        with patch.object(b,"_endpoint_path",side_effect=AssertionError("Must not touch IPC")):
            with self.assertRaises(ValueError):b.request("create_brush")

    def test_stale_and_selection_filtering(self):
        result={"ok":True,"age_ms":11000,"document":{"selection":{"entities":[2],"brushes":[]},
            "entities":[{"editor_id":1},{"editor_id":2}],"brushes":[{"editor_id":9}]}}
        with patch.object(b,"request",return_value=result):
            s=b.read_snapshot(True)
        self.assertTrue(s["refresh_required"])
        self.assertEqual(s["entities"],[{"editor_id":2}]);self.assertEqual(s["brushes"],[])
        self.assertNotIn("document",s)

    @unittest.skipUnless(os.name=="nt" and (b.ROOT/"native/build/vpCodexBridgex64.dll").is_file(),"Requires built Windows DLL")
    def test_native_entry_rejects_bad_abi_without_editor(self):
        dll=ct.CDLL(str(b.ROOT/"native/build/vpCodexBridgex64.dll"))
        dll.vpMain.argtypes=[ct.c_void_p,ct.c_int];dll.vpMain.restype=ct.c_int
        self.assertEqual(dll.vpMain(None,100),10)
        self.assertEqual(dll.vpMain(None,10),-1)
        for n in (0,8,1463,1465,65536):
            size=ct.c_size_t(n)
            self.assertEqual(dll.vpMain(ct.byref(size),10),-1)
        buf=(ct.c_size_t*183)();buf[0]=1464
        self.assertEqual(dll.vpMain(buf,10),-1) # null required function pointers

if __name__=="__main__":unittest.main()

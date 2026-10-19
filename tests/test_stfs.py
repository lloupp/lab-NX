import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from nxlab.stfs import Package,StfsError,offset
from nxlab.xex import inspect,XexError

class StfsTests(unittest.TestCase):
    def test_hash_boundary(self):
        self.assertEqual(offset(169,0xc000,0x1000),0xb5000)
        self.assertEqual(offset(170,0xc000,0x1000),0xb8000)
    def test_bad_header(self):
        with TemporaryDirectory() as temp:
            p=Path(temp)/'broken'
            p.write_bytes(b'BAD!'*20000)
            with self.assertRaises(StfsError):
                Package(p)
    def test_fake_xex(self):
        with TemporaryDirectory() as temp:
            p=Path(temp)/'file.xex'
            p.write_bytes(b'NOT XEX2'+bytes(120))
            with self.assertRaises(XexError):
                inspect(p)
    def test_synthetic_package(self):
        with TemporaryDirectory() as temp:
            data=bytearray(0xe000)
            data[:4]=b'LIVE'
            data[0x344:0x348]=bytes.fromhex('000D0000')
            data[0x360:0x364]=bytes.fromhex('584108B7')
            data[0x379]=0x24
            data[0x37b]=1
            data[0x37c:0x37e]=(1).to_bytes(2,'little')
            row=bytearray(64)
            row[:11]=b'default.xex'
            row[40]=0x40|11
            row[41:44]=(1).to_bytes(3,'little')
            row[47:50]=(1).to_bytes(3,'little')
            row[50:52]=b'\xff\xff'
            row[52:56]=(48).to_bytes(4,'big')
            data[0xc000:0xc040]=row
            h=b'XEX2'+(1).to_bytes(4,'big')+(32).to_bytes(4,'big')+bytes(4)+(40).to_bytes(4,'big')+(1).to_bytes(4,'big')+bytes.fromhex('0001020100000020')
            data[0xd000:0xd000+len(h)]=h
            p=Path(temp)/'fixture.stfs'
            p.write_bytes(data)
            pkg=Package(p)
            self.assertEqual(pkg.inventory()['files'],1)
            out=Path(temp)/'default.xex'
            self.assertEqual(pkg.extract_xex(out)['magic'],'XEX2')
            self.assertEqual(inspect(out)['optional_header_count'],1)
            with self.assertRaises(FileExistsError):
                pkg.extract_xex(out)

if __name__=='__main__':
    unittest.main()

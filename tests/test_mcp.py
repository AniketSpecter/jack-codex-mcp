"""Real stdio handshake and file inspection; never modifies an editor."""
import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[1]

class McpTests(unittest.TestCase):
    def test_stdio_tools_and_temporary_file(self):
        async def run():
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'test.map';p.write_bytes((ROOT/'examples/simple.map').read_bytes());before=p.read_bytes()
                params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'server.py')],env={**os.environ,'JACK_PROJECT_ROOT':d,'JACK_ENABLE_LIVE_CONTROL':'0'})
                async with stdio_client(params) as (reader,writer):
                    async with ClientSession(reader,writer) as client:
                        await client.initialize()
                        names={v.name for v in (await client.list_tools()).tools}
                        self.assertEqual(len(names),18)
                        self.assertIn('jack_native_plan_edits',names);self.assertIn('jack_native_apply_edits',names)
                        result=await client.call_tool('inspect_map',{'relative_path':'test.map'})
                        self.assertFalse(result.is_error)
                        self.assertEqual(p.read_bytes(),before)
        asyncio.run(run())

if __name__=='__main__':unittest.main()

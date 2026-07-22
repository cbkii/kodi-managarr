import os,unittest,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
class MetadataTests(unittest.TestCase):
    def test_complete_context_scope_and_assets(self):
        root=ET.parse(ROOT/'addon.xml').getroot()
        args={item.attrib.get('args') for item in root.findall(".//extension[@point='kodi.context.item']//item")}
        self.assertEqual(args,{'menu'})
        assets=root.find("extension[@point='xbmc.addon.metadata']/assets")
        self.assertEqual(assets.findtext('icon'),'resources/icon.png')
        self.assertEqual(assets.findtext('fanart'),'resources/fanart.jpg')
    def test_modern_settings_schema(self):
        root=ET.parse(ROOT/'resources/settings.xml').getroot()
        self.assertEqual(root.attrib.get('version'),'1')
        self.assertIsNotNone(root.find("section[@id='context.arr.manager']"))
if __name__=='__main__': unittest.main()

#!/usr/bin/env python3

import unittest
import difflib

from xmlmerge4 import merge_tree, MergeError
from lxml import etree


class MergeXMLTestCase(unittest.TestCase):
    def merge_xml(self, l, r):
        parser = etree.XMLParser(remove_blank_text=True)
        ltree = etree.fromstring(l, parser)
        rtree = etree.fromstring(r, parser)
        xml = merge_tree(ltree, rtree)
        return etree.tostring(ltree, pretty_print=True).decode('utf-8')


class NothingTestCase(MergeXMLTestCase):

   def test_merge_nothing(self):
        l = """\
<config>
</config>
"""
        r = """\
<config>
</config>
"""
        o = """\
<config>
</config>
"""
        xml = self.merge_xml(r, l)
        self.assertEqual(xml, o)



class MergeTestCase(MergeXMLTestCase):

   def test_not_existing(self):
        l = """\
<config>
</config>
"""
        r = """\
<config>
  <a>
    <name>Kilroy</name>
  </a>
  <b>Bee</b>
</config>
"""
        o = """\
<config>
<a><name>Kilroy</name></a><b>Bee</b></config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_existing_single(self):
        l = """\
<config>
  <a>
    <name>Kilroy</name>
  </a>
  <b>Ahh</b>
</config>
"""
        r = """\
<config>
  <a>
    <age>42</age>
  </a>
  <b>Bee</b>
</config>
"""
        o = """\
<config>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
  <b>Ahh</b>
  <b>Bee</b>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_existing_multiple(self):
        l = """\
<config>
  <a>
    <name>Kilroy</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
  <b>Ahh</b>
  <b>Ahh</b>
</config>
"""
        r = """\
<config>
  <a>
    <age>42</age>
  </a>
  <b>Bee</b>
</config>
"""
        o = """\
<config>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
  <b>Ahh</b>
  <b>Ahh</b>
  <b>Bee</b>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_text(self):
        l = """\
<config>
  <b>Ahh</b>
</config>
"""
        r = """\
<config>
  <b key="*">Bee</b>
</config>
"""
        with self.assertRaises(MergeError):
            xml = self.merge_xml(l, r)

   def test_key_non_existing(self):
        l = """\
<config>
</config>
"""
        r = """\
<config>
  <a key="name">
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
<a><name>Kilroy</name><age>42</age></a></config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_non_existing2(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
  </a>
</config>
"""
        r = """\
<config>
  <a key="name">
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_existing(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
</config>
"""
        r = """\
<config>
  <a key="name">
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_existing2(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
</config>
"""
        r = """\
<config>
  <a key="name">
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)

   def test_key_wildcard(self):
        l = """\
<config>
  <a>
    <name>Foo</name>
  </a>
  <a>
    <name>Kilroy</name>
  </a>
</config>
"""
        r = """\
<config>
  <a key="*">
    <age>42</age>
  </a>
</config>
"""
        o = """\
<config>
  <a>
    <name>Foo</name>
    <age>42</age>
  </a>
  <a>
    <name>Kilroy</name>
    <age>42</age>
  </a>
</config>
"""
        xml = self.merge_xml(l, r)
        self.assertEqual(xml, o)







if __name__ == '__main__':
    unittest.main()

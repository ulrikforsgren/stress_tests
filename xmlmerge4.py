#!/usr/bin/env python3

import re
import sys
from  lxml import etree as ET

"""
Actions:
 - merge (default)
 - add
 - replace
 - delete
"""

# TODO:
# - How to handle multiple nodes with same tag in rnode?
#   action should be "add" in this case?!
#   How should "replace", "merge" work in this case?
#   Multiple elements with no subelements (no key specified):
#    replace"   replace if one element, error if multiple. Add should be used.
#                  "replace" can be used on parent for replacing all elements.
#    "merge"    replace if one element, error if multiple. Add should be used.
#    "add"      add new node
#    "delete"   should delete if matching text?
#   With subelements (key specified):
#    "replace"  replace if "what" matches, keys?
#    "merge"    merge if "what" matches, keys?
#    "add"      add new node
#    "delete"   delete if "what" matches, keys?
# - How to add new element adjecent to existing element(s)

def merge_tree(lnode, rnode):
    for c in rnode:
        action = 'merge'
        if 'action' in c.attrib:
            action = c.attrib.get('action')
            del c.attrib['action']

        lcs = lnode.findall(c.tag)
        if action == 'add':
            lnode.append(c)
        elif not lcs: # Not found in lnode: Just add!
            # Add indentation (NOTE! Any garbage text will be copied as well!)
            last = list(lnode)[-1:][0]
            last.tail += rnode.text 
            # Add element
            lnode.append(c)
        elif len(lcs) == 1: # One node found
            if action == 'merge':
                if len(c):
                    merge_tree(lcs[0], c)
                else:
                    lnode.remove(lcs[0])
                    lnode.append(c)
            elif action == 'replace':
                lnode.remove(lcs[0])
                lnode.append(c)
            elif action == 'delete':
                lnode.remove(lcs[0])
        else:
            raise NotImplemented("Add to multiple nodes not supported.")

def main(files):
    ltree = None
    for filename in files:
        doc = ET.parse(filename)
        if ltree is None:
            ltree = doc
        else:
            assert(ltree.getroot().tag == doc.getroot().tag)
            merge_tree(ltree.getroot(), doc.getroot())

    if ltree is not None:
        print(ET.tostring(ltree).decode('utf-8'))

if __name__ == "__main__":
    main(sys.argv[1:])

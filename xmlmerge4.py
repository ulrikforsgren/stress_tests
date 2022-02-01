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
# - Define actions according to input:
#    * with/without key
#    * with/without subelements
#    * lnode content: empty/one/multiple element(s)
# - Write unit tests.
# - Refactor code: arrange after action instead of 
# - How to add new element adjecent to existing element(s)
#    * Use index + insert
# - Fix missing newlines for comments before root element.
# - Add rules to control where to add e.g. before, after, ...

class MergeError(Exception):
    pass

def fix_indentation(lnode, rnode):
    # add indentation (note! any garbage text will be copied as well!)
    # remove one newline to not add one extra empty line
    # does not work for all indentations...
    list(lnode)[-1:][0].tail += rnode.text.replace('\n', '', 1)

def has_subelements(e):
    return len(e)>0

def no_subelements(e):
    return len(e)==0

def merge_tree(lnode, rnode):
    for c in rnode:
        action = 'merge'
        if 'action' in c.attrib:
            action = c.attrib.get('action')
            del c.attrib['action']
        keyname = key = None 
        if 'key' in c.attrib:
            keyname = c.attrib.get('key')
            if keyname:
                v = c.find(keyname)
                if v is not None:
                    key = v.text.strip()
            del c.attrib['key'], v

        lcs = lnode.findall(c.tag)

        if action == 'add':
            if keyname is not None:
                raise MergeError('Specifying key with action add '
                                     'is not supported.')
            if not lcs:
                lnode.append(c)
            else:
                lc = lcs.pop() # Last element
                lnode.insert(lnode.index(lc)+1, c)

        elif not lcs: # ========= No elements in ltress ==========

            if action in ['add', 'merge', 'replace']:
                fix_indentation(lnode, rnode)
                lnode.append(c)
            else: # delete
                pass

        elif len(lcs) == 1: #  ========== One subelement ==========

            if action == 'merge':
                if has_subelements(c):
                    merge_tree(lcs[0], c)
                else:
                    lnode.replace(lcs[0], c)

            elif action == 'replace':
                fix_indentation(lnode, rnode)
                lnode.replace(lcs[0], c)

            elif action == 'delete':
                lnode.remove(lcs[0])

        else:          # ========== Multiple subelements ==========

            if action == 'merge':
                if no_subelements(c):
                    raise MergeError('Action merge has no meaning when '
                                         'there are multiple text only elements.')
                else:
                    for lc in lcs:
                        k = lc.find(keyname)
                        if k is not None and k.text.strip() == key:
                            merge_tree(lc, c)

            elif action == 'replace':
                if no_subelements(c):
                    raise MergeError('Action replace has no meaning when '
                                         'there are multiple text only elements.')
                else:
                    if keyname is None:
                        raise MergeError('No key specified for action replace.')
                    for lc in lcs:
                        k = lc.find(keyname)
                        if k is not None and k.text.strip() == key:
                            lnode.replace(lc, c)

            elif action == 'delete':
                # TODO: a defined key should be precedence?!
                if no_subelements(c):
                    for lc in lcs:
                        if c.text.strip() == lc.text.strip():
                            lnode.remove(lc)
                else:
                    if keyname is None:
                        raise MergeError('No key specified for action delete.')
                    for lc in lcs:
                        k = lc.find(keyname)
                        if k is not None and k.text.strip() == key:
                            lnode.remove(lc)

def main(files):
    ltree = None
    try:
        for filename in files:
            doc = ET.parse(filename)
            if ltree is None:
                ltree = doc
            else:
                # Verify that the root tags are the same
                assert(ltree.getroot().tag == doc.getroot().tag)
                # Merge the trees
                merge_tree(ltree.getroot(), doc.getroot())

        if ltree is not None:
            print(ET.tostring(ltree).decode('utf-8'))
    except MergeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])

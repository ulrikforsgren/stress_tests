#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

from copy import deepcopy
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
# - Refactor code: Look over structure and simplify if possible.
# - Add rules to control where to add e.g. before, after, ...
# - Preserve empty lines and adjust fix indentation...
# - Fix missing newlines for comments before root element.

class MergeError(Exception):
    pass

def fix_indentation(lnode, rnode):
    # add indentation (note! any garbage text will be copied as well!)
    # remove one newline to not add one extra empty line
    # does not work for all indentations...
#    list(lnode)[-1:][0].tail += rnode.text.replace('\n', '', 1)
    pass

def has_subelements(e):
    return len(e)>0

def no_subelements(e):
    return len(e)==0

def cleanup_attributes(node):
    for c in node:
        if 'action' in c.attrib:
            del c.attrib['action']
        if 'key' in c.attrib:
            del c.attrib['key']
        if has_subelements(c):
            cleanup_attributes(c)

def merge_tree(lnode, rnode):
    for c in rnode:
        action = 'merge' # default
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
            if no_subelements(c):
                if action == 'add':
                    raise MergeError('Attribute key can not be used with '
                                     'action add.')
                else:
                    raise MergeError('Attribute key can not be used with '
                                     'text only elements.')

        lcs = lnode.findall(c.tag)

        if action == 'add':
            if keyname is not None:
                raise MergeError('Attribute key can not be used with action '
                                 'add')
            if not lcs:
                lnode.append(c)
            else:
                lc = lcs.pop() # Last element
                lnode.insert(lnode.index(lc)+1, c)

        elif not lcs: # ========= No elements in ltress ==========

            if action == 'merge':
                fix_indentation(lnode, rnode)
                lnode.append(deepcopy(c))
            elif action == 'replace':
                if no_subelements(c):
                    raise MergeError('Action replace can not be used '
                                     'with text only elements.')
                fix_indentation(lnode, rnode)
                lnode.append(deepcopy(c))
            elif action == 'merge':
                fix_indentation(lnode, rnode)
                lnode.append(deepcopy(c))
            else: # delete
                pass

        else:          # ========== one or more elements ==========

            if action == 'merge':
                if no_subelements(c):
                    pos = lnode.index(lcs[0])
                    for lc in lcs:
                        lnode.remove(lc)
                    lnode.insert(pos, deepcopy(c))
                    del pos
                else:
                    if keyname is not None:
                        found = False
                        for lc in lcs:
                            if keyname == '*':
                                merge_tree(lc, deepcopy(c))
                                found = True
                            else:
                                k = lc.find(keyname)
                                if k is not None and k.text.strip() == key:
                                    found = True
                                    merge_tree(lc, deepcopy(c))
                        if not found:
                            lnode.insert(lnode.index(lc)+1, deepcopy(c))
                            del found
                    else:
                        for lc in lcs:
                            merge_tree(lc, deepcopy(c))

            elif action == 'replace':
                if no_subelements(c):
                    raise MergeError('Action replace can not be used '
                                     'with text only elements.')
                else:
                    if keyname is not None:
                        found = False
                        for lc in lcs:
                            if keyname == '*':
                                lnode.replace(lc, deepcopy(c))
                                found = True
                            else:
                                k = lc.find(keyname)
                                if k is not None and k.text.strip() == key:
                                    found = True
                                    lnode.replace(lc, deepcopy(c))
                        if not found:
                            lnode.insert(lnode.index(lc)+1, deepcopy(c))
                            del found
                    else:
                        for lc in lcs:
                            merge_tree(lc, deepcopy(c))

            elif action == 'delete':
                if no_subelements(c):
                    for lc in lcs:
                        if c.text is None or c.text.strip() == lc.text.strip():
                            lnode.remove(lc)
                else:
                    if keyname is None:
                        raise MergeError('No key specified for action delete.')
                    for lc in lcs:
                        if keyname == '*':
                            lnode.remove(lc)
                        else:
                            k = lc.find(keyname)
                            if k is not None and k.text.strip() == key:
                                lnode.remove(lc)

def main(files, unit_test=False):
    ltree = None
    try:
        parser = ET.XMLParser(remove_blank_text=True) if unit_test else None
        for filename in files:
            doc = ET.parse(filename, parser)
            if ltree is None:
                ltree = doc
            else:
                # Verify that the root tags are the same
                assert(ltree.getroot().tag == doc.getroot().tag)
                # Merge the trees
                merge_tree(ltree.getroot(), doc.getroot())

        if ltree is not None:
            cleanup_attributes(ltree.getroot())
            return 0, ET.tostring(ltree, pretty_print=unit_test).decode('utf-8')
    except MergeError as e:
        return 1, f"ERROR: {e}"


if __name__ == "__main__":
    status, xml = main(sys.argv[1:], True)
    print(xml)
    sys.exit(status)

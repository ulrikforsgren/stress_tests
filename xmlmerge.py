#!/usr/bin/env python3
import sys
from xml.etree import ElementTree

def main(files):
    first = None
    for filename in files:
        data = ElementTree.parse(filename).getroot()
        if first is None:
            first = data
        else:
            first.extend(data)
    if first is not None:
        print(ElementTree.tostring(first).decode('utf-8'))

if __name__ == "__main__":
    main(sys.argv[1:])

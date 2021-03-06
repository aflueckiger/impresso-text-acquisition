"""Utility functions to parse Alto XML files."""

import bs4
from bs4.element import Tag
from typing import List, Dict


def distill_coordinates(element: Tag) -> List[int]:
    """Extract image coordinates from any XML tag.

    .. note ::
        This function assumes the following attributes to be present in the
        input XML element: ``HPOS``, ``VPOS``. ``WIDTH``, ``HEIGHT``.

    :param Tag element: Input XML tag.
    :return: An ordered list of coordinates (``x``, ``y``, ``width``,
        ``height``).
    :rtype: List[int]

    """
    hpos = int(element.get('HPOS'))
    vpos = int(element.get('VPOS'))
    width = int(element.get('WIDTH'))
    height = int(element.get('HEIGHT'))

    # NB: these coordinates need to be converted
    return [hpos, vpos, width, height]


def parse_textline(element: Tag) -> dict:
    line = {}
    line['c'] = distill_coordinates(element)
    tokens = []

    for child in element.children:

        if isinstance(child, bs4.element.NavigableString):
            continue

        if child.name == 'String':
            token = {
                    'c': distill_coordinates(child),
                    'tx': child.get('CONTENT')
                    }

            if child.get('SUBS_TYPE') == "HypPart1":
                # token['tx'] += u"\u00AD"
                token['tx'] += "-"
                token['hy'] = True
            elif child.get('SUBS_TYPE') == "HypPart2":
                token['nf'] = child.get('SUBS_CONTENT')

            tokens.append(token)

    line['t'] = tokens
    return line


def parse_printspace(element: Tag, mappings: Dict[str, str]) -> List[dict]:
    """Parse the ``<PrintSpace>`` element of an ALTO XML document.

    :param Tag element: Input XML element (``<PrintSpace>``).
    :param Dict[str,str] mappings: Description of parameter `mappings`.
    :return: Description of returned object.
    :rtype: List[dict]

    """

    regions = []

    for block in element.children:

        if isinstance(block, bs4.element.NavigableString):
            continue

        block_id = block.get('ID')
        if block_id in mappings:
            part_of_contentitem = mappings[block_id]
        else:
            part_of_contentitem = None

        coordinates = distill_coordinates(block)

        lines = [
                parse_textline(line_element)
                for line_element in block.findAll('TextLine')
                ]

        paragraph = {
                "c": coordinates,
                "l": lines
                }

        region = {
                "c": coordinates,
                "p": [paragraph]
                }

        if part_of_contentitem:
            region['pOf'] = part_of_contentitem
        regions.append(region)
    return regions

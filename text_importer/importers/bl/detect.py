import json
import logging
import os
from collections import namedtuple
from datetime import date
from typing import List, Optional

from dask import bag as db
from impresso_commons.path.path_fs import _apply_datefilter

from text_importer.utils import get_access_right

import codecs
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EDITIONS_MAPPINGS = {
        1: 'a',
        2: 'b',
        3: 'c',
        4: 'd',
        5: 'e'
        }

BlIssueDir = namedtuple(
        "IssueDirectory", [
                'journal',
                'date',
                'edition',
                'path',
                'rights'
                ]
        )


def _get_single_subdir(_dir: str) -> Optional[str]:
    """Checks if the given dir only has one directory and returns its basename, returns None otherwise.
    
    :param str _dir: Directory to check
    :return: str The basename of the single directory
    """
    sub_dirs = [x for x in os.listdir(_dir) if os.path.isdir(os.path.join(_dir, x))]
    
    if len(sub_dirs) == 0:
        logger.warning(f"Could not find issue in BLIP: {_dir}")
        return None
    elif len(sub_dirs) > 1:
        logger.warning(f"Found more than one issue in BLIP: {_dir}")
        return None
    return sub_dirs[0]


def _get_journal_name(issue_path: str, blip_id: str) -> Optional[str]:
    """ Finds the Journal name from within the mets file, since for BL, it is not in the directory structure.
    The BLIP Id is needed to fetch the right section.
    
    :param str issue_path: Path to issue directory
    :param str blip_id: BLIP ID of the issue (usually the top-level directory where it is located)
    :return: str : The name of the journal, or None if not found
    """
    mets_file = [
            os.path.join(issue_path, f)
            for f in os.listdir(issue_path)
            if 'mets.xml' in f.lower()
            ]
    if len(mets_file) == 0:
        logger.critical(f"Could not find METS file in {issue_path}")
        return None
    
    mets_file = mets_file[0]
    
    with codecs.open(mets_file, 'r', "utf-8") as f:
        raw_xml = f.read()
    
    mets_doc = BeautifulSoup(raw_xml, 'xml')
    
    dmd_sec = [x for x in mets_doc.findAll('dmdSec') if x.get('ID') and blip_id in x.get('ID')]
    if len(dmd_sec) != 1:
        logger.critical(f"Could not get journal name for {issue_path}")
        return None
    
    contents = dmd_sec[0].find('title').contents
    if len(contents) != 1:
        logger.critical(f"Could not get journal name for {issue_path}")
        return None
    
    title = contents[0]
    return title


def dir2issue(blip_dir: str) -> Optional[BlIssueDir]:  # TODO: ask about rights and edition
    """
    Given the BLIP directory of an issue, this function returns the corresponding IssueDirectory.
    
    :param str blip_dir: The BLIP directory path
    :return: BlIssueDir The corresponding Issue
    """
    year_str = _get_single_subdir(blip_dir)
    if year_str is None:
        return None
    
    year_dir = os.path.join(blip_dir, year_str)
    mo_day = _get_single_subdir(year_dir)
    if mo_day is None:
        return None
    
    issue_path = os.path.join(year_dir, mo_day)
    month, day = int(mo_day[:2]), int(mo_day[2:])
    journal = _get_journal_name(issue_path, os.path.basename(blip_dir))
    
    return BlIssueDir(journal=journal, date=date(int(year_str), month, day), edition='a', path=issue_path,
                      rights='open_public')


def detect_issues(base_dir: str, access_rights: str) -> List[BlIssueDir]:
    """Detect newspaper issues to import within the filesystem.

    This function expects the directory structure that the BL used to
    organize the dump of Mets/Alto OCR data.

    :param str base_dir: Path to the base directory of newspaper data.
    :param str access_rights: Not used for this imported, but argument is kept for normality
    :return: List of `BlIssueDir` instances, to be imported.
    """
    blips = [os.path.join(base_dir, x) for x in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, x))]
    
    issues = [dir2issue(b) for b in blips]
    issues = [b for b in issues if b is not None]
    return issues


def select_issues(base_dir: str, config: dict, access_rights: str) -> Optional[List[BlIssueDir]]:
    """Detect selectively newspaper issues to import.

    The behavior is very similar to :func:`detect_issues` with the only
    difference that ``config`` specifies some rules to filter the data to
    import. See `this section <../importers.html#configuration-files>`__ for
    further details on how to configure filtering.

    :param str base_dir: Path to the base directory of newspaper data.
    :param dict config: Config dictionary for filtering.
    :param str access_rights: Path to ``access_rights.json`` file.
    :return: List of `BlIssueDir` instances, to be imported.
    """
    
    # read filters from json configuration (see config.example.json)
    try:
        filter_dict = config["newspapers"]
        exclude_list = config["exclude_newspapers"]
        year_flag = config["year_only"]
    
    except KeyError:
        logger.critical(f"The key [newspapers|exclude_newspapers|year_only] is missing in the config file.")
        return
    
    issues = detect_issues(base_dir, access_rights)
    issue_bag = db.from_sequence(issues)
    selected_issues = issue_bag \
        .filter(lambda i: (len(filter_dict) == 0 or i.journal in filter_dict.keys()) and i.journal not in exclude_list) \
        .compute()
    
    exclude_flag = False if not exclude_list else True
    filtered_issues = _apply_datefilter(filter_dict, selected_issues,
                                        year_only=year_flag) if not exclude_flag else selected_issues
    logger.info(
            "{} newspaper issues remained after applying filter: {}".format(
                    len(filtered_issues),
                    filtered_issues
                    )
            )
    return filtered_issues

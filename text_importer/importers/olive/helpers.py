import json
import os
import time
from operator import itemgetter
from time import strftime
from impresso_commons.images.olive_boxes import compute_box, get_scale_factor
from impresso_commons.path import IssueDir
from impresso_commons.path.path_fs import canonical_path

from text_importer.helpers import logger
from text_importer.tokenization import insert_whitespace


def get_image_info(issue, data_dir):
    """
    Get the contents of the `image-info.json` file for a given issue.

    :param issue: a newspaper issue
    :type issue: `IssueDir`
    :param data_dir: the path to the directory with the images
    :type data_dir: string
    :return: the content of the `image-info.json` file
    :rtype: dict
    """
    
    issue_dir = os.path.join(
            data_dir,
            issue.journal,
            str(issue.date).replace("-", "/"),
            issue.edition
            )
    
    issue_w_images = IssueDir(
            journal=issue.journal,
            date=issue.date,
            edition=issue.edition,
            path=issue_dir
            )
    
    image_info_name = canonical_path(
            issue_w_images,
            name="image-info",
            extension=".json"
            )
    
    image_info_path = os.path.join(issue_w_images.path, image_info_name)
    
    with open(image_info_path, 'r') as inp_file:
        try:
            json_data = json.load(inp_file)
            return json_data
        except Exception as e:
            logger.error(f"Decoding file {image_info_path} failed with '{e}'")
            raise e


def keep_title(title):
    black_list = [
            "untitled article",
            "untitled ad",
            "untitled picture"
            ]
    if title.lower() in black_list:
        return False
    else:
        return True


def convert_box(coords, scale_factor):
    box = " ".join([str(coord) for coord in coords])
    converted_box = compute_box(scale_factor, box)
    new_box = [int(c) for c in converted_box.split()]
    logger.debug(f'Converted box coordinates: {box} => {converted_box}')
    return new_box


def convert_page_coordinates(page, page_xml, page_image_name, zip_archive, box_strategy, issue):
    """
    Logic:
        - get scale factor (passing strategy)
        - for each element with coordinates recompute box

    Returns the same page, with converted boxes.
    """
    start_t = time.clock()
    scale_factor = get_scale_factor(
            issue.path,
            zip_archive,
            page_xml,
            box_strategy,
            page_image_name
            )
    for region in page['r']:
        region['c'] = convert_box(region['c'], scale_factor)
        for paragraph in region['p']:
            for line in paragraph['l']:
                line['c'] = convert_box(line['c'], scale_factor)
                for token in line['t']:
                    token['c'] = convert_box(token['c'], scale_factor)
    end_t = time.clock()
    t = end_t - start_t
    logger.info(
            f'Converted coordinates {page_image_name} in {issue.path} (took {t}s)'
            )
    return page


def convert_image_coordinates(image, page_xml, page_image_name, zip_archive, box_strategy, issue):
    """
    Logic:
        - get scale factor (passing strategy)
        - for each element with coordinates recompute box

    Returns the same page, with converted boxes.
    """
    try:
        scale_factor = get_scale_factor(
                issue.path,
                zip_archive,
                page_xml,
                box_strategy,
                page_image_name
                )
        image.c = convert_box(image.c, scale_factor)
        image.cc = True
    except Exception as e:
        image.cc = False
        # pass
    return image


def merge_pseudo_tokens(line):
    """Remove pseudo tokens from a line.

    :param line: a line of OCR in JSON format
    :type line: dict (keys: coords, tokens)
    :rtype: dict (keys: coords, tokens)
    """
    original_line = " ".join([t["tx"] for t in line["t"]])
    qids = set([
            token["qid"]
            for token in line["t"]
            if "qid" in token
            ])
    
    inline_qids = []
    
    for qid in qids:
        tokens = [
                (i, token)
                for i, token in enumerate(line["t"])
                if "qid" in token and token["qid"] == qid
                ]
        if len(tokens) > 1:
            inline_qids.append(qid)
    
    if len(inline_qids) == 0:
        return line
    
    for qid in inline_qids:
        # identify tokens to merge
        tokens = [
                (i, token)
                for i, token in enumerate(line["t"])
                if "qid" in token and token["qid"] == qid
                ]
        
        # remove tokens to merge from the line
        tokens_to_merge = [
                line["t"].pop(
                        line["t"].index(token)
                        )
                for i, token in tokens
                ]
        
        if len(tokens_to_merge) >= 2:
            insertion_point = tokens[0][0]
            merged_token = merge_tokens(tokens_to_merge, original_line)
            line["t"].insert(insertion_point, merged_token)
    
    return line


def merge_tokens(tokens, line):
    merged_token = {
            "tx": "".join(
                    [
                            token["tx"]
                            for token in tokens
                            ]
                    ),
            "c": tokens[0]["c"][:2] + tokens[-1]["c"][2:],
            "s": tokens[0]["s"]
            }
    logger.debug(
            "(In-line pseudo tokens) Merged {} => {} in line \"{}\"".format(
                    "".join([t["tx"] for t in tokens]),
                    merged_token["tx"],
                    line
                    )
            )
    return merged_token


def normalize_hyphenation(line):
    """Normalize end-of-line hyphenated words.

    :param line: a line of OCR in JSON format
    :type line: dict (keys: coords, tokens)
    :rtype: dict (keys: coords, tokens)
    """
    for i, token in enumerate(line["t"]):
        if i == (len(line["t"]) - 1):
            if token["tx"][-1] == "-":
                token["hy"] = True
            if token["tx"] == "-" and "nf" in token:
                prev_token = line["t"][i - 1]
                line["t"] = line["t"][:-2]
                merged_token = {
                        "tx": "".join([prev_token["tx"], token["tx"]]),
                        "c": prev_token["c"][:2] + token["c"][2:],
                        "s": token["s"],
                        "hy": token["hy"]
                        }
                logger.debug(
                        "Merged {} and {} => {}".format(
                                prev_token,
                                token,
                                merged_token
                                )
                        )
                line["t"].append(merged_token)
    return line


def normalize_line(line, lang):
    """Apply normalization to a line of OCR.

    :param line: a line of OCR text
    :type line: dict (keys: coords, tokens)
    :rtype: dict (keys: coords, tokens)
    """
    mw_tokens = [
            token
            for token in line["t"]
            if "qid" in token
            ]
    # apply normalization only to those lines that contain at least one
    # multi-word token (denoted by presence of `qid` field)
    if len(mw_tokens) > 0:
        line = merge_pseudo_tokens(line)
        line = normalize_hyphenation(line)
    
    for i, token in enumerate(line["t"]):
        if "qid" not in token and "nf" in token:
            del token["nf"]
        
        if "qid" in token:
            del token["qid"]
        
        if i == 0 and i != len(line["t"]) - 1:
            insert_ws = insert_whitespace(
                    token["tx"],
                    line["t"][i + 1]["tx"],
                    None,
                    lang
                    )
        
        elif i == 0 and i == len(line["t"]) - 1:
            insert_ws = insert_whitespace(
                    token["tx"],
                    None,
                    None,
                    lang
                    )
        
        elif i == len(line["t"]) - 1:
            insert_ws = insert_whitespace(
                    token["tx"],
                    None,
                    line["t"][i - 1]["tx"],
                    lang
                    )
        
        else:
            insert_ws = insert_whitespace(
                    token["tx"],
                    line["t"][i + 1]["tx"],
                    line["t"][i - 1]["tx"],
                    lang
                    )
        if not insert_ws:
            token["gn"] = True
    
    return line


def recompose_ToC(toc_data, articles, images):
    """TODO."""
    # concate content items from all pages into a single flat list
    content_items = [
            toc_data[pn][elid]
            for pn in toc_data.keys() for elid in toc_data[pn].keys()
            ]
    
    # filter out those items that are part of a multipart article
    contents = []
    sorted_content_items = sorted(content_items, key=itemgetter('seq'))
    for item in sorted_content_items:
        
        item['m'] = {}
        item["l"] = {}
        
        if (item["type"] == "Article" or item["type"] == "Ad"):
            
            # find the corresponding item in `articles`
            # by using `legacy_id` as the search key
            # if not found (raises exception) means that it's one of the
            # multipart articles, and it's ok to skip it
            legacy_id = item['legacy_id']
            article = None
            for ar in articles:
                if isinstance(ar["legacy"]["id"], list):
                    if ar["legacy"]["id"][0] == legacy_id:
                        article = ar
                else:
                    if ar["legacy"]["id"] == legacy_id:
                        article = ar
            
            try:
                assert article is not None
            except Exception:
                continue
            
            item['m']["id"] = item["id"]
            item['m']['pp'] = article["meta"]["page_no"]
            item['m']['l'] = article["meta"]["language"]
            item['m']['tp'] = article["meta"]["type"]["raw"].lower()
            
            if keep_title(article["meta"]["title"]):
                item['m']['t'] = article["meta"]["title"]
            
            item["l"]["id"] = article["legacy"]["id"]
            item["l"]["source"] = article["legacy"]["source"]
        
        elif (item["type"] == "Picture"):
            
            # find in which page the image is
            page_no = [
                    page_no
                    for page_no in toc_data
                    if item['legacy_id'] in toc_data[page_no]
                    ]
            
            # get the new canonical id via the legacy id
            item['m']['id'] = item['id']
            item['m']['tp'] = item['type'].lower()
            item['m']['pp'] = page_no
            
            try:
                image = [
                        image
                        for image in images
                        if image['id'] == item['legacy_id']
                        ][0]
            except IndexError:
                # if the image XML was faulty (e.g. because of missing
                # coords, it won't find a corresping image item
                logger.info(f"Image {item['legacy_id']} will be skipped")
                continue
            
            if keep_title(image["name"]):
                item['m']['t'] = image["name"]
            
            item['l']['id'] = item['legacy_id']
            item['l']['res'] = image['resolution']
            item['l']['path'] = image['filepath']
            
            item['c'] = image['coords']
            toc_item = toc_data[page_no[0]][item['legacy_id']]
            
            if "embedded_into" in item:
                cont_article_id = toc_item['embedded_into']
                try:
                    containing_article = toc_data[page_no[0]][cont_article_id]
                    
                    # content item entries exists in different shapes within
                    # the `toc_data` dict, depending on whether they have
                    # already been processed in this `for` loop or not
                    if (
                            "m" in containing_article and
                            len(containing_article['m'].keys()) > 0
                    ):
                        item['pOf'] = containing_article['m']['id']
                    else:
                        item['pOf'] = containing_article['id']
                except Exception as e:
                    logger.error(
                            f"Containing article for {item['m']['id']} not found (error = {e})"
                            )
        
        # delete redundant fields
        if "embedded_into" in item:
            del item['embedded_into']
        del item['seq']
        del item['legacy_id']
        del item['type']
        del item['id']
        
        contents.append(item)
    return contents


def recompose_page(page_number, info_from_toc, page_elements, clusters):
    """Create a page document starting from a list of page documents.

    :param page_number: page number
    :type page_number: int
    :param info_from_toc: a dictionary with page element IDs (articles, ads.)
        as keys, and dictionaries as values
    :type info_from_toc:
    :param page_elements: articles or advertisements
    :type page_elements: dict
    :param clusters: an inverted index of legacy ids; if an id is part of
        multipart article, the id is found not as a key but in one of the
        values.
    :type clusters: dict of lists

    It's here that `n` attributes are assigned to each region/para/line/token.
    """
    
    page = {
            "r": [],
            "cdt": strftime("%Y-%m-%d %H:%M:%S")
            }
    ordered_elements = sorted(
            list(info_from_toc[page_number].values()), key=itemgetter('seq')
            )
    
    id_mappings = {
            legacy_id: info_from_toc[page][legacy_id]['id']
            for page in info_from_toc
            for legacy_id in info_from_toc[page]
            }
    
    # put together the regions while keeping the order in the page
    for el in ordered_elements:
        
        # keep only IDS of content items that are Ads or Articles
        # but escluding various other files in the archive
        if ("Ar" not in el["legacy_id"] and "Ad" not in el["legacy_id"]):
            continue
        
        # this is to manage the situation of a multi-part article
        part_of = None
        if el['legacy_id'] in clusters:
            part_of = el['legacy_id']
        else:
            for key in clusters:
                if el['legacy_id'] in clusters[key]:
                    part_of = key
                    break
        
        if el["legacy_id"] in page_elements:
            element = page_elements[el["legacy_id"]]
        else:
            logger.error(f"{el['id']}: {el['legacy_id']} not found in page {page_number}")
            continue
        mapped_id = id_mappings[part_of] if part_of in id_mappings else None
        
        for i, region in enumerate(element["r"]):
            region["pOf"] = mapped_id
        
        page["r"] += element["r"]
    
    return page


def normalize_language(language):
    mappings = {
            "french": "fr",
            "english": "en",
            "german": "de"
            }
    return mappings[language.lower()]

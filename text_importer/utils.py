import json
import logging
import os

import pkg_resources
import python_jsonschema_objects as pjs


def init_logger(logger, log_level, log_file):
    # Initialise the logger
    logger.setLevel(log_level)
    
    if log_file is not None:
        handler = logging.FileHandler(filename=log_file, mode='w')
    else:
        handler = logging.StreamHandler()
    
    formatter = logging.Formatter(
            '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
            )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    logger.info("Logger successfully initialised")


def get_page_schema(schema_folder: str = 'impresso-schemas/json/newspaper/page.schema.json'):
    """Generate a list of python classes starting from a JSON schema.

    :param schema_folder: path to the schema folder (default="./schemas/")
    :rtype: `python_jsonschema_objects.util.Namespace`
    """
    schema_path = pkg_resources.resource_filename(
            'text_importer',
            schema_folder
            )
    with open(os.path.join(schema_path), 'r') as f:
        json_schema = json.load(f)
    builder = pjs.ObjectBuilder(json_schema)
    ns = builder.build_classes().NewspaperPage
    return ns


def get_issue_schema(schema_folder: str = 'impresso-schemas/json/newspaper/issue.schema.json'):
    """Generate a list of python classes starting from a JSON schema.

    :param schema_folder: path to the schema folder (default="./schemas/")
    :type schema_folder: string
    :rtype: `python_jsonschema_objects.util.Namespace`
    """
    schema_path = pkg_resources.resource_filename(
            'text_importer',
            schema_folder
            )
    with open(os.path.join(schema_path), 'r') as f:
        json_schema = json.load(f)
    builder = pjs.ObjectBuilder(json_schema)
    ns = builder.build_classes().NewspaperIssue
    return ns

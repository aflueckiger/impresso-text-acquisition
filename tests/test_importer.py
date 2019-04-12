import pkg_resources
from impresso_commons.path.path_fs import detect_issues

from text_importer.importer import import_issues
from text_importer.importers.lux.core import import_issues as lux_import_issues
from text_importer.importers.lux.detect import \
    detect_issues as lux_detect_issues, select_issues as lux_select_issues


from dask.distributed import Client
import logging

logger = logging.getLogger(__name__)

client = Client(processes=False, n_workers=8, threads_per_worker=2)
logger.info(client)


def test_olive_import_issues():
    inp_dir = pkg_resources.resource_filename(
        'text_importer',
        'data/sample_data/Olive/'
    )
    issues = detect_issues(inp_dir)
    assert issues is not None
    assert len(issues) > 0

    result = import_issues(
        issues,
        "/Volumes/cdh_dhlab_2_arch/project_impresso/images/",
        None,
        pkg_resources.resource_filename('text_importer', 'data/out/'),
        pkg_resources.resource_filename('text_importer', 'data/temp/'),
        "olive",
        True  # whether to parallelize or not
    )
    print(result)


def test_lux_importer():
    inp_dir = pkg_resources.resource_filename(
        'text_importer',
        'data/sample_data/Luxembourg/'
    )
    out_dir = pkg_resources.resource_filename('text_importer', 'data/out/')
    output_bucket = None

    issues = lux_detect_issues(inp_dir)
    assert issues is not None
    result = lux_import_issues(issues, out_dir, s3_bucket=output_bucket)
    assert result is not None


def test_lux_select():
    """Tests selective ingestion of BNL data.

    What to ingest is specified in a JSON configuration file.

    ..todo::

        - add support filtering/selection based on dates and date-ranges;
        - add support for exclusion of newspapers
    """
    cfg_file = pkg_resources.resource_filename(
        'text_importer',
        'config/import_BNL.json'
    )

    inp_dir = pkg_resources.resource_filename(
        'text_importer',
        'data/sample_data/Luxembourg/'
    )

    issues = lux_select_issues(cfg_file, inp_dir)
    assert issues

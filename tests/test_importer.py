import pkg_resources
from dask.distributed import Client
from impresso_commons.path.path_fs import detect_issues
from text_importer.importer import import_issues


def test_olive_import_issues():
    inp_dir = pkg_resources.resource_filename(
        'text_importer',
        'data/sample_data/'
    )
    issues = detect_issues(inp_dir)
    assert issues is not None
    assert len(issues) > 0

    client = Client(processes=False, n_workers=8, threads_per_worker=1)
    print(client)

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

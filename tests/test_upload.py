import pkg_resources

from impresso_commons.path.path_fs import (KNOWN_JOURNALS,
                                           detect_canonical_issues)
from impresso_commons.utils.s3 import get_bucket
from text_importer.upload import s3_upload_issues


def test_s3_upload_batch():
    """Tests the upload of imported canonical data into S3."""
    inp_dir = pkg_resources.resource_filename(
        'text_importer',
        'data/out/'
    )
    obucket = get_bucket('impresso-public')
    issues = detect_canonical_issues(inp_dir, KNOWN_JOURNALS)
    result = s3_upload_issues(
        issues,
        input_dir=inp_dir,
        output_bucket=obucket,
        overwrite=True
    )
    for issue, upload_success in result:
        assert upload_success is True

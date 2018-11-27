"""
CLI script to upload impresso canonical data to an S3 drive.

Usage:
    impresso-txt-uploader --input-dir=<id> --log-file=<f> --s3-bucket=<b> [--overwrite --scheduler=<sch>]

Options:
    --input-dir=<id>    Base directory containing one sub-directory for each journal
    --s3-bucket=<b>     If provided, writes output to an S3 drive, in the specified bucket
    --log-file=<f>      Log file; when missing print log to stdout
    --overwrite         Overwrite files on S3 if already present
    --scheduler=<sch>  Tell dask to use an existing scheduler (otherwise it'll create one)
"""  # noqa: E501

import getpass
import logging
import os
import pickle

import dask.bag as db
from boto.s3.connection import Key
from dask.distributed import Client, progress
from docopt import docopt

import text_importer
from impresso_commons.path.path_fs import (KNOWN_JOURNALS,
                                           detect_canonical_issues)
from impresso_commons.utils.s3 import (get_bucket, get_s3_versions)

logger = logging.getLogger(__name__)


def s3_upload_issue(local_issue, input_dir, output_bucket, overwrite=False):
    """Upload a canonical newspaper issue to an S3 bucket.

    :param local_issue: the issue to upload
    :type local_issue: an instance of `IssueDir`
    :param output_bucket: the target bucket
    :type output_bucket: `boto.s3.connection.Bucket`
    :return: a list of tuples `t` where `t[0]` contains the issue,
        and `t[1]` is a boolean indicating whether the upload was
        successful or not.
    """
    my_dir = local_issue.path
    files = [os.path.join(my_dir, f) for f in os.listdir(my_dir)]
    try:
        for f in files:
            k = Key(output_bucket)
            # remove the input_dir when setting the key's name
            k.key = f.replace(input_dir, "")

            if not overwrite and k.exists() is True:
                logger.info(
                    f'Skipping: {f} file present and overwrite == {overwrite}'
                )
            else:
                # copy the content of the file into the key
                # TODO: add support for metadata
                k.set_metadata('uuser', getpass.getuser())
                k.set_metadata(
                    'script',
                    f'{text_importer.__name__} v{text_importer.__version__}'
                )
                k.set_contents_from_filename(f)
                version_id, last_modified = get_s3_versions(
                    output_bucket.name,
                    k.name
                )[0]
                logger.info(
                    f'Uploaded {f} to s3://{output_bucket.name}/{k.key}'
                )
                logger.info(f'Current version id of {k} = {version_id}')

            k.close()
        return (local_issue, True)
    except Exception as e:
        print(f'Failed uploading {local_issue} with error = {e}')
        return (local_issue, False)


def s3_upload_issues(issues, input_dir, output_bucket, overwrite=False):
    """
    Upload a set of canonical newspaper issues to an S3 bucket.

    :param issues: the list of issues to upload
    :type issues: list of `IssueDir` instances
    :param output_bucket: the target bucket
    :type output_bucket: `boto.s3.connection.Bucket`
    :return: a list of tuples `t` where `t[0]` contains the issue,
        and `t[1]` is a boolean indicating whether the upload was
        successful or not.
    """
    issue_bag = db.from_sequence(issues).map(
        s3_upload_issue,
        input_dir=input_dir,
        output_bucket=output_bucket,
        overwrite=overwrite
    )
    future = issue_bag.persist()
    progress(future)
    return future.compute()


def main():
    args = docopt(__doc__)
    input_dir = args["--input-dir"]
    bucket_name = args["--s3-bucket"]
    log_file = args["--log-file"]
    scheduler = args["--scheduler"]
    overwrite = False if args["--overwrite"] is None else args["--overwrite"]

    # fetch the s3 bucket
    bucket = get_bucket(bucket_name)

    # configure logger
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(filename=log_file, mode='w')
    logger.addHandler(handler)

    # start the dask local cluster
    if scheduler is None:
        client = Client(processes=False, n_workers=2, threads_per_worker=1)
    else:
        client = Client(scheduler)

    logger.info(client)

    # gather issues to upload
    local_issues = detect_canonical_issues(input_dir, KNOWN_JOURNALS)
    print(f"Uploading {len(local_issues)} issues to S3 ({bucket_name})")
    result = s3_upload_issues(
        local_issues,
        input_dir,
        bucket,
        overwrite=overwrite
    )

    # filter files whose upload has failed
    errors = [
        issue
        for issue, success in result
        if not success
    ]

    print(f"\nUploaded {len(result) - len(errors)}/{len(result)} files")

    try:
        assert len(errors) == 0
    except AssertionError:
        logger.error(f"Upload of {len(errors)} failed (see pikcle file)")
        with open('./failed_s3_uploads.pkl', 'wb') as pickle_file:
            pickle.dump(
                [i.path for i in errors],
                pickle_file
            )


if __name__ == '__main__':
    main()

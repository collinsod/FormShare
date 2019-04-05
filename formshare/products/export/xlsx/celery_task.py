from formshare.config.celery_app import celeryApp
from formshare.config.celery_class import CeleryTask
import logging
from subprocess import Popen, PIPE
import os
import gettext
import uuid

log = logging.getLogger(__name__)
gettext.bindtextdomain('formshare', 'formshare:locate')
gettext.textdomain('formshare')
_ = gettext.gettext


class BuildFileError(Exception):
    """
        Exception raised when there is an error while creating the repository.
    """

    def __str__(self):
        return _('Unknown error while creating the XLSX. Sorry about this. '
                 'Please report this error to support_for_ilri@qlands.com')


class SheetNameError(Exception):
    """
        Exception raised when there is an error while creating the repository.
    """

    def __str__(self):
        return _(
                'A worksheet name has been repeated. Excel only allow 30 characters in the worksheet name. '
                'You can fix this by editing the dictionary and change the description of the tables to a maximum of '
                '30 characters.')


@celeryApp.task(base=CeleryTask)
def build_xlsx(settings, odk_dir, form_directory, form_schema, xlsx_file, include_sensitive):

    mysql_user = settings['mysql.user']
    mysql_password = settings['mysql.password']
    mysql_host = settings['mysql.host']
    mysql_port = settings['mysql.port']
    odk_tools_dir = settings['odktools.path']

    paths = ['forms', form_directory, "repository", "create.xml"]
    create_xml = os.path.join(odk_dir, *paths)

    paths = [odk_tools_dir, "utilities", "MySQLToXLSX", "mysqltoxlsx"]
    mysql_to_xlsx = os.path.join(odk_dir, *paths)

    uid = str(uuid.uuid4())

    paths = ['tmp', uid]
    temp_dir = os.path.join(odk_dir, *paths)
    os.makedirs(temp_dir)

    args = [mysql_to_xlsx, "-H " + mysql_host, "-P " + mysql_port, "-u " + mysql_user, "-p " + mysql_password,
            "-s " + form_schema, "-x " + create_xml, "-o " + xlsx_file, "-T " + temp_dir]

    if include_sensitive:
        args.append("-i")

    p = Popen(args, stdout=PIPE, stderr=PIPE)
    stdout, stderr = p.communicate()
    if p.returncode == 0:
        return True, xlsx_file
    else:
        log.error("MySQLToXLSX Error: " + stderr + "-" + stdout + ". Args: " + " ".join(args))
        error = stdout + stderr
        if error.find("Worksheet name is already in use") >= 0:
            raise SheetNameError()
        else:
            raise BuildFileError()
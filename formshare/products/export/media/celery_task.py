from formshare.config.celery_app import celeryApp
from formshare.config.celery_class import CeleryTask
import logging
from formshare.models import get_engine
import os
import gettext
import uuid
import datetime
from decimal import Decimal
import glob
import shutil
from formshare.processes.sse.messaging import send_task_status_to_form

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


class EmptyFileError(Exception):
    """
        Exception raised when there is an error while creating the repository.
    """

    def __str__(self):
        return _('The ODK form does not contain any media')


@celeryApp.task(base=CeleryTask)
def build_media_zip(settings, odk_dir, form_directory, form_schema, zip_file, primary_key):
    task_id = build_media_zip.request.id
    created = False
    engine = get_engine(settings)
    sql = "SELECT count(surveyid) as total FROM " + form_schema + ".maintable"
    submissions = engine.execute(sql).fetchone()
    total = submissions.total

    sql = "SELECT surveyid," + primary_key + " FROM " + form_schema + ".maintable"
    submissions = engine.execute(sql).fetchall()
    uid = str(uuid.uuid4())
    repo_dir = settings['repository.path']
    index = 0
    send_25 = True
    send_50 = True
    send_75 = True
    for submission in submissions:
        index = index + 1
        percentage = (index * 100) / total
        # We report chucks to not overload the messaging system
        if 25 <= percentage <= 50:
            if send_25:
                send_task_status_to_form(settings, task_id, _("25% processed"))
                send_25 = False
        if 50 <= percentage <= 75:
            if send_50:
                send_task_status_to_form(settings, task_id, _("50% processed"))
                send_50 = False
        if 75 <= percentage <= 100:
            if send_75:
                send_task_status_to_form(settings, task_id, _("75% processed"))
                send_75 = False
        key_value = submission[primary_key]

        if isinstance(key_value, datetime.datetime) or \
                isinstance(key_value, datetime.date) or \
                isinstance(key_value, datetime.time):
            key_value = key_value.isoformat().replace("T", " ")
        else:
            if isinstance(key_value, float):
                key_value = str(key_value)
            else:
                if isinstance(key_value, Decimal):
                    key_value = str(key_value)
                else:
                    if isinstance(key_value, datetime.timedelta):
                        key_value = str(key_value)

        key_value = key_value.replace("/", "_")  # Replace invalid character for directory
        tmp_dir = os.path.join(repo_dir, *['tmp', uid, key_value])
        os.makedirs(tmp_dir)
        submission_id = submission.surveyid
        submissions_path = os.path.join(odk_dir, *['forms', form_directory, "submissions", submission_id, '*.*'])
        files = glob.glob(submissions_path)
        if files:
            for file in files:
                shutil.copy(file, tmp_dir)
                created = True
    if created:
        tmp_dir = os.path.join(repo_dir, *['tmp', uid])
        send_task_status_to_form(settings, task_id, _("Creating zip file"))
        shutil.make_archive(zip_file.replace(".zip", ""), 'zip', tmp_dir)
    else:
        raise EmptyFileError(_('The ODK form does not contain any media'))
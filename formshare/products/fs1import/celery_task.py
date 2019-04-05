from formshare.config.celery_app import celeryApp
from formshare.config.celery_class import CeleryTask
import os
import glob
import json
import datetime
from subprocess import Popen, PIPE
import logging
from sqlalchemy import create_engine
from hashlib import md5
from formshare.processes.elasticsearch.repository_index import create_dataset_index, add_dataset
from formshare.processes.elasticsearch.record_index import create_record_index, add_record
from formshare.processes.sse.messaging import send_task_status_to_form
import gettext

gettext.bindtextdomain('formshare', 'formshare:locate')
gettext.textdomain('formshare')
_ = gettext.gettext
log = logging.getLogger(__name__)


def add_submission(engine, project, form, project_of_assistant, assistant, submission, md5sum, status):
    try:
        engine.execute("INSERT INTO submission (project_id,form_id,submission_id,submission_dtime,submission_status,"
                       "enum_project,coll_id,md5sum)"
                       " VALUES ('{}','{}','{}','{}','{}','{}','{}','{}')".
                       format(project, form, submission, datetime.datetime.now().isoformat(), status,
                              project_of_assistant, assistant, md5sum))
    except Exception as e:
        return False, str(e)
    return True, ""


def add_json_log(engine, project, form, submission, json_file, log_file, status, project_of_assistant, assistant):
    try:
        engine.execute("INSERT INTO jsonlog (form_id,project_id,log_id,log_dtime,json_file,log_file,status,"
                       "enum_project,coll_id) values ('{}','{}','{}','{}','{}','{}','{}','{}','{}')".
                       format(form, project, submission, datetime.datetime.now().isoformat(), json_file, log_file,
                              status, project_of_assistant, assistant))
    except Exception as e:
        return False, str(e)
    return True, ""


def store_json_file(engine, submission_id, temp_json_file, json_file, odk_dir, xform_directory, schema, user,
                    project, form, assistant, project_code, geopoint_variable, project_of_assistant, settings,
                    ignore_xform_check=False):
    mysql_user = settings['mysql.user']
    mysql_password = settings['mysql.password']
    mysql_host = settings['mysql.host']
    mysql_port = settings['mysql.port']

    json_to_mysql = os.path.join(settings['odktools.path'], *["JSONToMySQL", "jsontomysql"])

    # Add the controlling fields to the JSON file
    with open(temp_json_file, 'r') as f:
        submission_data = json.load(f)
        if not ignore_xform_check:
            if submission_data["_xform_id_string"] != form:
                log.error("File {} has XFomID = {} but {} was expected".format(temp_json_file,
                                                                               submission_data["_xform_id_string"], form))
                return 1, ""
        else:
            submission_data["_xform_id_string"] = form
        submission_data["_submitted_by"] = assistant
        submission_data["_submitted_date"] = datetime.datetime.now().isoformat()
        submission_data["_user_id"] = user
        submission_data.pop("_version", "")
        submission_data.pop("_id", "")
        submission_data["_submission_id"] = submission_id
        submission_data["_project_code"] = project_code
        if geopoint_variable is not None:
            if geopoint_variable in submission_data.keys():
                submission_data["_geopoint"] = submission_data[geopoint_variable]

    with open(temp_json_file, "w", ) as outfile:
        json_string = json.dumps(submission_data, indent=4, ensure_ascii=False)
        outfile.write(json_string)

    # Second we pass the temporal JSON to jQ to order its elements
    # this will help later on if we want to compare between JSONs
    args = ["jq", "-S", ".", temp_json_file]

    final = open(json_file, "w")
    md5sum = md5(open(json_file, 'rb').read()).hexdigest()
    p = Popen(args, stdout=final, stderr=PIPE)
    stdout, stderr = p.communicate()
    final.close()
    if p.returncode == 0:
        try:
            os.remove(temp_json_file)
        except Exception as e:
            log.error(
                "XMLToJSON error. Temporary file " + temp_json_file + " might not exist! Error: " + str(e))
            return 1, ""

        # Third we try to move the JSON data into the database
        log_file_name = os.path.splitext(json_file)[0] + ".xml"
        uuid_file_name = os.path.splitext(json_file)[0] + ".log"
        log_file = os.path.join(odk_dir, *['forms', xform_directory, 'submissions', 'logs',
                                           os.path.basename(log_file_name)])
        imported_file = os.path.join(odk_dir,
                                     *['forms', xform_directory, 'submissions', 'logs', 'imported.log'])
        uuid_file = os.path.join(odk_dir,
                                 *['forms', xform_directory, 'submissions', 'logs', uuid_file_name])
        maps_directory = os.path.join(odk_dir, *['forms', xform_directory, 'submissions', 'maps'])
        manifest_file = os.path.join(odk_dir, *['forms', xform_directory, 'repository', 'manifest.xml'])
        args = [json_to_mysql, "-H " + mysql_host, "-P " + mysql_port, "-u " + mysql_user, "-p " + mysql_password,
                "-s " + schema, "-o " + log_file, "-j " + json_file, "-i " + imported_file, "-M " + maps_directory,
                "-m " + manifest_file, "-U " + uuid_file, "-O m", "-w"]

        p = Popen(args, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        # An error 2 is an SQL error that goes to the logs
        if p.returncode == 0 or p.returncode == 2:
            added, message = add_submission(engine, project, form, project_of_assistant, assistant, submission_id,
                                            md5sum, p.returncode)

            if not added:
                log.error(message)
                return 1, message

            if p.returncode == 2:
                added, message = add_json_log(engine, project, form, submission_id, json_file,
                                              log_file, 1, project_of_assistant, assistant)
                if not added:
                    log.error(message)
                    return 1, message
            else:
                # Add the JSON to the Elastic Search index but only submissions without error
                create_dataset_index(settings, user, project_code, form)
                add_dataset(settings, user, project_code, form, submission_id, submission_data)
                # Add the inserted records in the record index
                create_record_index(settings)
                with open(uuid_file) as f:
                    lines = f.readlines()
                    for line in lines:
                        parts = line.split(",")
                        add_record(settings, schema, parts[0], parts[1])

            return 0, ""
        else:
            log.error(
                "JSONToMySQL error. Inserting " + json_file + ". Error: " + stdout.decode() + "-" +
                stderr.decode() + ". Command line: " + " ".join(args))
            return 2, ""
    else:
        log.error(
            "jQ error. Converting " + temp_json_file + "  to " + json_file + ". Error: " + "-" +
            stderr + ". Command line: " + " ".join(args))
        return 1, ""


@celeryApp.task(base=CeleryTask)
def import_json_files(user, project, form, odk_dir, form_directory, schema, assistant, path_to_files, project_code,
                      geopoint_variable, project_of_assistant, settings, ignore_xform_check=False):
    task_id = import_json_files.request.id
    engine = create_engine(settings['sqlalchemy.url'])
    list_of_files = path_to_files + '/**/*.json'
    files_to_import = glob.iglob(list_of_files, recursive=True)
    index = 0
    for file_to_import in files_to_import:
        index = index + 1
    total_files = index
    files_to_import = glob.iglob(list_of_files, recursive=True)
    index = 1
    send_25 = True
    send_50 = True
    send_75 = True
    for file_to_import in files_to_import:
        percentage = (index * 100) / total_files
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
        file_name = os.path.basename(file_to_import)
        submission_id = os.path.splitext(os.path.basename(file_to_import))[0]
        json_file = os.path.join(odk_dir, *['forms', form_directory, "submissions", file_name])
        store_json_file(engine, submission_id, file_to_import, json_file, odk_dir, form_directory, schema,
                        user, project, form, assistant, project_code, geopoint_variable, project_of_assistant, settings,
                        ignore_xform_check)
        index = index + 1
    engine.dispose()
import gettext
import glob
import json
import logging
import os
import shutil
import time
import traceback
import uuid
from subprocess import Popen, PIPE, check_call, CalledProcessError

import transaction
from lxml import etree
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers

from formshare.config.celery_app import celeryApp
from formshare.config.celery_class import CeleryTask
from formshare.models import (
    get_engine,
    get_session_factory,
    get_tm_session,
    Odkform,
    map_to_schema,
    initialize_schema,
)
from formshare.processes.elasticsearch.repository_index import delete_dataset_index
from formshare.processes.email.send_async_email import send_async_email
from formshare.processes.sse.messaging import send_task_status_to_form

log = logging.getLogger("formshare")


class MergeDataBaseError(Exception):
    """
        Exception raised when there is an error while creating the repository.
    """


def get_odk_path(settings):
    repository_path = settings["repository.path"]
    return os.path.join(repository_path, *["odk"])


def move_changes(node_b, root_a):
    target_table = None
    for tag in node_b.iter():
        if not len(tag):
            field_name = tag.get("name")
            field_desc = tag.get("desc")
            field_sensitive = tag.get("sensitive")
            field_protection = tag.get("protection")
            target_field = target_table.find(".//field[@name='" + field_name + "']")
            if target_field is not None:
                target_field.set("desc", field_desc)
                if field_sensitive is not None:
                    target_field.set("sensitive", field_sensitive)
                    target_field.set("protection", field_protection)
        else:
            current_table = tag.get("name")
            if current_table is not None:
                table_desc = tag.get("desc")
                target_table = root_a.find(".//table[@name='" + current_table + "']")
                if target_table is not None:
                    target_table.set("desc", table_desc)


def make_database_changes(
    settings,
    cnf_file,
    a_schema,
    b_schema,
    merge_create_file,
    merge_insert_file,
    merge_log_file,
    c_create_xml_file,
    b_create_xml_file,
    b_backup_file,
    a_form_directory,
    task_id,
    _,
):
    error = False
    error_message = ""

    args = [
        "mysql",
        "--defaults-file=" + cnf_file,
        "--execute=CREATE SCHEMA "
        + a_schema
        + " DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_general_ci",
    ]
    try:
        check_call(args)
    except CalledProcessError as e:
        error_message = "Error dropping schema \n"
        error_message = error_message + "Error: \n"
        if e.stderr is not None:
            error_message = error_message + e.stderr.encode() + "\n"
        log.error(error_message)
        error = True

    if not error:
        maria_db = False
        args = ["mariadb_config", "--version"]
        p = Popen(args, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        if p.returncode == 0:
            maria_db = True
            mysql_version = stdout.decode().replace("\n", "")
        else:
            args = ["mysql_config", "--version"]
            p = Popen(args, stdout=PIPE, stderr=PIPE)
            stdout, stderr = p.communicate()
            if p.returncode == 0:
                mysql_version = stdout.decode().replace("\n", "")
            else:
                raise MergeDataBaseError("Cannot determine the version of MySQL")
        parts = mysql_version.split(".")
        major_version = int(parts[0])

        send_task_status_to_form(settings, task_id, _("Creating database backup..."))
        if major_version <= 5 or maria_db:
            args = ["mysqldump", "--defaults-file=" + cnf_file, b_schema]
        else:
            args = [
                "mysqldump",
                "--column-statistics=0 --defaults-file=" + cnf_file,
                b_schema,
            ]
        with open(b_backup_file, "w") as backup_file:
            proc = Popen(args, stdin=PIPE, stderr=PIPE, stdout=backup_file)
            output, error = proc.communicate()
            if proc.returncode != 0:
                error_message = "Error creating database backup \n"
                error_message = error_message + "File: " + b_backup_file + "\n"
                error_message = error_message + "Error: \n"
                if error is not None:
                    error_message = error_message + error.decode() + "\n"
                error_message = error_message + "Output: \n"
                if output is not None:
                    error_message = error_message + output.decode() + "\n"
                log.error(error_message)
                error = True

    if not error:
        send_task_status_to_form(
            settings, task_id, _("Moving backup into new schema...")
        )
        args = ["mysql", "--defaults-file=" + cnf_file, a_schema]
        with open(b_backup_file) as input_file:
            proc = Popen(args, stdin=input_file, stderr=PIPE, stdout=PIPE)
            output, error = proc.communicate()
            if proc.returncode != 0:
                error_message = "Error creating database \n"
                error_message = error_message + "File: " + b_backup_file + "\n"
                error_message = error_message + "Error: \n"
                if error is not None:
                    error_message = error_message + error.decode() + "\n"
                error_message = error_message + "Output: \n"
                if output is not None:
                    error_message = error_message + output.decode() + "\n"
                log.error(error_message)
                error = True

    if not error:
        send_task_status_to_form(
            settings, task_id, _("Applying structure changes in the new schema...")
        )
        args = ["mysql", "--defaults-file=" + cnf_file, a_schema]
        with open(merge_create_file) as input_file:
            proc = Popen(args, stdin=input_file, stderr=PIPE, stdout=PIPE)
            output, error = proc.communicate()
            if proc.returncode != 0:
                error_message = "Error creating database \n"
                error_message = error_message + "File: " + merge_create_file + "\n"
                error_message = error_message + "Error: \n"
                if error is not None:
                    error_message = error_message + error.decode() + "\n"
                error_message = error_message + "Output: \n"
                if output is not None:
                    error_message = error_message + output.decode() + "\n"
                log.error(error_message)
                error = True

    if not error:
        send_task_status_to_form(
            settings, task_id, _("Applying lookup value changes in the new schema...")
        )
        args = ["mysql", "--defaults-file=" + cnf_file, a_schema]
        with open(merge_insert_file) as input_file:
            proc = Popen(args, stdin=input_file, stderr=PIPE, stdout=PIPE)
            output, error = proc.communicate()
            if proc.returncode != 0:
                error_message = "Error creating database \n"
                error_message = error_message + "File: " + merge_insert_file + "\n"
                error_message = error_message + "Error: \n"
                if error is not None:
                    error_message = error_message + error.decode() + "\n"
                error_message = error_message + "Output: \n"
                if output is not None:
                    error_message = error_message + output.decode() + "\n"
                log.error(error_message)
                error = True

    if not error:
        try:
            root = etree.parse(merge_log_file)
            error_list = root.findall(".//error")
            new_table_list = []
            rebuild_table_list = []
            if error_list:
                for an_error in error_list:
                    if an_error.get("code") == "FNF":
                        if an_error.get("table") not in rebuild_table_list:
                            rebuild_table_list.append(an_error.get("table"))
                    if an_error.get("code") == "TNF":
                        new_table_list.append(an_error.get("to"))
            if len(new_table_list) >= 0 or len(rebuild_table_list) >= 0:
                if len(rebuild_table_list) > 0:
                    send_task_status_to_form(
                        settings, task_id, _("Dropping old triggers")
                    )
                    engine = create_engine(settings.get("sqlalchemy.url"))
                    for a_table in rebuild_table_list:
                        if not error:
                            sql = (
                                "SELECT TRIGGER_NAME FROM information_schema.triggers "
                                "WHERE TRIGGER_SCHEMA = '{}' "
                                "AND EVENT_OBJECT_TABLE = '{}' "
                                "AND TRIGGER_NAME LIKE 'audit_%'".format(
                                    a_schema, a_table
                                )
                            )
                            try:
                                res = engine.execute(sql).fetchall()
                                for a_trigger in res:
                                    sql = "DROP TRIGGER {}.{}".format(
                                        a_schema, a_trigger[0]
                                    )
                                    try:
                                        engine.execute(sql)
                                    except Exception as e:
                                        error_message = "Error {} while dropping trigger {} from database {}".format(
                                            str(e), a_trigger[0], a_schema
                                        )
                                        log.error(error_message)
                                        error = True
                                        break
                            except Exception as e:
                                error_message = "Error {} while loading triggers from schema {}, table {}".format(
                                    str(e), a_schema, a_table
                                )
                                log.error(error_message)
                                error = True
                    engine.dispose()
                    if not error:
                        odk_dir = get_odk_path(settings)

                        str_all_tables = ",".join(rebuild_table_list + new_table_list)

                        create_audit_triggers = os.path.join(
                            settings["odktools.path"],
                            *["utilities", "createAuditTriggers", "createaudittriggers"]
                        )
                        audit_path = os.path.join(
                            odk_dir, *["forms", a_form_directory, "merging_files"]
                        )
                        mysql_host = settings["mysql.host"]
                        mysql_port = settings["mysql.port"]
                        mysql_user = settings["mysql.user"]
                        mysql_password = settings["mysql.password"]
                        args = [
                            create_audit_triggers,
                            "-H " + mysql_host,
                            "-P " + mysql_port,
                            "-u " + mysql_user,
                            "-p " + mysql_password,
                            "-s " + a_schema,
                            "-o " + audit_path,
                            "-t " + str_all_tables,
                        ]
                        p = Popen(args, stdout=PIPE, stderr=PIPE)
                        stdout, stderr = p.communicate()
                        if p.returncode == 0:
                            audit_file = os.path.join(
                                odk_dir,
                                *[
                                    "forms",
                                    a_form_directory,
                                    "merging_files",
                                    "mysql_create_audit.sql",
                                ]
                            )
                            send_task_status_to_form(
                                settings, task_id, _("Creating new triggers")
                            )
                            args = ["mysql", "--defaults-file=" + cnf_file, a_schema]
                            with open(audit_file) as input_file:
                                proc = Popen(
                                    args, stdin=input_file, stderr=PIPE, stdout=PIPE
                                )
                                output, error = proc.communicate()
                                if proc.returncode != 0:
                                    error_message = "Error loading audit triggers \n"
                                    error_message = (
                                        error_message + "File: " + audit_file + "\n"
                                    )
                                    error_message = error_message + "Error: \n"
                                    if error is not None:
                                        error_message = (
                                            error_message + error.decode() + "\n"
                                        )
                                    error_message = error_message + "Output: \n"
                                    if output is not None:
                                        error_message = (
                                            error_message + output.decode() + "\n"
                                        )
                                    log.error(error_message)
                                    error = True
                        else:
                            error = True
                            error_message = (
                                "Error while creating audit triggers: "
                                + stdout.decode()
                                + " - "
                                + stderr.decode()
                                + " - "
                                + " ".join(args)
                            )
                            log.error(error_message)
        except Exception as e:
            error_message = "Error processing merge log file: {}. Error: {}".format(
                merge_log_file, str(e)
            )
            log.error(error_message)
            error = True

    if not error:
        try:
            # Move all metadata changes made to b into c
            tree_b = etree.parse(b_create_xml_file)
            tree_c = etree.parse(c_create_xml_file)
            root_b = tree_b.getroot()
            root_c = tree_c.getroot()
            move_changes(root_b, root_c)
            tree_c.write(
                c_create_xml_file,
                pretty_print=True,
                xml_declaration=True,
                encoding="utf-8",
            )
        except Exception as e:
            error_message = "Error while moving metadata changes from {} to {}. Error: {}".format(
                b_create_xml_file, c_create_xml_file, str(e)
            )
            log.error(error_message)
            error = True
    if error:
        raise MergeDataBaseError(error_message)


def update_form(db_session, project, form, form_data):
    mapped_data = map_to_schema(Odkform, form_data)
    try:
        db_session.query(Odkform).filter(Odkform.project_id == project).filter(
            Odkform.form_id == form
        ).update(mapped_data)
        return True, ""
    except Exception as e:
        log.error(
            "Error {} while updating form {} in project {}".format(
                str(e), project, form
            )
        )
        raise MergeDataBaseError(str(e))


@celeryApp.task(base=CeleryTask)
def merge_into_repository(
    settings,
    user,
    project_id,
    project_code,
    a_form_id,
    a_form_directory,
    b_form_directory,
    b_schema_name,
    odk_merge_string,
    b_hex_color,
    locale,
):
    parts = __file__.split("/products/")
    this_file_path = parts[0] + "/locale"
    es = gettext.translation("formshare", localedir=this_file_path, languages=[locale])
    es.install()
    _ = es.gettext

    odk_dir = get_odk_path(settings)

    merge_create_file = os.path.join(
        odk_dir, *["forms", a_form_directory, "merging_files", "create.sql"]
    )

    merge_insert_file = os.path.join(
        odk_dir, *["forms", a_form_directory, "merging_files", "insert.sql"]
    )

    merge_log_file = os.path.join(
        odk_dir, *["forms", a_form_directory, "merging_files", "output.xml"]
    )

    c_create_xml_file = os.path.join(
        odk_dir, *["forms", a_form_directory, "merging_files", "create.xml"]
    )

    b_create_xml_file = os.path.join(
        odk_dir, *["forms", b_form_directory, "repository", "create.xml"]
    )

    b_backup_directory = os.path.join(
        odk_dir, *["forms", b_form_directory, "repository_bks"]
    )
    if not os.path.exists(b_backup_directory):
        os.makedirs(b_backup_directory)

    b_backup_file = os.path.join(
        odk_dir, *["forms", b_form_directory, "repository_bks", b_schema_name + ".sql"]
    )

    a_schema_name = "FS_" + str(uuid.uuid4()).replace("-", "_")

    task_id = merge_into_repository.request.id
    cnf_file = settings["mysql.cnf"]

    session_factory = get_session_factory(get_engine(settings))
    critical_part = False
    form_with_changes = []
    with transaction.manager:
        db_session = get_tm_session(session_factory, transaction.manager)
        configure_mappers()
        initialize_schema()

        # Block all forms using the old schema so they cannot accept any changes
        db_session.query(Odkform).filter(Odkform.form_schema == b_schema_name).update(
            {"form_blocked": 1}
        )
        update_form(db_session, project_id, a_form_id, {"form_blocked": 1})
        transaction.commit()
        time.sleep(5)  # Sleep for 5 seconds just to allow any pending updates to finish
        try:
            make_database_changes(
                settings,
                cnf_file,
                a_schema_name,
                b_schema_name,
                merge_create_file,
                merge_insert_file,
                merge_log_file,
                c_create_xml_file,
                b_create_xml_file,
                b_backup_file,
                a_form_directory,
                task_id,
                _,
            )
            # At this stage all changes were made to the new schema and C XML create file. Now we need to update
            # the FormShare forms with the new schema. This is a critical part. If something goes wrong
            # in between the critical parts then all the involved forms are broken and then technical team will need
            # to deal with them. A log indicating the involved forms are posted

            send_task_status_to_form(settings, task_id, "FINALIZING")
            # Sleep for another five seconds because the FINALIZING will disable the cancellation of the task.
            # Just to be sure that the user cannot cancel the task beyond this point.
            time.sleep(10)

            critical_part = True
            # Move all forms using the old schema to the new schema, replace their create file with C and unblock them
            res = (
                db_session.query(Odkform)
                .filter(Odkform.form_schema == b_schema_name)
                .all()
            )
            for a_form in res:
                form_with_changes.append(
                    {
                        "id": a_form.form_id,
                        "project_id": a_form.project_id,
                        "from": a_form.form_schema,
                        "to": a_schema_name,
                    }
                )
                log.error(
                    "Form ID: {} in project: {} will change schema from {} to {}".format(
                        a_form.form_id,
                        a_form.project_id,
                        a_form.form_schema,
                        a_schema_name,
                    )
                )

            db_session.query(Odkform).filter(
                Odkform.form_schema == b_schema_name
            ).update(
                {
                    "form_blocked": 0,
                    "form_schema": a_schema_name,
                    "form_createxmlfile": c_create_xml_file,
                    "form_hexcolor": b_hex_color,
                }
            )

            form_data = {
                "form_schema": a_schema_name,
                "form_blocked": 0,
                "form_createxmlfile": c_create_xml_file,
                "form_hexcolor": b_hex_color,
            }
            update_form(db_session, project_id, a_form_id, form_data)

            critical_part = False
            # Remove any test submissions if any. In try because nothing happens if they
            # don't get removed... just junk files
            submissions_path = os.path.join(
                odk_dir, *["forms", a_form_directory, "submissions", "*.*"]
            )
            files = glob.glob(submissions_path)
            if files:
                for file in files:
                    try:
                        os.remove(file)
                    except Exception as e:
                        log.error(str(e))
            submissions_path = os.path.join(
                odk_dir, *["forms", a_form_directory, "submissions", "*/"]
            )
            files = glob.glob(submissions_path)
            if files:
                for file in files:
                    if file[-5:] != "logs/" and file[-5:] != "maps/":
                        try:
                            shutil.rmtree(file)
                        except Exception as e:
                            log.error(str(e))
            # Delete the dataset index
            delete_dataset_index(settings, user, project_code, a_form_id)

        except Exception as e:
            if critical_part:
                status = "Critical error with merging"
            else:
                status = "Non Critical error with merging"
            email_from = settings.get("mail.from", None)
            email_to = settings.get("mail.error", None)
            error_dict = {"errors": form_with_changes}
            if critical_part:
                log.error("BEGIN CRITICAL MERGE ERROR")
                log.error(error_dict)
                log.error(odk_merge_string)
                log.error("END CRITICAL MERGE ERROR")
            send_async_email(
                settings,
                email_from,
                email_to,
                status,
                json.dumps(error_dict)
                + "\n\nError: {}\n\nTraceback: {}\n\nMerge string {}".format(
                    str(e), traceback.format_exc(), odk_merge_string
                ),
                None,
                locale,
            )
            log.error("Error while merging the form: {}".format(str(e)))
            db_session.query(Odkform).filter(
                Odkform.form_schema == b_schema_name
            ).update({"form_blocked": 0})
            update_form(db_session, project_id, a_form_id, {"form_blocked": 0})
            transaction.commit()
            raise MergeDataBaseError(str(e))

from .classes import PrivateView, AssistantAPIView
from pyramid.httpexceptions import HTTPNotFound, HTTPFound
from formshare.processes.db import (
    get_form_data,
    get_project_id_from_name,
    get_project_owner,
    get_form_details,
)
from formshare.config.auth import get_user_data
import json
from formshare.processes.submission.api import (
    get_request_data_jqgrid,
    get_fields_from_table,
    delete_submission,
    delete_all_submission,
    update_record_with_id,
)
from pyramid.response import Response
from formshare.processes.elasticsearch.record_index import get_table
from formshare.processes.odk.processes import get_assistant_permissions_on_a_form


class ManageSubmissions(PrivateView):
    def __init__(self, request):
        PrivateView.__init__(self, request)
        self.privateOnly = True
        self.checkCrossPost = False

    def process_view(self):
        user_id = self.request.matchdict["userid"]
        project_code = self.request.matchdict["projcode"]
        form_id = self.request.matchdict["formid"]
        project_id = get_project_id_from_name(self.request, user_id, project_code)
        project_details = {}
        if project_id is not None:
            project_found = False
            for project in self.user_projects:
                if project["project_id"] == project_id:
                    project_found = True
                    project_details = project
            if not project_found:
                raise HTTPNotFound
        else:
            raise HTTPNotFound

        if project_details["access_type"] >= 3:
            raise HTTPNotFound

        form_data = get_form_details(self.request, user_id, project_id, form_id)
        if form_data is not None:
            if form_data["form_schema"] is None:
                raise HTTPNotFound
            if form_data["submissions"] <= 0:
                raise HTTPNotFound

            fields, checked = get_fields_from_table(
                self.request, project_id, form_id, "maintable", []
            )
            return {
                "projectDetails": project_details,
                "formid": form_id,
                "formDetails": form_data,
                "userid": user_id,
                "fields": fields,
            }
        else:
            raise HTTPNotFound


class ReviewAudit(PrivateView):
    def __init__(self, request):
        PrivateView.__init__(self, request)
        self.privateOnly = True
        self.checkCrossPost = False

    def process_view(self):
        user_id = self.request.matchdict["userid"]
        project_code = self.request.matchdict["projcode"]
        form_id = self.request.matchdict["formid"]
        project_id = get_project_id_from_name(self.request, user_id, project_code)
        project_details = {}
        if project_id is not None:
            project_found = False
            for project in self.user_projects:
                if project["project_id"] == project_id:
                    project_found = True
                    project_details = project
            if not project_found:
                raise HTTPNotFound
        else:
            raise HTTPNotFound

        if project_details["access_type"] >= 3:
            raise HTTPNotFound

        form_data = get_form_details(self.request, user_id, project_id, form_id)
        if form_data is not None:
            if form_data["form_schema"] is None:
                raise HTTPNotFound

            fields = [
                {"name": "audit_date", "desc": "Date"},
                {"name": "audit_user", "desc": "User"},
                {"name": "audit_action", "desc": "Action"},
                {"name": "audit_table", "desc": "Table"},
                {"name": "audit_column", "desc": "Column"},
                {"name": "audit_oldvalue", "desc": "Previous value"},
                {"name": "audit_newvalue", "desc": "New value"},
                {"name": "audit_key", "desc": "Row ID"},
            ]

            return {
                "projectDetails": project_details,
                "formid": form_id,
                "formDetails": form_data,
                "userid": user_id,
                "fields": fields,
            }
        else:
            raise HTTPNotFound


class GetFormSubmissions(PrivateView):
    def __init__(self, request):
        PrivateView.__init__(self, request)
        self.privateOnly = True
        self.checkCrossPost = False
        self.returnRawViewResult = True

    def process_view(self):
        user_id = self.request.matchdict["userid"]
        project_code = self.request.matchdict["projcode"]
        form_id = self.request.matchdict["formid"]
        project_id = get_project_id_from_name(self.request, user_id, project_code)
        project_details = {}
        if project_id is not None:
            project_found = False
            for project in self.user_projects:
                if project["project_id"] == project_id:
                    project_found = True
                    project_details = project
            if not project_found:
                raise HTTPNotFound
        else:
            raise HTTPNotFound

        if project_details["access_type"] >= 3:
            raise HTTPNotFound

        form_data = get_form_data(self.request, project_id, form_id)
        if form_data is not None:
            if form_data["form_schema"] is None:
                raise HTTPNotFound
            if self.request.method == "GET":
                raise HTTPNotFound
            request_data = self.get_post_dict()
            call_back = self.request.params.get("callback")

            search_field = request_data.get("searchField", None)
            search_string = request_data.get("searchString", "")
            search_operator = request_data.get("searchOper", None)

            fields, checked = get_fields_from_table(
                self.request, project_id, form_id, "maintable", []
            )
            field_names = []
            for field in fields:
                field_names.append(field["name"])

            if request_data["sidx"] == "":
                table_order = None
            else:
                table_order = request_data["sidx"]

            order_direction = request_data["sord"]
            data = get_request_data_jqgrid(
                self.request,
                project_id,
                form_id,
                "maintable",
                field_names,
                int(request_data["page"]),
                int(request_data["rows"]),
                table_order,
                order_direction,
                search_field,
                search_string,
                search_operator,
            )

            return call_back + "(" + json.dumps(data) + ")"
        else:
            raise HTTPNotFound


class GetFormAudit(PrivateView):
    def __init__(self, request):
        PrivateView.__init__(self, request)
        self.privateOnly = True
        self.checkCrossPost = False
        self.returnRawViewResult = True

    def process_view(self):
        user_id = self.request.matchdict["userid"]
        project_code = self.request.matchdict["projcode"]
        form_id = self.request.matchdict["formid"]
        project_id = get_project_id_from_name(self.request, user_id, project_code)
        project_details = {}
        if project_id is not None:
            project_found = False
            for project in self.user_projects:
                if project["project_id"] == project_id:
                    project_found = True
                    project_details = project
            if not project_found:
                raise HTTPNotFound
        else:
            raise HTTPNotFound

        if project_details["access_type"] >= 3:
            raise HTTPNotFound

        form_data = get_form_data(self.request, project_id, form_id)
        if form_data is not None:
            if form_data["form_schema"] is None:
                raise HTTPNotFound
            if self.request.method == "GET":
                raise HTTPNotFound
            request_data = self.get_post_dict()
            call_back = self.request.params.get("callback")

            search_field = request_data.get("searchField", None)
            search_string = request_data.get("searchString", "")
            search_operator = request_data.get("searchOper", None)

            field_names = [
                "audit_date",
                "audit_user",
                "audit_action",
                "audit_table",
                "audit_column",
                "audit_oldvalue",
                "audit_newvalue",
                "audit_key",
            ]

            table_order_is_none = False
            if request_data["sidx"] == "":
                table_order = "audit_date"
                table_order_is_none = True
            else:
                table_order = request_data["sidx"]

            if not table_order_is_none:
                order_direction = request_data["sord"]
            else:
                order_direction = "DESC"
            data = get_request_data_jqgrid(
                self.request,
                project_id,
                form_id,
                "audit_log",
                field_names,
                int(request_data["page"]),
                int(request_data["rows"]),
                table_order,
                order_direction,
                search_field,
                search_string,
                search_operator,
            )

            return call_back + "(" + json.dumps(data) + ")"
        else:
            raise HTTPNotFound


class DeleteFormSubmission(PrivateView):
    def __init__(self, request):
        PrivateView.__init__(self, request)
        self.privateOnly = True
        self.checkCrossPost = False
        self.returnRawViewResult = True

    def process_view(self):
        user_id = self.request.matchdict["userid"]
        project_code = self.request.matchdict["projcode"]
        form_id = self.request.matchdict["formid"]
        project_id = get_project_id_from_name(self.request, user_id, project_code)
        project_details = {}
        if project_id is not None:
            project_found = False
            for project in self.user_projects:
                if project["project_id"] == project_id:
                    project_found = True
                    project_details = project
            if not project_found:
                raise HTTPNotFound
        else:
            raise HTTPNotFound

        if project_details["access_type"] >= 3:
            raise HTTPNotFound

        form_data = get_form_data(self.request, project_id, form_id)
        if form_data is not None:
            if form_data["form_schema"] is None:
                raise HTTPNotFound
            if form_data["form_blocked"] != 0:
                raise HTTPNotFound
            if self.request.method == "GET":
                raise HTTPNotFound
            request_data = self.get_post_dict()
            if request_data.get("oper", None) == "del":
                if request_data.get("id", "") != "":
                    delete_submission(
                        self.request,
                        user_id,
                        project_id,
                        form_id,
                        request_data.get("id"),
                        project_code,
                    )
            return {}
        else:
            raise HTTPNotFound


class DeleteAllSubmissions(PrivateView):
    def __init__(self, request):
        PrivateView.__init__(self, request)
        self.privateOnly = True
        self.checkCrossPost = False
        self.returnRawViewResult = True

    def process_view(self):
        user_id = self.request.matchdict["userid"]
        project_code = self.request.matchdict["projcode"]
        form_id = self.request.matchdict["formid"]
        project_id = get_project_id_from_name(self.request, user_id, project_code)
        project_details = {}
        if project_id is not None:
            project_found = False
            for project in self.user_projects:
                if project["project_id"] == project_id:
                    project_found = True
                    project_details = project
            if not project_found:
                raise HTTPNotFound
        else:
            raise HTTPNotFound

        if project_details["access_type"] >= 3:
            raise HTTPNotFound

        form_data = get_form_data(self.request, project_id, form_id)
        if form_data is not None:
            if form_data["form_schema"] is None:
                raise HTTPNotFound
            if form_data["form_blocked"] != 0:
                raise HTTPNotFound
            if self.request.method == "GET":
                raise HTTPNotFound
            request_data = self.get_post_dict()
            owner = get_project_owner(self.request, project_id)
            user_data = get_user_data(owner, self.request)
            if request_data.get("owner_email", "") != "":
                if user_data.email == request_data.get("owner_email", ""):
                    deleted, message = delete_all_submission(
                        self.request, user_id, project_id, form_id, project_code
                    )
                    if deleted:
                        return HTTPFound(
                            location=self.request.route_url(
                                "form_details",
                                userid=project_details["owner"],
                                projcode=project_code,
                                formid=form_id,
                            )
                        )
                    else:
                        self.add_error(self._("Unable to delete all submissions"))
                        return HTTPFound(
                            location=self.request.route_url(
                                "manageSubmissions",
                                userid=project_details["owner"],
                                projcode=project_code,
                                formid=form_id,
                            )
                        )
                else:
                    self.add_error(self._("The email is not correct"))
                    return HTTPFound(
                        location=self.request.route_url(
                            "manageSubmissions",
                            userid=project_details["owner"],
                            projcode=project_code,
                            formid=form_id,
                        )
                    )
            else:
                self.add_error(self._("You need to enter your email"))
                return HTTPFound(
                    location=self.request.route_url(
                        "manageSubmissions",
                        userid=project_details["owner"],
                        projcode=project_code,
                        formid=form_id,
                    )
                )

        else:
            raise HTTPNotFound


class UpdateRepositoryView(AssistantAPIView):
    def __init__(self, request):
        AssistantAPIView.__init__(self, request)

    def process_view(self):
        user_id = self.request.matchdict["userid"]
        project_code = self.request.matchdict["projcode"]
        form_id = self.request.matchdict["formid"]

        permissions = get_assistant_permissions_on_a_form(
            self.request, user_id, self.project_id, self.assistant["coll_id"], form_id
        )

        if permissions["enum_canclean"] == 0:
            response = Response(
                content_type="application/json",
                status=401,
                body=json.dumps(
                    {"error": self._("You are not authorized to clean this dataset")}
                ).encode(),
            )
            return response

        if "rowuuid" in self.json.keys():
            try:
                schema, table = get_table(
                    self.request.registry.settings,
                    user_id,
                    project_code,
                    form_id,
                    self.json["rowuuid"],
                )
                if schema is not None:
                    modified, error = update_record_with_id(
                        self.request,
                        self.assistant["coll_id"],
                        schema,
                        table,
                        self.json["rowuuid"],
                        self.json,
                    )
                    if modified:
                        response = Response(
                            content_type="application/json",
                            body=json.dumps({"status": self._("OK")}).encode(),
                        )
                        return response
                    else:
                        response = Response(
                            content_type="application/json",
                            status=400,
                            body=json.dumps({"error": error}).encode(),
                        )
                        return response
                else:
                    response = Response(
                        content_type="application/json",
                        status=404,
                        body=json.dumps(
                            {"error": self._("RowUUID not found")}
                        ).encode(),
                    )
                    return response

            except Exception as e:
                response = Response(
                    content_type="application/json",
                    status=500,
                    body=json.dumps({"error": type(e).__name__}).encode(),
                )
                return response
        else:
            response = Response(
                content_type="application/json",
                status=400,
                body=json.dumps(
                    {"error": self._("The JSON data does not have a rowuuid")}
                ).encode(),
            )
            return response

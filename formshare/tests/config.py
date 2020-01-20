server_config = {
    "pyramid.reload_templates": "true",
    "pyramid.debug_authorization": "false",
    "pyramid.debug_notfound": "false",
    "pyramid.debug_routematch": "false",
    "pyramid.default_locale_name": "en",
    "pyramid.includes": "\npyramid_debugtoolbar",
    "sqlalchemy.url": "mysql+mysqlconnector://root:test@localhost/formshare?charset=utf8",
    "auth.main.secret": "WA&Vr-hfK8NE\\#38G",
    "auth.main.cookie": "formshare_main_auth_tkt",
    "auth.assistant.secret": "WA&Vr-hfK8NE\\#38G",
    "auth.assistant.cookie": "formshare_assistant_auth_tkt",
    "auth.secret": "WA&Vr-hfK8NE\\#38G",
    "aes.key": "!e[~faXa.kp&<wUM&C3NLG3?/pBv4hW&",
    "auth.opaque": "8ee0f2c2cbba476db0a8a81fcde4cbee",
    "auth.realm": "formshare@qlands.com",
    "auth.register_users_via_api": "false",
    "auth.register_users_via_web": "true",
    "auth.share_projects_among_users": "false",
    "auth.allow_guest_access": "false",
    "auth.allow_edit_profile_name": "true",
    "auth.allow_user_change_password": "true",
    "auth.auto_accept_collaboration": "true",
    "perform_post_checks": "false",
    "ignore_email_check": "true",
    "celery.broker": "amqp://formshare:formshare@localhost:5672/formshare",
    "celery.backend": "rpc://formshare:formshare@localhost:5672/formshare",
    "celery.taskname": "fstask",
    "elasticfeeds.feed_index": "formshare_feeds",
    "elasticfeeds.network_index": "formshare_network",
    "elasticsearch.user.index_name": "formshare_users",
    "elasticsearch.records.index_name": "formshare_records",
    "repository.path": "/home/cquiros/temp/formshare",
    "odktools.path": "/home/cquiros/odktools",
    "mysql.cnf": "/home/cquiros/data/projects2017/personal/software/FormShare/mysql.cnf",
    "mysql.host": "localhost",
    "mysql.port": "3306",
    "mysql.user": "root",
    "mysql.password": "test",
    "mail.server.available": "false",
    "mail.server": "",
    "mail.port": "",
    "mail.login": "",
    "mail.password": "",
    "mail.starttls": "false",
    "mail.ssl": "true",
    "mail.from": "noreply@qlands.com",
    "mail.error": "formshare_support@qlands.com",
}
import json
import os
from zipfile import ZipFile

import gitlab
from django.conf import settings

from amelie.data_export.exporters.exporter import DataExporter


class GitLabDataExporter(DataExporter):
    def export_data(self):
        self.log.debug("Exporting gitlab data for {} to {}".format(self.data_export.person, self.filename))

        ad_name = self.data_export.person.get_adname()

        if not ad_name:
            return None

        server = settings.CLAUDIA_GITLAB['SERVER']
        token = settings.CLAUDIA_GITLAB['TOKEN']
        verify_ssl = settings.CLAUDIA_GITLAB['VERIFY_SSL']

        git = gitlab.Gitlab(server, private_token=token, ssl_verify=verify_ssl)

        git_user_list = git.users.list(username=ad_name)
        if not git_user_list:
            return None

        git_user = git_user_list[0]

        user_data = self.download_user_data(git_user)

        with ZipFile(self.filename, mode='w') as zip_file:
            zip_file.writestr('metadata.json', json.dumps(user_data, indent=2, sort_keys=True))

            for project_id, project_info in user_data['projects'].items():
                name = project_info['path']
                path = '/projects/{}/snapshot'.format(project_id)
                project = git.projects.get(project_id)

                zip_file.writestr(
                    os.path.join(name, 'snapshot.tar'),
                    git.http_get(path, wiki=True).content
                )
                zip_file.writestr(
                    os.path.join(name, 'files.tar.gz'),
                    project.repository_archive()
                )
                zip_file.writestr(
                    os.path.join(name, 'project.json'),
                    json.dumps({
                        'id': project_id,
                        'commits': self.list_sub_objects(project.commits, [
                            'short_id', 'title', 'created_at', 'parent_ids', 'message', 'author_name', 'author_email',
                            'authored_date', 'committer_name', 'committer_email', 'committed_date'
                        ]),
                        'branches': self.list_sub_objects(project.branches, [
                            'name', 'commit', 'merged', 'protected', 'developers_can_push', 'developers_can_merge'
                        ]),
                        'members': self.list_sub_objects(project.members, ['access_level', 'state']),
                        # 'customattributes': self.list_sub_objects(project.customattributes),
                        # 'deployments': self.list_sub_objects(project.deployments),
                        # 'environments': self.list_sub_objects(project.environments),
                        # 'events': self.list_sub_objects(project.events),
                        # 'hooks': self.list_sub_objects(project.hooks),
                        # 'issues': self.list_sub_objects(project.issues),
                        # 'jobs': self.list_sub_objects(project.jobs),
                        'keys': self.list_sub_objects(project.keys, ['title', 'key', 'created_at']),
                        # 'labels': self.list_sub_objects(project.labels),
                        # 'mergerequests': self.list_sub_objects(project.mergerequests),
                        # 'milestones': self.list_sub_objects(project.milestones),
                        # 'pipelines': self.list_sub_objects(project.pipelines),
                        # 'pipelineschedules': self.list_sub_objects(project.pipelineschedules),
                        'protectedbranches': self.list_sub_objects(project.protectedbranches, [
                            "merge_access_levels", "push_access_levels"]),
                        'runners': self.list_sub_objects(project.runners, [
                            "active", "description", "is_shared", "name", "online",
                            "status"]),
                        # 'snippets': self.list_sub_objects(project.snippets),
                        # 'tags': self.list_sub_objects(project.tags),
                        # 'variables': self.list_sub_objects(project.variables),
                        # 'wikis': self.list_sub_objects(project.wikis),
                    }, indent=2, sort_keys=True)
                )

        return self.filename

    @staticmethod
    def download_user_data(git_user):
        user_data = {}

        for attribute in [
            'id', 'name', 'username', 'state', 'avatar_url', 'web_url', 'created_at', 'bio', 'location', 'skype',
            'linkedin', 'twitter', 'website_url', 'organization', 'last_sign_in_at', 'confirmed_at', 'last_activity_on',
            'email', 'theme_id', 'color_scheme_id', 'projects_limit', 'current_sign_in_at', 'can_create_group',
            'can_create_project', 'two_factor_enabled', 'external', 'is_admin'
        ]:
            user_data[attribute] = getattr(git_user, attribute, None)

        user_data['ssh_keys'] = GitLabDataExporter.list_sub_objects(git_user.keys, ['title', 'key', 'created_at'])
        user_data['gpg_keys'] = GitLabDataExporter.list_sub_objects(git_user.gpgkeys, ['title', 'key', 'created_at'])
        user_data['extra_email'] = GitLabDataExporter.list_sub_objects(git_user.emails, ['email'])
        user_data['events'] = GitLabDataExporter.list_sub_objects(git_user.events, [
            'project_id', 'action_name', 'target_id', 'target_iid', 'target_type', 'author_id', 'target_title',
            'created_at', 'push_data', 'author_username'
        ])

        user_data['projects'] = GitLabDataExporter.list_sub_objects(git_user.projects, [
            'description', 'name', 'name_with_namespace', 'path', 'path_with_namespace', 'created_at',
            'default_branch', 'tag_list', 'ssh_url_to_repo', 'http_url_to_repo', 'web_url', 'avatar_url', 'star_count',
            'forks_count', 'last_activity_at', 'archived', 'visibility', 'resolve_outdated_diff_discussions',
            'container_registry_enabled', 'issues_enabled', 'merge_requests_enabled', 'wiki_enabled', 'jobs_enabled',
            'snippets_enabled', 'shared_runners_enabled', 'lfs_enabled', 'creator_id', 'import_status',
            'open_issues_count', 'public_jobs', 'ci_config_path', 'shared_with_groups',
            'only_allow_merge_if_pipeline_succeeds', 'request_access_enabled',
            'only_allow_merge_if_all_discussions_are_resolved', 'printing_merge_request_link_enabled',
            'merge_method',
        ])

        return user_data

    @staticmethod
    def list_sub_objects(object_key, fields=None):
        result = {}
        try:
            for index, obj in enumerate(object_key.list()):
                if fields:
                    obj_data = {}
                    for attribute in fields:
                        obj_data[attribute] = getattr(obj, attribute, None)
                else:
                    obj_data = obj.attributes
                    obj_data.pop(obj._id_attr, None)
                    for key in list(obj_data.keys()):
                        if key.startswith('_'):
                            obj_data.pop(key)
                result[getattr(obj, obj._id_attr or 'NO_ID', index)] = obj_data
        except gitlab.GitlabListError:
            pass
        return result

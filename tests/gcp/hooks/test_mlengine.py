# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import unittest
from unittest import mock

from googleapiclient.errors import HttpError

from airflow.gcp.hooks import mlengine as hook


class TestMLEngineHook(unittest.TestCase):

    @mock.patch("airflow.gcp.hooks.mlengine.MLEngineHook._authorize")
    @mock.patch("airflow.gcp.hooks.mlengine.build")
    def test_mle_engine_client_creation(self, mock_build, mock_authorize):
        mle_engine_hook = hook.MLEngineHook()

        result = mle_engine_hook.get_conn()

        self.assertEqual(mock_build.return_value, result)
        mock_build.assert_called_with(
            'ml', 'v1', http=mock_authorize.return_value, cache_discovery=False
        )

    @mock.patch("airflow.gcp.hooks.mlengine.MLEngineHook.get_conn")
    def test_create_version(self, mock_get_conn):
        project_id = 'test-project'
        model_name = 'test-model'
        version_name = 'test-version'
        version = {'name': version_name}
        operation_path = 'projects/{}/operations/test-operation'.format(project_id)
        model_path = 'projects/{}/models/{}'.format(project_id, model_name)
        operation_done = {'name': operation_path, 'done': True}

        (
            mock_get_conn.return_value.
            projects.return_value.
            models.return_value.
            versions.return_value.
            create.return_value.
            execute.return_value
        ) = version
        (
            mock_get_conn.return_value.
            projects.return_value.
            operations.return_value.
            get.return_value.
            execute.return_value
        ) = {'name': operation_path, 'done': True}

        mle_engine_hook = hook.MLEngineHook()
        create_version_response = mle_engine_hook.create_version(
            project_id=project_id,
            model_name=model_name,
            version_spec=version
        )

        self.assertEqual(create_version_response, operation_done)
        mock_get_conn.assert_has_calls([
            mock.call().projects().models().versions().create(body=version, parent=model_path),
            mock.call().projects().models().versions().create().execute(),
            mock.call().projects().operations().get(name=version_name),
        ], any_order=True)

    @mock.patch("airflow.gcp.hooks.mlengine.MLEngineHook.get_conn")
    def test_set_default_version(self, mock_get_conn):
        project_id = 'test-project'
        model_name = 'test-model'
        version_name = 'test-version'
        operation_path = 'projects/{}/operations/test-operation'.format(project_id)
        version_path = 'projects/{}/models/{}/versions/{}'.format(project_id, model_name, version_name)
        operation_done = {'name': operation_path, 'done': True}

        (
            mock_get_conn.return_value.
            projects.return_value.
            models.return_value.
            versions.return_value.
            setDefault.return_value.
            execute.return_value
        ) = operation_done

        mle_engine_hook = hook.MLEngineHook()
        set_default_version_response = mle_engine_hook.set_default_version(
            project_id=project_id,
            model_name=model_name,
            version_name=version_name
        )

        self.assertEqual(set_default_version_response, operation_done)
        mock_get_conn.assert_has_calls([
            mock.call().projects().models().versions().setDefault(body={}, name=version_path),
            mock.call().projects().models().versions().setDefault().execute()
        ], any_order=True)

    @mock.patch("airflow.gcp.hooks.mlengine.MLEngineHook.get_conn")
    def test_list_versions(self, mock_get_conn):
        project_id = 'test-project'
        model_name = 'test-model'
        model_path = 'projects/{}/models/{}'.format(project_id, model_name)
        version_names = ['ver_{}'.format(ix) for ix in range(3)]
        response_bodies = [
            {
                'nextPageToken': "TOKEN-{}".format(ix),
                'versions': [ver]
            } for ix, ver in enumerate(version_names)]
        response_bodies[-1].pop('nextPageToken')

        pages_requests = [
            mock.Mock(**{'execute.return_value': body}) for body in response_bodies
        ]
        versions_mock = mock.Mock(
            **{'list.return_value': pages_requests[0], 'list_next.side_effect': pages_requests[1:] + [None]}
        )
        (
            mock_get_conn.return_value.
            projects.return_value.
            models.return_value.
            versions.return_value
        ) = versions_mock

        mle_engine_hook = hook.MLEngineHook()
        list_versions_response = mle_engine_hook.list_versions(
            project_id=project_id, model_name=model_name)

        self.assertEqual(list_versions_response, version_names)
        mock_get_conn.assert_has_calls([
            mock.call().projects().models().versions().list(pageSize=100, parent=model_path),
            mock.call().projects().models().versions().list().execute(),
        ] + [
            mock.call().projects().models().versions().list_next(
                previous_request=pages_requests[i], previous_response=response_bodies[i]
            ) for i in range(3)
        ], any_order=True)

    @mock.patch("airflow.gcp.hooks.mlengine.MLEngineHook.get_conn")
    def test_delete_version(self, mock_get_conn):
        project_id = 'test-project'
        model_name = 'test-model'
        version_name = 'test-version'
        operation_path = 'projects/{}/operations/test-operation'.format(project_id)
        version_path = 'projects/{}/models/{}/versions/{}'.format(project_id, model_name, version_name)
        version = {'name': operation_path}
        operation_not_done = {'name': operation_path, 'done': False}
        operation_done = {'name': operation_path, 'done': True}

        (
            mock_get_conn.return_value.
            projects.return_value.
            operations.return_value.
            get.return_value.
            execute.side_effect
        ) = [operation_not_done, operation_done]

        (
            mock_get_conn.return_value.
            projects.return_value.
            models.return_value.
            versions.return_value.
            delete.return_value.
            execute.return_value
        ) = version

        mle_engine_hook = hook.MLEngineHook()
        delete_version_response = mle_engine_hook.delete_version(
            project_id=project_id, model_name=model_name,
            version_name=version_name)

        self.assertEqual(delete_version_response, operation_done)
        mock_get_conn.assert_has_calls([
            mock.call().projects().models().versions().delete(name=version_path),
            mock.call().projects().models().versions().delete().execute(),
            mock.call().projects().operations().get(name=operation_path),
            mock.call().projects().operations().get().execute()
        ], any_order=True)

    @mock.patch("airflow.gcp.hooks.mlengine.MLEngineHook.get_conn")
    def test_create_model(self, mock_get_conn):
        project_id = 'test-project'
        model_name = 'test-model'
        model = {
            'name': model_name,
        }
        project_path = 'projects/{}'.format(project_id)

        (
            mock_get_conn.return_value.
            projects.return_value.
            models.return_value.
            create.return_value.
            execute.return_value
        ) = model

        mle_engine_hook = hook.MLEngineHook()
        create_model_response = mle_engine_hook.create_model(
            project_id=project_id, model=model
        )

        self.assertEqual(create_model_response, model)
        mock_get_conn.assert_has_calls([
            mock.call().projects().models().create(body=model, parent=project_path),
            mock.call().projects().models().create().execute()
        ])

    @mock.patch("airflow.gcp.hooks.mlengine.MLEngineHook.get_conn")
    def test_get_model(self, mock_get_conn):
        project_id = 'test-project'
        model_name = 'test-model'
        model = {'model': model_name}

        (
            mock_get_conn.return_value.
            projects.return_value.
            models.return_value.
            get.return_value.
            execute.return_value
        ) = model

        mle_engine_hook = hook.MLEngineHook()
        get_model_response = mle_engine_hook.get_model(
            project_id=project_id, model_name=model_name
        )

        self.assertEqual(get_model_response, model)
        mock_get_conn.assert_has_calls([
            mock.call().AAA()
        ])

    @mock.patch("airflow.gcp.hooks.mlengine.MLEngineHook.get_conn")
    def test_create_mlengine_job(self, mock_get_conn):
        project_id = 'test-project'
        job_id = 'test-job-id'
        project_path = 'projects/{}'.format(project_id)
        job_path = 'projects/{}/jobs/{}'.format(project_id, job_id)
        new_job = {
            'jobId': job_id,
            'foo': 4815162342,
        }
        job_succeeded = {
            'jobId': job_id,
            'state': 'SUCCEEDED',
        }
        job_queued = {
            'jobId': job_id,
            'state': 'QUEUED',
        }

        (
            mock_get_conn.return_value.
            projects.return_value.
            jobs.return_value.
            create.return_value.
            execute.return_value
        ) = job_queued
        (
            mock_get_conn.return_value.
            projects.return_value.
            jobs.return_value.
            get.return_value.
            execute.side_effect
        ) = [job_queued, job_succeeded]

        mle_engine_hook = hook.MLEngineHook()
        create_job_response = mle_engine_hook.create_job(
            project_id=project_id, job=new_job
        )

        self.assertEqual(create_job_response, job_succeeded)
        mock_get_conn.assert_has_calls([
            mock.call().projects().jobs().create(body=new_job, parent=project_path),
            mock.call().projects().jobs().get(name=job_path),
            mock.call().projects().jobs().get().execute()
        ], any_order=True)

    @mock.patch("airflow.gcp.hooks.mlengine.MLEngineHook.get_conn")
    def test_create_mlengine_job_reuse_existing_job_by_default(self, mock_get_conn):
        project_id = 'test-project'
        job_id = 'test-job-id'
        project_path = 'projects/{}'.format(project_id)
        job_path = 'projects/{}/jobs/{}'.format(project_id, job_id)
        job_succeeded = {
            'jobId': job_id,
            'foo': 4815162342,
            'state': 'SUCCEEDED',
        }
        error_job_exists = HttpError(resp=mock.MagicMock(status=409), content=b'Job already exists')

        (
            mock_get_conn.return_value.
            projects.return_value.
            jobs.return_value.
            create.return_value.
            execute.side_effect
        ) = error_job_exists
        (
            mock_get_conn.return_value.
            projects.return_value.
            jobs.return_value.
            get.return_value.
            execute.return_value
        ) = job_succeeded

        mle_engine_hook = hook.MLEngineHook()
        create_job_response = mle_engine_hook.create_job(
            project_id=project_id, job=job_succeeded)

        self.assertEqual(create_job_response, job_succeeded)
        mock_get_conn.assert_has_calls([
            mock.call().projects().jobs().create(body=job_succeeded, parent=project_path),
            mock.call().projects().jobs().create().execute(),
            mock.call().projects().jobs().get(name=job_path),
            mock.call().projects().jobs().get().execute()
        ], any_order=True)

    @mock.patch("airflow.gcp.hooks.mlengine.MLEngineHook.get_conn")
    def test_create_mlengine_job_check_existing_job_failed(self, mock_get_conn):
        project_id = 'test-project'
        job_id = 'test-job-id'
        my_job = {
            'jobId': job_id,
            'foo': 4815162342,
            'state': 'SUCCEEDED',
            'someInput': {
                'input': 'someInput'
            }
        }
        different_job = {
            'jobId': job_id,
            'foo': 4815162342,
            'state': 'SUCCEEDED',
            'someInput': {
                'input': 'someDifferentInput'
            }
        }
        error_job_exists = HttpError(resp=mock.MagicMock(status=409), content=b'Job already exists')

        (
            mock_get_conn.return_value.
            projects.return_value.
            jobs.return_value.
            create.return_value.
            execute.side_effect
        ) = error_job_exists
        (
            mock_get_conn.return_value.
            projects.return_value.
            jobs.return_value.
            get.return_value.
            execute.return_value
        ) = different_job

        def check_input(existing_job):
            return existing_job.get('someInput', None) == \
                my_job['someInput']

        with self.assertRaises(HttpError):
            mle_engine_hook = hook.MLEngineHook()
            mle_engine_hook.create_job(
                project_id=project_id, job=my_job,
                use_existing_job_fn=check_input)

    @mock.patch("airflow.gcp.hooks.mlengine.MLEngineHook.get_conn")
    def test_create_mlengine_job_check_existing_job_success(self, mock_get_conn):
        project_id = 'test-project'
        job_id = 'test-job-id'
        my_job = {
            'jobId': job_id,
            'foo': 4815162342,
            'state': 'SUCCEEDED',
            'someInput': {
                'input': 'someInput'
            }
        }
        error_job_exists = HttpError(resp=mock.MagicMock(status=409), content=b'Job already exists')

        (
            mock_get_conn.return_value.
            projects.return_value.
            jobs.return_value.
            create.return_value.
            execute.side_effect
        ) = error_job_exists
        (
            mock_get_conn.return_value.
            projects.return_value.
            jobs.return_value.
            get.return_value.
            execute.return_value
        ) = my_job

        def check_input(existing_job):
            return existing_job.get('someInput', None) == my_job['someInput']

        mle_engine_hook = hook.MLEngineHook()
        create_job_response = mle_engine_hook.create_job(
            project_id=project_id, job=my_job,
            use_existing_job_fn=check_input)

        self.assertEqual(create_job_response, my_job)

# -*- coding: utf-8 -*-
#
# This file is part of Zenodo.
# Copyright (C) 2016 CERN.
#
# Zenodo is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Zenodo is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Zenodo; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Test validation in Zenodo deposit REST API."""

from __future__ import absolute_import, print_function

import json

from invenio_search import current_search
from six import BytesIO


def get_data(**kwargs):
    """Get test data."""
    test_data = dict(
        metadata=dict(
            upload_type='presentation',
            title='Test title',
            creators=[
                dict(name='Doe, John', affiliation='Atlantis'),
            ],
            description='Test Description',
            publication_date='2013-05-08',
            access_right='open'
        )
    )
    test_data['metadata'].update(kwargs)
    return test_data


def test_missing_files(api_client, deposit, json_auth_headers,
                       deposit_url, get_json):
    """Test data validation."""
    client = api_client
    headers = json_auth_headers

    # Create
    res = client.post(
        deposit_url, data=json.dumps(get_data()), headers=headers)
    links = get_json(res, code=201)['links']
    current_search.flush_and_refresh(index='deposits')

    # Publish - not possible (file is missing)
    res = client.post(links['publish'], headers=headers)
    data = get_json(res, code=400)
    assert len(data['errors']) == 1


def test_file_ops(api_client, deposit, json_auth_headers, auth_headers,
                  deposit_url, get_json):
    """Test data validation."""
    client = api_client
    headers = json_auth_headers
    auth = auth_headers

    # Create empty deposit
    res = client.post(deposit_url, data=json.dumps({}), headers=headers)
    links = get_json(res, code=201)['links']
    current_search.flush_and_refresh(index='deposits')

    # Upload same file twice - first ok, second not
    for code in [201, 400]:
        f = dict(file=(BytesIO(b'test'), 'test1.txt'), name='test1.txt')
        res = client.post(links['files'], data=f, headers=auth)
        res.status_code == code

    # Upload another file
    client.post(
        links['files'],
        data=dict(file=(BytesIO(b'test'), 'test2.txt'), name='test2.txt'),
        headers=auth
    )

    # List files
    data = get_json(client.get(links['files'], headers=headers), code=200)
    assert len(data) == 2
    file_id = data[0]['id']
    file_url = '{0}/{1}'.format(links['files'], file_id)

    # Get file
    assert client.get(file_url, headers=headers).status_code == 200

    # File does not exists
    assert client.get(
        '{0}/invalid'.format(links['files']), headers=headers
    ).status_code == 404

    data = get_json(client.get(links['files'], headers=headers), code=200)
    invalid_files_list = [dict(filename=x['filename']) for x in data]
    ok_files_list = list(reversed([dict(id=x['id']) for x in data]))

    # Sort - invalid
    assert client.put(
        links['files'], data=json.dumps(invalid_files_list), headers=headers
    ).status_code == 400

    # Sort - valid
    assert client.put(
        links['files'], data=json.dumps(ok_files_list), headers=headers
    ).status_code == 200

    # Delete
    assert client.delete(file_url, headers=headers).status_code == 204
    assert client.get(file_url, headers=headers).status_code == 404
    data = get_json(client.get(links['files'], headers=headers), code=200)
    assert len(data) == 1
    file_id = data[0]['id']
    file_url = '{0}/{1}'.format(links['files'], file_id)

    # Rename
    assert client.put(
        file_url, data=json.dumps(dict(filename='rename.txt')), headers=headers
    ).status_code == 200

    # Bad renaming
    for data in [dict(name='test.txt'), dict(filename='../../etc/passwd')]:
        assert client.put(
            file_url, data=json.dumps(data), headers=headers
        ).status_code == 400

    data = get_json(client.get(file_url, headers=headers), code=200)
    assert data['filename'] == 'rename.txt'

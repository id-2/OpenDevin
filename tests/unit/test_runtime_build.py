import os
import tempfile
from importlib.metadata import version
from unittest.mock import ANY, MagicMock, call, patch

import pytest
import toml
from pytest import TempPathFactory

from openhands.runtime.utils.runtime_build import (
    _generate_dockerfile,
    _get_package_version,
    _put_source_code_to_dir,
    build_runtime_image,
    get_runtime_image_repo,
    get_runtime_image_repo_and_tag,
    prep_docker_build_folder,
)

OD_VERSION = f'od_v{_get_package_version()}'


@pytest.fixture
def temp_dir(tmp_path_factory: TempPathFactory) -> str:
    return str(tmp_path_factory.mktemp('test_runtime_build'))


def _check_source_code_in_dir(temp_dir):
    # assert there is a folder called 'code' in the temp_dir
    code_dir = os.path.join(temp_dir, 'code')
    assert os.path.exists(code_dir)
    assert os.path.isdir(code_dir)

    # check the source file is the same as the current code base
    assert os.path.exists(os.path.join(code_dir, 'pyproject.toml'))

    # The source code should only include the `openhands` folder, but not the other folders
    assert set(os.listdir(code_dir)) == {
        'agenthub',
        'openhands',
        'pyproject.toml',
        'poetry.lock',
        'LICENSE',
        'README.md',
        'PKG-INFO',
    }
    assert os.path.exists(os.path.join(code_dir, 'openhands'))
    assert os.path.isdir(os.path.join(code_dir, 'openhands'))

    # make sure the version from the pyproject.toml is the same as the current version
    with open(os.path.join(code_dir, 'pyproject.toml'), 'r') as f:
        pyproject = toml.load(f)

    _pyproject_version = pyproject['tool']['poetry']['version']
    assert _pyproject_version == version('openhands-ai')


def test_put_source_code_to_dir(temp_dir):
    _put_source_code_to_dir(temp_dir)
    _check_source_code_in_dir(temp_dir)


def test_docker_build_folder(temp_dir):
    prep_docker_build_folder(
        temp_dir,
        base_image='nikolaik/python-nodejs:python3.11-nodejs22',
        skip_init=False,
    )

    # check the source code is in the folder
    _check_source_code_in_dir(temp_dir)

    # Now check dockerfile is in the folder
    dockerfile_path = os.path.join(temp_dir, 'Dockerfile')
    assert os.path.exists(dockerfile_path)
    assert os.path.isfile(dockerfile_path)

    # check the folder only contains the source code and the Dockerfile
    assert set(os.listdir(temp_dir)) == {'code', 'Dockerfile'}


def test_hash_folder_same(temp_dir):
    dir_hash_1 = prep_docker_build_folder(
        temp_dir,
        base_image='nikolaik/python-nodejs:python3.11-nodejs22',
        skip_init=False,
    )

    with tempfile.TemporaryDirectory() as temp_dir_2:
        dir_hash_2 = prep_docker_build_folder(
            temp_dir_2,
            base_image='nikolaik/python-nodejs:python3.11-nodejs22',
            skip_init=False,
        )
    assert dir_hash_1 == dir_hash_2


def test_hash_folder_diff_init(temp_dir):
    dir_hash_1 = prep_docker_build_folder(
        temp_dir,
        base_image='nikolaik/python-nodejs:python3.11-nodejs22',
        skip_init=False,
    )

    with tempfile.TemporaryDirectory() as temp_dir_2:
        dir_hash_2 = prep_docker_build_folder(
            temp_dir_2,
            base_image='nikolaik/python-nodejs:python3.11-nodejs22',
            skip_init=True,
        )
    assert dir_hash_1 != dir_hash_2


def test_hash_folder_diff_image(temp_dir):
    dir_hash_1 = prep_docker_build_folder(
        temp_dir,
        base_image='nikolaik/python-nodejs:python3.11-nodejs22',
        skip_init=False,
    )

    with tempfile.TemporaryDirectory() as temp_dir_2:
        dir_hash_2 = prep_docker_build_folder(
            temp_dir_2,
            base_image='debian:11',
            skip_init=False,
        )
    assert dir_hash_1 != dir_hash_2


def test_generate_dockerfile_scratch():
    base_image = 'debian:11'
    dockerfile_content = _generate_dockerfile(
        base_image,
        skip_init=False,
    )
    assert base_image in dockerfile_content
    assert 'apt-get update' in dockerfile_content
    assert 'apt-get install -y wget sudo apt-utils' in dockerfile_content
    assert (
        'RUN /openhands/miniforge3/bin/mamba install conda-forge::poetry python=3.11 -y'
        in dockerfile_content
    )

    # Check the update command
    assert 'COPY ./code /openhands/code' in dockerfile_content
    assert (
        '/openhands/miniforge3/bin/mamba run -n base poetry install'
        in dockerfile_content
    )


def test_generate_dockerfile_skip_init():
    base_image = 'debian:11'
    dockerfile_content = _generate_dockerfile(
        base_image,
        skip_init=True,
    )

    # These commands SHOULD NOT include in the dockerfile if skip_init is True
    assert 'RUN apt update && apt install -y wget sudo' not in dockerfile_content
    assert (
        'RUN /openhands/miniforge3/bin/mamba install conda-forge::poetry python=3.11 -y'
        not in dockerfile_content
    )

    # These update commands SHOULD still in the dockerfile
    assert 'COPY ./code /openhands/code' in dockerfile_content
    assert (
        '/openhands/miniforge3/bin/mamba run -n base poetry install'
        in dockerfile_content
    )


def test_get_runtime_image_repo_and_tag_eventstream():
    base_image = 'debian:11'
    img_repo, img_tag = get_runtime_image_repo_and_tag(base_image)
    assert (
        img_repo == f'{get_runtime_image_repo()}'
        and img_tag == f'{OD_VERSION}_image_debian_tag_11'
    )

    base_image = 'nikolaik/python-nodejs:python3.11-nodejs22'
    img_repo, img_tag = get_runtime_image_repo_and_tag(base_image)
    assert (
        img_repo == f'{get_runtime_image_repo()}'
        and img_tag
        == f'{OD_VERSION}_image_nikolaik_s_python-nodejs_tag_python3.11-nodejs22'
    )

    base_image = 'ubuntu'
    img_repo, img_tag = get_runtime_image_repo_and_tag(base_image)
    assert (
        img_repo == f'{get_runtime_image_repo()}'
        and img_tag == f'{OD_VERSION}_image_ubuntu_tag_latest'
    )


def test_build_runtime_image_from_scratch(temp_dir):
    base_image = 'debian:11'

    from_scratch_hash = prep_docker_build_folder(
        temp_dir,
        base_image,
        skip_init=False,
    )

    mock_runtime_builder = MagicMock()
    mock_runtime_builder.image_exists.return_value = False
    mock_runtime_builder.build.return_value = (
        f'{get_runtime_image_repo()}:{from_scratch_hash}'
    )

    image_name = build_runtime_image(base_image, mock_runtime_builder)
    mock_runtime_builder.build.assert_called_once_with(
        path=ANY,
        tags=[
            f'{get_runtime_image_repo()}:{from_scratch_hash}',
            f'{get_runtime_image_repo()}:{OD_VERSION}_image_debian_tag_11',
        ],
    )
    assert image_name == f'{get_runtime_image_repo()}:{from_scratch_hash}'


def test_build_runtime_image_exact_hash_exist(temp_dir):
    base_image = 'debian:11'

    from_scratch_hash = prep_docker_build_folder(
        temp_dir,
        base_image,
        skip_init=False,
    )

    mock_runtime_builder = MagicMock()
    mock_runtime_builder.image_exists.return_value = True
    mock_runtime_builder.build.return_value = (
        f'{get_runtime_image_repo()}:{from_scratch_hash}'
    )

    image_name = build_runtime_image(base_image, mock_runtime_builder)
    assert image_name == f'{get_runtime_image_repo()}:{from_scratch_hash}'
    mock_runtime_builder.build.assert_not_called()


@patch('openhands.runtime.utils.runtime_build._build_sandbox_image')
def test_build_runtime_image_exact_hash_not_exist(mock_build_sandbox_image, temp_dir):
    base_image = 'debian:11'
    repo, latest_image_tag = get_runtime_image_repo_and_tag(base_image)
    latest_image_name = f'{repo}:{latest_image_tag}'

    from_scratch_hash = prep_docker_build_folder(
        temp_dir,
        base_image,
        skip_init=False,
    )
    with tempfile.TemporaryDirectory() as temp_dir_2:
        non_from_scratch_hash = prep_docker_build_folder(
            temp_dir_2,
            base_image,
            skip_init=True,
        )

    mock_runtime_builder = MagicMock()
    # Set up mock_runtime_builder.image_exists to return False then True
    mock_runtime_builder.image_exists.side_effect = [False, True]

    with patch(
        'openhands.runtime.utils.runtime_build.prep_docker_build_folder'
    ) as mock_prep_docker_build_folder:
        mock_prep_docker_build_folder.side_effect = [
            from_scratch_hash,
            non_from_scratch_hash,
        ]

        image_name = build_runtime_image(base_image, mock_runtime_builder)

        mock_prep_docker_build_folder.assert_has_calls(
            [
                call(ANY, base_image=base_image, skip_init=False, extra_deps=None),
                call(
                    ANY, base_image=latest_image_name, skip_init=True, extra_deps=None
                ),
            ]
        )

        mock_build_sandbox_image.assert_called_once_with(
            docker_folder=ANY,
            runtime_builder=mock_runtime_builder,
            target_image_repo=repo,
            target_image_hash_tag=from_scratch_hash,
            target_image_tag=latest_image_tag,
        )
        assert image_name == f'{repo}:{from_scratch_hash}'

from __future__ import absolute_import, unicode_literals, division

import pytest

from c8 import C8Client
from c8.fabric import StandardFabric
from tests.executors import (
    TestAsyncExecutor,
    TestBatchExecutor,
    TestTransactionExecutor
)
from tests.helpers import (
    generate_fabric_name,
    generate_col_name,
    generate_string,
    generate_username,
    generate_graph_name,
)

global_data = dict()


def pytest_addoption(parser):
    parser.addoption('--host', action='store', default='127.0.0.1')
    parser.addoption('--port', action='store', default='8529')
    parser.addoption('--passwd', action='store', default='passwd')
    parser.addoption("--complete", action="store_true")


# noinspection PyShadowingNames
def pytest_configure(config):
    client = C8Client(
        host=config.getoption('host'),
        port=config.getoption('port')
    )
    sys_fabric = client.fabric(
        name='_system',
        username='root',
        password=config.getoption('passwd')
    )

    # Create a user and non-system fabric for testing.
    username = generate_username()
    password = generate_string()
    tst_fabric_name = generate_fabric_name()
    bad_fabric_name = generate_fabric_name()
    sys_fabric.create_fabric(
        name=tst_fabric_name,
        users=[{
            'active': True,
            'username': username,
            'password': password,
        }]
    )
    tst_fabric = client.fabric(tst_fabric_name, username, password)
    bad_fabric = client.fabric(bad_fabric_name, username, password)

    # Create a standard collection for testing.
    col_name = generate_col_name()
    tst_col = tst_fabric.create_collection(col_name, edge=False)
    tst_col.add_skiplist_index(['val'])
    tst_col.add_fulltext_index(['text'])
    geo_index = tst_col.add_geo_index(['loc'])

    # Create a legacy edge collection for testing.
    lecol_name = generate_col_name()
    tst_fabric.create_collection(lecol_name, edge=True)

    # Create test vertex & edge collections and graph.
    graph_name = generate_graph_name()
    ecol_name = generate_col_name()
    fvcol_name = generate_col_name()
    tvcol_name = generate_col_name()
    tst_graph = tst_fabric.create_graph(graph_name)
    tst_graph.create_vertex_collection(fvcol_name)
    tst_graph.create_vertex_collection(tvcol_name)
    tst_graph.create_edge_definition(
        edge_collection=ecol_name,
        from_vertex_collections=[fvcol_name],
        to_vertex_collections=[tvcol_name]
    )

    global_data.update({
        'client': client,
        'username': username,
        'password': password,
        'sys_fabric': sys_fabric,
        'tst_fabric': tst_fabric,
        'bad_fabric': bad_fabric,
        'geo_index': geo_index,
        'col_name': col_name,
        'lecol_name': lecol_name,
        'graph_name': graph_name,
        'ecol_name': ecol_name,
        'fvcol_name': fvcol_name,
        'tvcol_name': tvcol_name,
    })


# noinspection PyShadowingNames
def pytest_unconfigure(*_):  # pragma: no cover
    sys_fabric = global_data['sys_fabric']

    # Remove all test async jobs.
    sys_fabric.clear_async_jobs()

    # Remove all test tasks.
    for task in sys_fabric.tasks():
        task_name = task['name']
        if task_name.startswith('test_task'):
            sys_fabric.delete_task(task_name, ignore_missing=True)

    # Remove all test users.
    for user in sys_fabric.users():
        username = user['username']
        if username.startswith('test_user'):
            sys_fabric.delete_user(username, ignore_missing=True)

    # Remove all test fabrics.
    for fabric_name in sys_fabric.fabrics():
        if fabric_name.startswith('test_fabric'):
            sys_fabric.delete_fabric(fabric_name, ignore_missing=True)

    # Remove all test collections.
    for collection in sys_fabric.collections():
        col_name = collection['name']
        if col_name.startswith('test_collection'):
            sys_fabric.delete_collection(col_name, ignore_missing=True)


# noinspection PyProtectedMember
def pytest_generate_tests(metafunc):
    tst_fabric = global_data['tst_fabric']
    bad_fabric = global_data['bad_fabric']

    tst_fabrics = [tst_fabric]
    bad_fabrics = [bad_fabric]

    if metafunc.config.getoption('complete'):
        tst = metafunc.module.__name__.split('.test_', 1)[-1]
        tst_conn = tst_fabric._conn
        bad_conn = bad_fabric._conn

        if tst in {'collection', 'document', 'graph', 'c8ql', 'index'}:
            # Add test transaction fabrics
            tst_txn_fabric = StandardFabric(tst_conn)
            tst_txn_fabric._executor = TestTransactionExecutor(tst_conn)
            tst_txn_fabric._is_transaction = True
            tst_fabrics.append(tst_txn_fabric)

            bad_txn_fabric = StandardFabric(bad_conn)
            bad_txn_fabric._executor = TestTransactionExecutor(bad_conn)
            bad_fabrics.append(bad_txn_fabric)

        if tst not in {'async', 'batch', 'transaction', 'client', 'exception'}:
            # Add test async fabrics
            tst_async_fabric = StandardFabric(tst_conn)
            tst_async_fabric._executor = TestAsyncExecutor(tst_conn)
            tst_fabrics.append(tst_async_fabric)

            bad_async_fabric = StandardFabric(bad_conn)
            bad_async_fabric._executor = TestAsyncExecutor(bad_conn)
            bad_fabrics.append(bad_async_fabric)

            # Add test batch fabrics
            tst_batch_fabric = StandardFabric(tst_conn)
            tst_batch_fabric._executor = TestBatchExecutor(tst_conn)
            tst_fabrics.append(tst_batch_fabric)

            bad_batch_bfabric = StandardFabric(bad_conn)
            bad_batch_bfabric._executor = TestBatchExecutor(bad_conn)
            bad_fabrics.append(bad_batch_bfabric)

    if 'fabric' in metafunc.fixturenames and 'bad_fabric' in metafunc.fixturenames:
        metafunc.parametrize('fabric,bad_fabric', zip(tst_fabrics, bad_fabrics))

    elif 'fabric' in metafunc.fixturenames:
        metafunc.parametrize('fabric', tst_fabrics)

    elif 'bad_fabric' in metafunc.fixturenames:
        metafunc.parametrize('bad_fabric', bad_fabrics)


@pytest.fixture(autouse=False)
def client():
    return global_data['client']


@pytest.fixture(autouse=False)
def sys_fabric():
    return global_data['sys_fabric']


@pytest.fixture(autouse=False)
def username():
    return global_data['username']


@pytest.fixture(autouse=False)
def password():
    return global_data['password']


@pytest.fixture(autouse=False)
def col(fabric):
    collection = fabric.collection(global_data['col_name'])
    collection.truncate()
    return collection


@pytest.fixture(autouse=False)
def bad_col(bad_fabric):
    return bad_fabric.collection(global_data['col_name'])


@pytest.fixture(autouse=False)
def geo():
    return global_data['geo_index']


@pytest.fixture(autouse=False)
def lecol(fabric):
    collection = fabric.collection(global_data['lecol_name'])
    collection.truncate()
    return collection


@pytest.fixture(autouse=False)
def graph(fabric):
    return fabric.graph(global_data['graph_name'])


@pytest.fixture(autouse=False)
def bad_graph(bad_fabric):
    return bad_fabric.graph(global_data['graph_name'])


# noinspection PyShadowingNames
@pytest.fixture(autouse=False)
def fvcol(graph):
    collection = graph.vertex_collection(global_data['fvcol_name'])
    collection.truncate()
    return collection


# noinspection PyShadowingNames
@pytest.fixture(autouse=False)
def tvcol(graph):
    collection = graph.vertex_collection(global_data['tvcol_name'])
    collection.truncate()
    return collection


# noinspection PyShadowingNames
@pytest.fixture(autouse=False)
def bad_fvcol(bad_graph):
    return bad_graph.vertex_collection(global_data['fvcol_name'])


# noinspection PyShadowingNames
@pytest.fixture(autouse=False)
def ecol(graph):
    collection = graph.edge_collection(global_data['ecol_name'])
    collection.truncate()
    return collection


# noinspection PyShadowingNames
@pytest.fixture(autouse=False)
def bad_ecol(bad_graph):
    return bad_graph.edge_collection(global_data['ecol_name'])


@pytest.fixture(autouse=False)
def docs():
    return [
        {'_key': '1', 'val': 1, 'text': 'foo', 'loc': [1, 1]},
        {'_key': '2', 'val': 2, 'text': 'foo', 'loc': [2, 2]},
        {'_key': '3', 'val': 3, 'text': 'foo', 'loc': [3, 3]},
        {'_key': '4', 'val': 4, 'text': 'bar', 'loc': [4, 4]},
        {'_key': '5', 'val': 5, 'text': 'bar', 'loc': [5, 5]},
        {'_key': '6', 'val': 6, 'text': 'bar', 'loc': [5, 5]},
    ]


@pytest.fixture(autouse=False)
def fvdocs():
    return [
        {'_key': '1', 'val': 1},
        {'_key': '2', 'val': 2},
        {'_key': '3', 'val': 3},
    ]


@pytest.fixture(autouse=False)
def tvdocs():
    return [
        {'_key': '4', 'val': 4},
        {'_key': '5', 'val': 5},
        {'_key': '6', 'val': 6},
    ]


@pytest.fixture(autouse=False)
def edocs():
    fv = global_data['fvcol_name']
    tv = global_data['tvcol_name']
    return [
        {'_key': '1', '_from': '{}/1'.format(fv), '_to': '{}/4'.format(tv)},
        {'_key': '2', '_from': '{}/1'.format(fv), '_to': '{}/5'.format(tv)},
        {'_key': '3', '_from': '{}/6'.format(fv), '_to': '{}/2'.format(tv)},
        {'_key': '4', '_from': '{}/8'.format(fv), '_to': '{}/7'.format(tv)},
    ]

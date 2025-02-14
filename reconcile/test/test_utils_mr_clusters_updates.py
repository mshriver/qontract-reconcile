from io import StringIO
from unittest import TestCase
from unittest.mock import (
    MagicMock,
    patch,
)

import reconcile.utils.mr.clusters_updates as sut

from .fixtures import Fixtures

fxt = Fixtures("clusters")


@patch.object(sut.CreateClustersUpdates, "cancel")
class TestProcess(TestCase):
    def setUp(self):
        self.clusters = [fxt.get_anymarkup("cluster1.yml")]
        self.raw_clusters = fxt.get("cluster1.yml")

    def test_no_changes(self, cancel):
        cli = MagicMock()
        c = sut.CreateClustersUpdates({})
        c.branch = "abranch"
        c.main_branch = "main"
        c.process(cli)
        cancel.assert_called_once()

        cli.project.files.get.assert_not_called()

    def test_changes_to_spec(self, cancel):
        cli = MagicMock()
        cli.project.files.get.return_value = self.raw_clusters.encode()
        c = sut.CreateClustersUpdates(
            {"cluster1": {"spec": {"id": "42"}, "root": {}, "path": "/a/path"}}
        )
        c.branch = "abranch"
        c.main_branch = "main"
        c.process(cli)
        self.clusters[0]["spec"]["id"] = "42"

        cnt = StringIO()
        sut.yaml.dump(self.clusters[0], cnt)
        cli.update_file.assert_called_once_with(
            branch_name="abranch",
            file_path="/a/path",
            commit_message="update cluster cluster1 spec fields",
            content=cnt.getvalue(),
        )
        cancel.assert_not_called()

    def test_changes_to_root(self, cancel):
        cli = MagicMock()
        cli.project.files.get.return_value = self.raw_clusters.encode()
        c = sut.CreateClustersUpdates(
            {
                "cluster1": {
                    "spec": {},
                    "root": {"prometheusUrl": "aprometheusurl"},
                    "path": "/a/path",
                }
            }
        )
        c.branch = "abranch"
        c.main_branch = "main"
        c.process(cli)
        self.clusters[0]["prometheusUrl"] = "aprometheusurl"

        cnt = StringIO()
        sut.yaml.dump(self.clusters[0], cnt)
        cli.update_file.assert_called_once_with(
            branch_name="abranch",
            file_path="/a/path",
            commit_message="update cluster cluster1 spec fields",
            content=cnt.getvalue(),
        )
        cancel.assert_not_called()

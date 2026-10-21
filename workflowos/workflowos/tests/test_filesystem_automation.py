# workflowos/tests/test_filesystem_automation.py
import os
import shutil
import tempfile
from workflowos.automation.adapters.filesystem import FileSystemAdapter


def test_real_file_lifecycle_automation():
    # Setup isolated test directory
    with tempfile.TemporaryDirectory() as temp_dir:
        in_dir = os.path.join(temp_dir, "Input")
        out_dir = os.path.join(temp_dir, "Output")
        os.makedirs(in_dir, exist_ok=True)
        os.makedirs(out_dir, exist_ok=True)

        context = {}

        # 1. Create File
        file_path = os.path.join(in_dir, "test_invoice.txt")
        ok, res, err = FileSystemAdapter.create_file(
            db=None,
            params={"file_path": file_path, "content": "Hello WorkFlowOS\n"},
            context=context
        )
        assert ok is True
        assert os.path.exists(file_path)
        assert context["file_path"] == os.path.abspath(file_path)

        # 2. Rename File
        ok, res, err = FileSystemAdapter.rename_file(
            db=None,
            params={"new_name": "renamed_invoice.txt"},
            context=context
        )
        assert ok is True
        renamed_path = os.path.join(in_dir, "renamed_invoice.txt")
        assert os.path.exists(renamed_path)
        assert not os.path.exists(file_path)
        assert context["file_path"] == os.path.abspath(renamed_path)

        # 3. Move File
        ok, res, err = FileSystemAdapter.move_file(
            db=None,
            params={"destination_dir": out_dir},
            context=context
        )
        assert ok is True
        dest_path = os.path.join(out_dir, "renamed_invoice.txt")
        assert os.path.exists(dest_path)
        assert not os.path.exists(renamed_path)
        assert context["file_path"] == os.path.abspath(dest_path)


def test_real_file_missing_source_fails():
    with tempfile.TemporaryDirectory() as temp_dir:
        context = {}
        ok, res, err = FileSystemAdapter.rename_file(
            db=None,
            params={"source_path": os.path.join(temp_dir, "non_existent.txt"), "new_name": "new.txt"},
            context=context
        )
        assert ok is False
        assert "does not exist" in err

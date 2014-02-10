# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Tests for testing filesystem
"""
from chevah.compat import (
    system_users,
    )

from chevah.compat.testing import (
    manufacture as compat_mk,
    TEST_ACCOUNT_USERNAME,
    TEST_ACCOUNT_PASSWORD,
    )
from chevah.empirical import EmpiricalTestCase, mk, conditionals
from chevah.empirical.filesystem import LocalTestFilesystem


class TestElevatedLocalTestFilesystem(EmpiricalTestCase):
    """
    Test for LocalTestFilesystem using different account.
    """

    @classmethod
    def setUpClass(cls):
        super(TestElevatedLocalTestFilesystem, cls).setUpClass()

        user = TEST_ACCOUNT_USERNAME
        password = TEST_ACCOUNT_PASSWORD
        token = compat_mk.makeToken(username=user, password=password)
        home_folder_path = system_users.getHomeFolder(
            username=user, token=token)
        cls.avatar = compat_mk.makeFilesystemOSAvatar(
            name=user,
            home_folder_path=home_folder_path,
            token=token,
            )

    def checkTemporaryFolderInitialization(self, filesystem):
        """
        Check that temporary folder can be initialized.
        """
        # Temporary folder can be initialized and is owned by the dedicate
        # user.
        try:
            filesystem.setUpTemporaryFolder()
            owner = filesystem.getOwner(filesystem.temp_segments)

            self.assertEqual(TEST_ACCOUNT_USERNAME, owner)
        finally:
            filesystem.tearDownTemporaryFolder()

    @conditionals.onOSFamily('posix')
    def test_temporary_folder_unix(self):
        """
        On Unix the normal temporary folder is used.
        """
        filesystem = LocalTestFilesystem(avatar=self.avatar)

        # We check that the elevated filesystem start with the same
        # path as normal filesystem
        self.assertEqual(
            mk.fs.temp_segments[:-1], filesystem.temp_segments[:-1])

        self.checkTemporaryFolderInitialization(filesystem)

    @conditionals.onOSFamily('nt')
    def test_temporary_folder_nt(self):
        """
        For elevated accounts temporary folder is not located insider
        user default tempo folder and we can start and stop the
        temporary folder.
        """
        filesystem = LocalTestFilesystem(avatar=self.avatar)

        temporary = filesystem.temp_segments
        self.assertEqual([u'c', u'temp'], temporary[:2])

        self.checkTemporaryFolderInitialization(filesystem)
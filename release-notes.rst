Release notes for chevah.empirical
==================================


0.15.1 - 26/06/2013
-------------------

* Move elevated constants to chevah.compat.


0.15.0 - 26/06/2013
-------------------

* Make ChevahTestCase.getHostname a static method.



0.14.0 - 04/06/2013
-------------------

* Fix TestCase.assertTempIsClean() and remove `silent` flag argument.
* Add TestCase.cleanTemporaryFolder().
* Add TestCase.patch() and TestCase.patchObject().
* Add mk.ascii and mk.TCPPort.
* Remove mk.makeMock() and move it as TestCase.Mock().


0.13.0 - 21/05/2013
-------------------

* Add helpers for deferred:
  successResultOf, failureResultOf and assertNoResult


0.12.1 - 21/05/2013
-------------------

* Rename ChevahCommonsFactory.md5checksum to ChevahCommonsFactory.md5.


0.12.0 - 19/05/2013
-------------------

* rename filesystem.LocalTestFilesystem,getFileContent to
  filesystem.LocalTestFilesyste.getFileLines.
* add filesystem.LocalTestFilesyste.getFileContent which returns full content.
* add mockup.ChevahCommonsFactory.md5checksum

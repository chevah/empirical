Release notes for chevah.empirical
==================================


0.16.5 - 08/11/2013
-------------------

* Fix fake reactor shutdown to set running flag.


0.16.4 - 06/11/2013
-------------------

* Use pseudo-random generator for mk.number().


0.16.3 - 27/09/2013
-------------------

* Fix retrieving test success state from full stack.


0.16.2 - 20/07/2013
-------------------

* Add tests for running deferred with chained callbacks.


0.16.1 - 18/07/2013
-------------------

* Fix previous bad release due to missing import line.


0.16.0 - 18/07/2013
-------------------

* Quick and dirty fix for resolving 2nd level deferrers.


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

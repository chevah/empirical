Release notes for chevah.empirical
==================================


0.20.1 - 17/12/2013
-------------------

* Rename decorators to conditionals.
* Allow a list of os names for onOSName conditional.


0.20.0 - 17/12/2013
-------------------

* Add decorators for skipping tests based on OS name or family.


0.19.0 - 12/12/2013
-------------------

* Check working folder for temporary files or folders.


0.18.2 - 10/12/2013
-------------------

* Fix listenPort() with Windows shutdown exception.


0.18.1 - 10/12/2013
-------------------

* Update listenPort() to support AIX.


0.18.0 - 09/12/2013
-------------------

* Move os accounts and group initialization into chevah.compat package.
* Call sys.exitfunc before exiting the test runner.
* Update build system to latest brink for independent paver.sh script.


0.17.5 - 03/12/2013
-------------------

* Re-release after merging 0.16.7.
* Update to latest compat and brink.


0.17.4 - 29/11/2013
-------------------

* Support temporary folders for Windows elevated accounts.


0.17.3 - 29/11/2013
-------------------

* Update LocalTestFilesystem to support chevah.server usage.


0.17.2 - 29/11/2013
-------------------

* Fix duplicate creation of temp folder on Windows.
* Fix build cleanup.
* Check that temporary folder does not exists when setting a new temp
  folder.


0.17.1 - 29/11/2013
-------------------

* Bad release.


0.17.0 - 29/11/2013
-------------------

* Add support for having separate temporary folders for each
  LocalTestFilesystem.


0.16.7 - 29/11/2013
-------------------

* Fix test timer for skipped tests.


0.16.6 - 08/11/2013
-------------------

* On reactor stop, restore reactor startup event.


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

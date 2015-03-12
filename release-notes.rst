Release notes for chevah.empirical
==================================


0.34.4 - 12/03/2015
-------------------

* Fix closing the HTTPServerContext when the persistent connection is
  already dropped.


0.34.3 - 11/03/2015
-------------------

* Fix assertIsEmpty.


0.34.2 - 10/03/2015
-------------------

* Fix HTTPServerContext stopping before making any connection.


0.34.1 - 10/03/2015
-------------------

* Fix HTTPServerContext close on Windows.


0.34.0 - 10/03/2015
-------------------

* Add strict checking for persistent connection by verifying client IP:PORT.


0.33.1 - 15/01/2015
-------------------

* Make zope.interface dependency optional.


0.33.0 - 15/01/2015
-------------------

* Make Twisted dependency optional.


0.32.2 - 18/12/2014
-------------------

* Add check for request method.
* Rename MockHTTPServer to HTTPServerContext and MockHTTPResponse to
  ResponseDefinition.


0.32.1 - 17/12/2014
-------------------

* Mocking HTTP server not uses HTTP/1.1
* Add check for persistent HTTP connection requests.


0.32.0 - 17/12/2014
-------------------

* Allow mocking HTTP response message/phrase beside the response code and
  a response length.


0.31.2 - 29/10/2014
-------------------

* Fix writeFileContent to always write file in UTF-8 mode.


0.31.1 - 29/10/2014
-------------------

* Merge with forgotten code from 0.30.2


0.31.0 - 29/10/2014
-------------------

* Add prefix and suffix option for creating folder in temp.
* Add helper method to replace content to existing file.


0.30.2 - 27/10/2014
-------------------

* Add support for Iterable in assertIsEmpty/assertIsNotEmpty.


0.30.1 - 04/10/2014
-------------------

* Fix socket error exception for OS X.


0.30.0 - 04/10/2014
-------------------

* Update support for OS X.


0.29.1 - 01/09/2014
-------------------

* Add skip message for skipped methods.


0.29.0 - 29/08/2014
-------------------

* Add support to call conditionals on classes.
* Add a generic skipOnCondition conditional.


0.28.4 - 27/08/2014
-------------------

* Make unique ID a singleton to make sure all code use the same ID.


0.28.3 - 22/08/2014
-------------------

* When show strings in assertion error use repr() to also see non
  printable characters.


0.28.2 - 23/07/2014
-------------------

* When threads are found in reactor, add a small wait to allow the thread to
  execute.


0.28.1 - 22/07/2014
-------------------

* Fix a bug in executeReactor in which it does not wait for thread from
  thread pool.


0.28.0 - 21/07/2014
-------------------

* Fix a bug in executeReactor in which it does not wait for delayed calls.


0.27.0 - 04/07/2014
-------------------

* Update for Solaris and latest chevah.compat.


0.26.4 - 29/05/2014
-------------------

* Force Unicode error message in assertFailureType.


0.26.3 - 29/05/2014
-------------------

* Fix error message encoding for assertions.


0.26.2 - 11/04/2014
-------------------

* Fix OLE/WMI error for missing WMI source on Windows 7 64bit. Use UTF-8
  encoded WMI query string.


0.26.0 - 03/04/2014
-------------------

* Remove assertExceptionID and assertExceptionData functions from
  EmpiricalTestCase.


0.25.1 - 04/03/2014
-------------------

* Fix cleanup of test_segments when they are not a directory and not a file,
  for example a link.


0.25.0 - 04/03/2014
-------------------

* Add conditional based on process capabilities.


0.24.1 - 03/03/2014
-------------------

* Add cached hostname to EmpiricalTestCase.


0.24.0 - 03/03/2014
-------------------

* Add support to call registered cleanup methods before tearDown.


0.23.2 - 13/02/2014
-------------------

* Show peak memory in Windows as integer.


0.23.1 - 13/02/2014
-------------------

* Fix getting memory usage on Windows.


0.23.0 - 12/02/2014
-------------------

* Record maximum memory used at end of test run.
* Add plugin to record memory usage for each test.


0.22.0 - 08/02/2014
-------------------

* Remove Twisted Web testing support.


0.21.0 - 07/02/2014
-------------------

* Enforce unicode ids for failures.


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

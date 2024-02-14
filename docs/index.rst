Welcome to the RCTab Functions' documentation!
==============================================

RCTab uses three function apps to collect data and enable/disable subscriptions.
They can be run locally or deployed to Azure.
Each function app requires different permissions on Azure and has different configuration options but they are deployed and triggered in the same way.
See the pages for the individual functions for more details.

.. toctree::
   :maxdepth: 2
   :caption: External Links
   :glob:
   :hidden:

   RCTab docs home <https://rctab.readthedocs.io/en/latest/>

.. toctree::
   :maxdepth: 2
   :caption: Contents
   :hidden:
   :glob:

   Home <self>
   content/setup
   content/controller
   content/status
   content/usage

.. autosummary::
   :toctree: _autosummary
   :recursive:
   :caption: Docstrings

   controller
   status
   usage
   utils

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

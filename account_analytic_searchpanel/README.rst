=====================
Analytic Search Panel
=====================

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-OCA%2Faccount--analytic-lightgray.png?logo=github
    :target: https://github.com/OCA/account-analytic/tree/18.0/account_analytic_searchpanel
    :alt: OCA/account-analytic
.. |badge4| image:: https://img.shields.io/badge/weblate-Translate%20me-F47D42.png
    :target: https://translation.odoo-community.org/projects/account-analytic-18-0/account-analytic-18-0-account_analytic_searchpanel
    :alt: Translate me on Weblate
.. |badge5| image:: https://img.shields.io/badge/runboat-Try%20me-875A7B.png
    :target: https://runboat.odoo-community.org/builds?repo=OCA/account-analytic&target_branch=18.0
    :alt: Try me on Runboat

|badge1| |badge2| |badge3| |badge4| |badge5|

This module improves analytic line navigation by adding an Analytic Plan
search panel to the analytic line search view.

Analytic plans can be configured as explorable or not explorable in that
search panel. The panel keeps the analytic plan hierarchy, using the plan
``parent_id``, so users can navigate the plan structure instead of a flat
list. This lets each database decide which analytic dimensions are
meaningful for navigation, without imposing that the panel always follows
the project dimension.

It also adds Analytic Plan and Analytic Account group-by entries, and
opens the standard analytic item actions grouped by Analytic Plan and then
Analytic Account.

**Table of contents**

.. contents::
   :local:

Usage
=====

1. Go to **Accounting > Configuration > Analytic Accounting > Analytic
   Plans**.
2. Enable **Show in Analytic Search Panel** on the dimensions that should
   be available for exploration.
3. Go to **Accounting > Analytic Accounting > Analytic Items**.
4. Use the left search panel to navigate the explorable analytic plan tree.
5. Review analytic lines grouped by Analytic Plan and Analytic Account.
6. Combine it with standard filters, groups, list, pivot, or graph views.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/OCA/account-analytic/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us smash it by providing a detailed and welcomed
feedback.

Credits
=======

Authors
-------

* Quim Rebull (Coopdevs)
* Odoo Community Association (OCA)

Contributors
------------

* Quim Rebull <quim@coopdevs.org>

Maintainers
-----------

This module is maintained by the OCA.

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

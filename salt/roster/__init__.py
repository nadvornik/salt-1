"""
Generate roster data, this data is used by non-minion devices which need to be
hit from the master rather than acting as an independent entity. This covers
hitting minions without zeromq in place via an ssh agent, and connecting to
systems that cannot or should not host a minion agent.
"""

import logging
import os

# Import salt libs
import salt.loader
import salt.syspaths
from salt.ext import six

log = logging.getLogger(__name__)


def get_roster_file(options):
    """
    Find respective roster file.

    :param options:
    :return:
    """
    template = None
    # The __disable_custom_roster is always True if Salt SSH Client comes
    # from Salt API. In that case no way to define own 'roster_file', instead
    # this file needs to be chosen from already validated rosters
    # (see /etc/salt/master config).
    if options.get("__disable_custom_roster") and options.get("roster_file"):
        roster = options.get("roster_file").strip("/")
        for roster_location in options.get("rosters"):
            r_file = os.path.join(roster_location, roster)
            if os.path.isfile(r_file):
                template = r_file
                break

    if not template:
        if options.get("roster_file"):
            template = options.get("roster_file")
        elif "config_dir" in options.get("__master_opts__", {}):
            template = os.path.join(options["__master_opts__"]["config_dir"], "roster")
        elif "config_dir" in options:
            template = os.path.join(options["config_dir"], "roster")
        else:
            template = os.path.join(salt.syspaths.CONFIG_DIR, "roster")

    if not os.path.isfile(template):
        raise OSError('Roster file "{}" not found'.format(template))

    if not os.access(template, os.R_OK):
        raise OSError('Access denied to roster "{}"'.format(template))

    return template


class Roster:
    """
    Used to manage a roster of minions allowing the master to become outwardly
    minion aware
    """

    def __init__(self, opts, backends="flat", context=None):
        self.opts = opts
        if isinstance(backends, list):
            self.backends = backends
        elif isinstance(backends, str):
            self.backends = backends.split(",")
        else:
            self.backends = backends
        if not backends:
            self.backends = ["flat"]
        utils = salt.loader.utils(self.opts)
        runner = salt.loader.runner(self.opts, utils=utils)
        self.rosters = salt.loader.roster(
            self.opts, runner=runner, utils=utils, context=context
        )

    def _gen_back(self):
        """
        Return a list of loaded roster backends
        """
        back = set()
        if self.backends:
            for backend in self.backends:
                fun = "{}.targets".format(backend)
                if fun in self.rosters:
                    back.add(backend)
            return back
        return sorted(back)

    def targets(self, tgt, tgt_type):
        """
        Return a dict of {'id': {'ipv4': <ipaddr>}} data sets to be used as
        targets given the passed tgt and tgt_type
        """
        targets = {}
        for back in self._gen_back():
            f_str = "{}.targets".format(back)
            if f_str not in self.rosters:
                continue
            try:
                targets.update(self.rosters[f_str](tgt, tgt_type))
            except salt.exceptions.SaltRenderError as exc:
                log.error("Unable to render roster file: %s", exc)
            except OSError as exc:
                log.error("Can't access roster for backend %s: %s", back, exc)

        log.debug("Matched minions: %s", targets)
        return targets

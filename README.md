# *OctopusMiner* GitHub Repository Miner

This repository contains a Python-based repository miner that pulls repositories from GitHub and examines the version history of all available branches to locate octopus merges. Octopus merges are merges that have more than two parents (i.e. they involve merges between more than two streams of commits). This miner is inspired by a [66-parent octopus merge](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=2cde51fbd0f3) (a "Cthulhu merge" according to Linus Torvalds) and the surrounding discussion regarding these types of merges in the Linux kernel
([The Biggest and Weirdest Commits in Linux Kernel Git History](https://www.destroyallsoftware.com/blog/2017/the-biggest-and-weirdest-commits-in-linux-kernel-git-history)).

Required packages for successfully using the miner include:
* `PyGithub` package required for walking git commit trees: [gitpython-developers/GitPython](https://github.com/gitpython-developers/GitPython)
  * Also available through `pip`: `pip install GitPython`
* `Progressbar 2` package required for displaying a simplified progress indicator: [WoLpH/python-progressbar](https://github.com/WoLpH/python-progressbar)
  * Also available through `pip`: `pip install progressbar2`

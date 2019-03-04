#!/usr/bin/python3
from urllib.request import urlopen
import re, json, csv, pickle
import time, datetime
import os, shutil
from collections import defaultdict
from git import Repo
import progressbar

REPO_LIMIT = 1000
REPOS = defaultdict(dict)
LOCAL_PATH = ""
ERROR_REPOS = []

def OctopusMiner():
    buildRepoList()
    examineBranchesAndCommits()
    reportTotals()
    writeReport()

def buildRepoList():
    GH_url = "https://api.github.com/repositories?since=1"
    while (len(REPOS) < REPO_LIMIT):
        (first, last, next) = processGitHubPage(GH_url)
        print('Processed repos {} to {} from {}'.format(first, last, GH_url))
        GH_url = next

def examineBranchesAndCommits():
    repo_names = list(REPOS.keys())
    for i in progressbar.progressbar(range(len(REPOS)), redirect_stdout=True):
        repo = repo_names[i]
        print("{}: Examining {}".format(i+1, repo))
        cloneRepo(repo, REPOS[repo]['url'])
        updateBranches(repo)
        for branch in REPOS[repo]['branches']:
            walkCommitHistory(repo, branch)
        removeRepo(repo)

def reportTotals():
    repos = len(REPOS) - len(ERROR_REPOS)
    branches = sum(len(REPOS[k]['branches']) for k in REPOS)
    commits = sum(REPOS[k]['commits'] for k in REPOS)
    octopus = sum(len(REPOS[k]['octopus_merges']) for k in REPOS)
    print("Repositories: {}, Branches: {}, Commits: {}, Octopus Merges: {}".format(repos, branches, commits, octopus))

def writeReport():
    path = buildPath('repos.csv')
    with open(path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_ALL)
        writer.writerow(['repo_name','url','branches','commits','octopus_merges'])
        for k,v in REPOS.items():
            writer.writerow([k, v['url'], stringify(v['branches']), v['commits'], stringify(v['octopus_merges'])])

def processGitHubPage(url):
    page = urlopen(url)
    header = dict(page.info())
    api_limit = header['X-RateLimit-Limit']
    api_remaining = header['X-RateLimit-Remaining']
    api_reset = header['X-RateLimit-Reset']
    api_next = header['Link'].partition("<")[2].partition(">")[0]
    json_data = json.loads(page.read())
    first = len(REPOS)
    for repo in json_data:
        REPOS[repo['full_name']] = {
            'url': repo['html_url'],
            'branches': [],
            'commits': 0,
            'octopus_merges': []
        }
        if len(REPOS) >= REPO_LIMIT:
            break
    if int(api_remaining) <= 0:
        resetGHRateLimit(api_remaining, api_limit, api_reset)
    return (first, len(REPOS), api_next)

def resetGHRateLimit(remaining, request_limit, reset_time):
    wait = int(float(reset_time) - time.time())
    wait_formatted = str(datetime.timedelta(seconds=wait))
    print("***GitHub API Rate Limit Reached ({}/{} requests)*** Waiting {} (HH:MM:SS)...".format(remaining, request_limit, wait_formatted))
    time.sleep(wait)

def walkCommitHistory(repo_name, branch_name):
    if repo_name in ERROR_REPOS:
        return
    path = buildPath(repo_name)
    try:
        repo = Repo(path)
    except:
        print("\tRepo setup error for '{}' at {}".format(repo_name, path))
        ERROR_REPOS.append(repo_name)
        return
    for commit in repo.iter_commits(branch_name):
        REPOS[repo_name]['commits'] += 1
        if len(commit.parents) > 2:
            REPOS[repo_name]['octopus_merges'].append(commit.hexsha)
    print("\tWalking branch '{}' => {} commits, {} octopus".format(branch_name, REPOS[repo_name]['commits'], len(REPOS[repo_name]['octopus_merges'])))

def buildPath(filename):
    return (LOCAL_PATH + filename) if LOCAL_PATH.endswith(os.path.sep) else (LOCAL_PATH + os.path.sep + filename)

def cloneRepo(repo_name, url):
    path = buildPath(repo_name)
    if os.path.isdir(path) and os.path.exists(path):
        return
    else:
        try:
            Repo.clone_from(url, path)
        except:
            print("\tRepo clone error for '{}' at {}".format(repo_name, url))
            ERROR_REPOS.append(repo_name)

def updateBranches(repo_name):
    if repo_name in ERROR_REPOS:
        return
    path = buildPath(repo_name)
    try:
        repo = Repo(path)
    except:
        print("\tRepo setup error for '{}' at {}".format(repo_name, path))
        ERROR_REPOS.append(repo_name)
        return
    for remote in repo.remotes.origin.fetch():
        REPOS[repo_name]['branches'].append(remote)

def removeRepo(repo_name):
    shutil.rmtree(buildPath(repo_name), ignore_errors=True)

def stringify(aList):
    return "[" + ','.join(map(str, aList)) + "]"

if __name__ == "__main__":
    OctopusMiner()

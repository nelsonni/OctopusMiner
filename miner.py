#!/usr/bin/python3
from urllib.request import urlopen
import re, json, csv, pickle
import time, datetime
import os, shutil, sys
from collections import defaultdict
from subprocess import Popen, PIPE
from git import Repo
import progressbar
#import fixer

REPO_LIMIT = 1000
REPOS = defaultdict(dict)
LOCAL_PATH = "."
ERROR_REPOS = []

def OctopusMiner():
    buildRepoFromTxt()
    examineBranchesAndCommits()
    reportTotals()
    writeReport()
    print(REPOS)

#def buildRepoList():   #remove for netty/netty instead of itterating list of 1000
#    GH_url = "https://api.github.com/repositories?since=1"
#    while (len(REPOS) < REPO_LIMIT):
#        (first, last, next) = processGitHubPage(GH_url)
#        print('Processed repos {} to {} from {}'.format(first, last, GH_url))
#        GH_url = next

#def processGitHubPage(url):               #build page
#    page = urlopen(url)
#    header = dict(page.info())
#    api_limit = header['X-RateLimit-Limit']
#    api_remaining = header['X-RateLimit-Remaining']
#    api_reset = header['X-RateLimit-Reset']
#    api_next = header['Link'].partition("<")[2].partition(">")[0]
#    json_data = json.loads(page.read())
#   first = len(REPOS)                                             #first is last?
#    for repo in json_data:
#        REPOS[repo['full_name']] = {
#            'url': repo['html_url'],
#            'language': processTopLang(repo['full_name']),
#            'branches': [],
#            'commits': 0,
#            'merges': [],
#            'octopus_merges': []
#        }
#        if len(REPOS) >= REPO_LIMIT:
#            break
#    if int(api_remaining) <= 0:
#        resetGHRateLimit(api_remaining, api_limit, api_reset)
#    return (first, len(REPOS), api_next)

def buildRepoFromTxt():
    txt = open("RepoList.txt", "r")
    for line in txt:
        targets = line.split(' ')
        print(targets[0] + "\n")
        print(targets[1] + "\n")

        processEntry(targets[1].rstrip(), targets[0])

    txt.close()

def processEntry(name, url):
    REPOS[ name ] = {
        'url': url,
        'language': "", #processTopLang(repo['full_name']),
        'branches': [],
        'commits': 0,
        'merges': [],
        'octopus_merges': []
    }

def examineBranchesAndCommits():   #Remove list and just replace with single netty/netty gh
    repo_names = list(REPOS.keys())
    for i in progressbar.progressbar(range(len(REPOS)), redirect_stdout=True):
    #for i in range(len(REPOS)):
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
    merges = sum(len(REPOS[k]['merges']) for k in REPOS)
    octopus = sum(len(REPOS[k]['octopus_merges']) for k in REPOS)
    print("Repositories: {}, Branches: {}, Commits: {}, Merges: {}, Octopus Merges: {}".format(repos, branches, commits, merges, octopus))
    languages = {i:[REPOS[k]['language'] for k in REPOS].count(i) for i in set([REPOS[k]['language'] for k in REPOS])}
    for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
        print("\t{}: {}".format(lang, count))

def writeReport():
    path = buildPath('repos.csv')
    with open(path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_ALL)
        writer.writerow(['repo_name','url','language','branches','commits','merges','octopus_merges'])
        for k,v in REPOS.items():
            writer.writerow([k, v['url'], v['language'], stringify(v['branches']), v['commits'], stringify(v['merges']), stringify(v['octopus_merges'])])



def resetGHRateLimit(remaining, request_limit, reset_time):    
    wait = int(float(reset_time) - time.time())
    wait_formatted = str(datetime.timedelta(seconds=wait))
    print("***GitHub API Rate Limit Reached ({}/{} requests)*** Waiting {} (HH:MM:SS)...".format(remaining, request_limit, wait_formatted))
    time.sleep(wait)

def processTopLang(repo_full_name):               #not sure maybe finds the most used language, not sure what json_data.keys are or os.path.sep
    lang_url = ("https://api.github.com/repos/" + repo_full_name + os.path.sep + "languages")
    print("repo url: {}, lang url: {}".format(repo_full_name, lang_url))
    page = urlopen(lang_url)
    json_data = json.loads(page.read())
    if len(json_data) > 0:
        return list(json_data.keys())[0]
    else:
        return ""

def walkCommitHistory(repo_name, branch_name):     #Walks through branch commits and finds parents of 2 and more
    if repo_name in ERROR_REPOS:
        return
    path = buildPath('scratch' + os.path.sep + repo_name)
    try:
        repo = Repo(path)                      # what is Repo func
    except:
        print("\tRepo setup error for '{}' at {}".format(repo_name, path))
        ERROR_REPOS.append(repo_name)
        return
    for commit in repo.iter_commits(branch_name):
        REPOS[repo_name]['commits'] += 1
        if len(commit.parents) == 2:
            REPOS[repo_name]['merges'].append(commit.hexsha)
        if len(commit.parents) > 2:
            REPOS[repo_name]['octopus_merges'].append(commit.hexsha)
    print("\tWalking branch '{}' => {} commits, {} merges, {} octopus".format(branch_name, REPOS[repo_name]['commits'], len(REPOS[repo_name]['merges']), len(REPOS[repo_name]['octopus_merges'])))

def buildPath(filename):
    return (LOCAL_PATH + filename) if LOCAL_PATH.endswith(os.path.sep) else (LOCAL_PATH + os.path.sep + filename)

def cloneRepo(repo_name, url):           #If the repo is already cloned then return but otherwise clone it and give an error if not successful
    path = buildPath('scratch' + os.path.sep + repo_name)
    print("Path: {}".format(path))
    if os.path.isdir(path) and os.path.exists(path):
        return
    else:
        try:        
            status = Repo.clone_from(url, path)
           
        except:
            print("\tRepo clone error for '{}' at {}".format(repo_name, url))
            ERROR_REPOS.append(repo_name)

def updateBranches(repo_name):           #Fills out ERROR_REPOS on fail or adds branches to REPOS list. Returns if already on ERROR_REPOS
    if repo_name in ERROR_REPOS:
        return
    path = buildPath('scratch' + os.path.sep + repo_name)   #clarify?
    try:
        repo = Repo(path)
    except:
        print("\tRepo setup error for '{}' at {}".format(repo_name, path))
        ERROR_REPOS.append(repo_name)
        return
    for remote in repo.remotes.origin.fetch():
        REPOS[repo_name]['branches'].append(remote)          #clarify?

def removeRepo(repo_name):               # removes repo from list
    shutil.rmtree(buildPath(repo_name), ignore_errors=True)

def stringify(aList):                    # Turns list into string
    return "[" + ','.join(map(str, aList)) + "]"

if __name__ == "__main__":
    OctopusMiner()

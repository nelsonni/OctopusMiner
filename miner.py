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
CONFLICTED_MERGES = []

def OctopusMiner():
    buildRepoFromTxt()
    examineBranchesAndCommits()
    examineAllMerges()
    print(CONFLICTED_MERGES)
    #reportTotals()
    #writeReport()


def examineAllMerges():

    count = 0
    for k in REPOS:
        count += 1
        path = buildPath('scratch' + os.path.sep + str(k))
        myRepo = Repo(path)
        for j in progressbar.progressbar(range(len(REPOS[k]['merges'])), redirect_stdout=True):
            print("In repo {}:{} working on merge {}".format(count, k, REPOS[k]['merges'][j]))
            commit = myRepo.commit(REPOS[k]['merges'][j])
            try:
                findConflicts(REPOS[k], commit, str(k))
            except:
                print("Something went wrong!")

    return 0

def findConflicts(repo, merge_commit, repo_name):
    conflictSets = []
    old_wd = os.getcwd()
    os.chdir("./scratch/"+ repo_name)
    
    if len(merge_commit.parents) < 2:
        return [] # not enough commits for a conflict to emerge
    else:
        try:
            firstCommitStr = merge_commit.parents[0].hexsha

            p = Popen(["git", "checkout", firstCommitStr], stdin=None, stdout=PIPE, stderr=PIPE)
            out, err = p.communicate()
            rc = p.returncode

            arguments = ["git", "merge"] + list(map(lambda c:c.hexsha, merge_commit.parents))
            p = Popen(arguments, stdin=None, stdout=PIPE, stderr=PIPE)
            out, err = p.communicate()
            rc = p.returncode

            filenames = findFilenames(out)
            for filename in filenames:
                conflictSets += getConflictSets(repo_name, filename, merge_commit)

            p = Popen(["git", "merge", "--abort"], stdin=None, stdout=PIPE, stderr=PIPE)
            out, err = p.communicate()
            rc = p.returncode
            return conflictSets

        finally:
            try:
                # Completely reset the working state after performing the merge
                p = Popen(["git", "clean", "-xdf"], stdin=None, stdout=PIPE, stderr=PIPE)
                out, err = p.communicate()
                rc = p.returncode
                p = Popen(["git", "reset", "--hard"], stdin=None, stdout=PIPE, stderr=PIPE)
                out, err = p.communicate()
                rc = p.returncode
                p = Popen(["git", "checkout", "."], stdin=None, stdout=PIPE, stderr=PIPE)
                out, err = p.communicate()
                rc = p.returncode
            finally:
                # Set the working directory back
                os.chdir(old_wd)
              

    return conflictSets

def getConflictSets(repo_name, filename, merge_commit):
    """
    Requires that the filename exist in the currently branch checked out through git.
    """
    path = os.getcwd() + "\\" + str(filename).split("b'")[-1][:-1].replace("/","\\")
    f = open(path, 'r')
    lines = f.readlines()
    f.close()
    print("Looking at conflict in %s" % path)

    isLeft, isRight = False, False
    leftLines, rightLines = [], []
    conflictSets = []
    leftSHA = None
    rightSHA = None

    for line in lines:
        if isRight:
            if ">>>>>>>" not in line:
                rightLines.append(line)
                
            else:
                rightSHA = line.split(">>>>>>>")[1].strip()
                isRight = False

                leftDict = {}
                leftDict['filename'] = path
                leftDict['SHA'] = leftSHA
                leftDict['lines'] = os.linesep.join(leftLines)

                rightDict = {}
                rightDict['filename'] = path
                rightDict['SHA'] = rightSHA
                rightDict['lines'] = os.linesep.join(rightLines)

                conflict = [leftDict, rightDict]
                conflictSets.append(conflict)

        if isLeft:
            if "=======" not in line:
                leftLines.append(line)
            else:
                isRight = True
                isLeft = False

        if "<<<<<<<" in line:
            isLeft = True
            leftSHA = line.split("<<<<<<<")[1].strip()
            if leftSHA == 'HEAD':
                leftSHA = str(merge_commit)
    
    arguments = ["git", "merge"] + list(map(lambda c:c.hexsha, merge_commit.parents))
    firstCommitStr = merge_commit.parents[0].hexsha
    tag = repo_name + " " + str(merge_commit) + " arguments: " + str(arguments) + " firstCommitStr: " + str(firstCommitStr) 
    if tag not in CONFLICTED_MERGES:
        CONFLICTED_MERGES.append(tag)
        print("Added {} to list from the {} repository".format(str(merge_commit), repo_name))

    return conflictSets

def findFilenames(output):
    conflict_filenames = []
    if "CONFLICT" in str(output):
        notification_lines = [x for x in output.splitlines() if str.encode("CONFLICT") in x]
        for line in notification_lines:
            if str.encode("Merge conflict in ") in line:
                conflict_filenames.append(line.split(str.encode('Merge conflict in '))[-1])
            elif str.encode("deleted in ") in line:
                conflict_filenames.append(line.split(str.encode(' deleted in '))[0].split(str.encode(': '))[-1])
            else:
                print("Unknown conflict filename detection: %s" % line)
                continue
    return conflict_filenames

#reading text file to build repo
def buildRepoFromTxt():
    txt = open("RepoList.txt", "r")
    for line in txt:
        targets = line.split(' ')
        print(targets[0] + "\n")
        print(targets[1] + "\n")

        processEntry(targets[1].rstrip(), targets[0])

    txt.close()

#Build entry object
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

def walkCommitHistory(repo_name, branch_name):     #Walks through branch commits and finds parents of 2 and more
    if repo_name in ERROR_REPOS:
        return
    path = buildPath('scratch' + os.path.sep + repo_name)
    try:
        repo = Repo(path)                      # Build repo objects
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

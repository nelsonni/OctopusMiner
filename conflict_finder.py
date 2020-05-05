import os, sys
from subprocess import Popen, PIPE
import fixer

def findConflicts(repo, merge_commit):
    conflictSets = []
    old_wd = os.getcwd()
    os.chdir(repo.working_dir)

    if len(merge_commit.parents) < 2:
        return [] # not enough commits for a conflict to emerge
    else:
        try:
            firstCommitStr = merge_commit.parents[0].hexsha

            p = Popen(["git", "checkout", firstCommitStr], stdin=None, stdout=PIPE, stderr=PIPE)
            out, err = p.communicate()
            rc = p.returncode

            arguments = ["git", "merge"] + map(lambda c:c.hexsha, merge_commit.parents)
            p = Popen(arguments, stdin=None, stdout=PIPE, stderr=PIPE)
            out, err = p.communicate()
            rc = p.returncode

            filenames = findFilenames(out)
            for filename in filenames:
                conflictSets += getConflictSets(repo, filename)

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
                fixer.headcheck(repo)

    return conflictSets

def getConflictSets(repo, filename):
    """
    Requires that the filename exist in the currently branch checked out through git.
    """
    path = repo.working_dir + '/' + filename
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
                leftSHA = str(repo.head.commit)

    return conflictSets

def findFilenames(output):
    conflict_filenames = []
    if "CONFLICT" in output:
        notification_lines = [x for x in output.splitlines() if "CONFLICT" in x]
        for line in notification_lines:
            if "Merge conflict in " in line:
                conflict_filenames.append(line.split('Merge conflict in ')[-1])
            elif "deleted in " in line:
                conflict_filenames.append(line.split(' deleted in ')[0].split(': ')[-1])
            else:
                print("Unknown conflict filename detection: %s" % line)
                continue
    return conflict_filenames
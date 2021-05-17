import os
import csv
from git import Repo
from git import IndexFile
import tempfile
import subprocess
import uuid
import shutil
from constants import Constant
from util import Util
from pathlib import Path

home = str(Path.home())
UUID = str(uuid.uuid4())


class GitService(object):
    def __init__(self, repo_name, git_url, repo_dir, branch_name, result_dir):
        # preparing
        # clone if not exists
        if not os.path.exists(repo_dir):
            print("Repo does not exist")
            if not git_url:
                print("But git_url is empty!")
                return
            else:
                git("clone", "--progress", "-v", git_url, repo_dir)
        # clear the result dir
        if os.path.exists(result_dir):
            shutil.rmtree(result_dir)
        if not os.path.exists(result_dir):
            os.makedirs(result_dir)
        self.repo = Repo(repo_dir)
        self.repo_dir = repo_dir
        self.git_url = git_url
        if not branch_name or len(branch_name.strip()) == 0 or not GitService.branch_exists(repo_dir, branch_name):
            branch_name = self.get_default_branch()
        self.branch = branch_name
        self.result_dir = result_dir

        print("Ready to process repo: %s at branch: %s" % (repo_name, branch_name))

    def get_default_branch(self):
        if not git_url:
            print("But git_url is empty!")
            return
        print("Fetching remote for default branch from: " + git_url + " (be patient)")

        lines = self.repo.git.remote('show', self.git_url)
        print(lines)
        lines = lines.split("\n")
        default_branch = ''
        for line in lines:
            if "HEAD branch" in line:
                default_branch = line.split(":")[1].strip()
                break
        if default_branch == "":
            default_branch = "master"
        print("Got default branch: " + default_branch)
        return default_branch

    def get_conflict_blobs(self, base_commit, ours_commit, theirs_commit):
        return IndexFile.from_tree(self.repo, base_commit, ours_commit, theirs_commit).unmerged_blobs()

    def get_file_content_at_commit(self, commit, file_path):
        try:
            content = self.repo.git.show('{}:{}'.format(commit.hexsha, file_path))
        except:
            content = None
        return content

    # given the commit as str
    def get_file_content_at_commit_str(self, commit, file_path):
        try:
            content = self.repo.git.show('{}:{}'.format(commit, file_path))
        except:
            content = None
        return content

    @staticmethod
    def branch_exists(repo_dir, branch_name):
        return_code = subprocess.call(["git", "rev-parse", "--verify", "--quiet", branch_name], cwd=repo_dir)
        if return_code == 1:
            return False
        else:
            return True

    @staticmethod
    def threeway_merge_file(base_file_path, ours_file_path, theirs_file_path):
        return subprocess.call(["git", "merge-file", "--diff3", ours_file_path, base_file_path, theirs_file_path])

    @staticmethod
    def threeway_merge_content(base_content, ours_content, theirs_content):
        # deleted in ours or theirs
        # !!! One difference need to be noticed: if ours/theirs content is None (both deleted)
        # !!! git merge-file result will be none, but still there will be conflicts in the file level
        # if ours_content == None or theirs_content == None:
        #     return None, 0
        base_temp = os.path.join(tempfile.gettempdir(), Constant.TEMP, UUID, Constant.BASE)
        ours_temp = os.path.join(tempfile.gettempdir(), Constant.TEMP, UUID, Constant.OURS)
        theirs_temp = os.path.join(tempfile.gettempdir(), Constant.TEMP, UUID, Constant.THEIRS)
        if os.path.exists(base_temp):
            os.remove(base_temp)
        if os.path.exists(ours_temp):
            os.remove(ours_temp)
        if os.path.exists(theirs_temp):
            os.remove(theirs_temp)
        Util.write_content(base_temp, base_content)
        Util.write_content(ours_temp, ours_content)
        Util.write_content(theirs_temp, theirs_content)
        num_conflicts = GitService.threeway_merge_file(base_temp, ours_temp, theirs_temp)
        git_merged_content = Util.read_content(ours_temp)
        # if and only if conflicts happen
        # if git_merged_content != None and num_conflicts > 0:
        #     return git_merged_content, num_conflicts
        # else:
        #     return None, 0
        return git_merged_content, num_conflicts

    def save_content_to_files(self, commit, relative_path, base_content, ours_content, theirs_content,
                              git_merged_content):
        base_path = os.path.join(self.result_dir, str(commit), Constant.BASE, relative_path)
        ours_path = os.path.join(self.result_dir, str(commit), Constant.OURS, relative_path)
        theirs_path = os.path.join(self.result_dir, str(commit), Constant.THEIRS, relative_path)
        git_merged_path = os.path.join(self.result_dir, str(commit), Constant.GIT, relative_path)
        Util.write_content(base_path, base_content)
        Util.write_content(ours_path, ours_content)
        Util.write_content(theirs_path, theirs_content)
        Util.write_content(git_merged_path, git_merged_content)
        # save the manual merged result
        manual_path = os.path.join(self.result_dir, str(commit), Constant.MANUAL, relative_path)
        manual_content = self.get_file_content_at_commit_str(str(commit), relative_path)
        if manual_content != None:
            Util.save_to_file(manual_path, manual_content)

    # a merge scenrio contains the three way file to merge, and the merged result by git and developer
    def collect_merge_scenrios(self, commit, unmerged_blobs):
        conflict_file_paths = []
        num_conflicts_at_commit = 0
        num_conflicts_per_file = []

        for relative_path in unmerged_blobs:
            # only care about java files now
            if relative_path.endswith(".java"):
                base_content = None
                ours_content = None
                theirs_content = None
                for (stage, blob) in unmerged_blobs[relative_path]:
                    if stage == 1:
                        base_content = blob.data_stream.read()
                    if stage == 2:
                        ours_content = blob.data_stream.read()
                    if stage == 3:
                        theirs_content = blob.data_stream.read()
                # save the git merged result
                git_merged_content, num_conflicts = self.threeway_merge_content(base_content, ours_content,
                                                                                theirs_content)
                # if one side content is None, merge result will be None, but not conflicts
                if num_conflicts > 0 and base_content != None and base_content.strip() != "":
                    conflict_file_paths.append(relative_path)
                    num_conflicts_at_commit += num_conflicts
                    num_conflicts_per_file.append(str(num_conflicts))
                    self.save_content_to_files(commit, relative_path, base_content, ours_content, theirs_content,
                                               git_merged_content)
        if len(conflict_file_paths) > 0:
            print("Commit: %s, #Unmerged_blobs: %s, #Conflict java files: %s, #Conflict blocks: %s" % (
                str(commit), len(unmerged_blobs),
                len(conflict_file_paths), num_conflicts_at_commit))
        return conflict_file_paths, num_conflicts_per_file

    def save_four_commits(self, summary_path, file_paths, num_conflicts_per_file, merge_commit, ours_commit,
                          theirs_commit, base_commit):
        line = []
        line.append(str(merge_commit))
        line.append(str(ours_commit))
        line.append(str(theirs_commit))
        line.append(str(base_commit[0]))
        line.append(str(len(file_paths)))
        line.append(','.join(num_conflicts_per_file))
        line.append(','.join(file_paths))

        with open(summary_path, 'a') as open_a:
            open_a.write('\n' + ';'.join(line))

    # find and collect merge scenarios from the git commit history of a repo
    def collect_from_repo(self, statistic_path):
        # preparing
        if os.path.exists(statistic_path):
            os.remove(statistic_path)

        if not os.path.isfile(statistic_path):
            open_w = open(statistic_path, "w")
            # header
            open_w.write(
                "merge commit; ours commit; theirs commit; base commit; #conflict java files; #conflict blocks; conflict java file paths")
            open_w.close()
        # 1. get all merge commits, 2 parents and merge_base
        for commit in self.repo.iter_commits(self.branch):
            if (len(commit.parents) >= 2):
                merge_commit = commit
                # on ours, merge theirs
                ours_commit = merge_commit.parents[0]
                theirs_commit = merge_commit.parents[1]
                base_commit = self.repo.merge_base(ours_commit, theirs_commit)
                # 2. get all unmerged files
                unmerged_blobs = self.get_conflict_blobs(base_commit, ours_commit, theirs_commit)
                # 3. re-merge java files with git, if conflicts, save the 3-way java files and manual merged result
                conflict_file_paths, num_conflicts_per_file = self.collect_merge_scenrios(merge_commit, unmerged_blobs)
                # 4. write related commit ids to the statistic file
                if len(conflict_file_paths) > 0:
                    self.save_four_commits(statistic_path, conflict_file_paths, num_conflicts_per_file, merge_commit,
                                           ours_commit,
                                           theirs_commit, base_commit)

    # collect merge scenarios given merge commits from a csv file
    def collect_from_csv(self, csv_file):
        if not os.path.exists(csv_file):
            print("%s does not exist!" % csv_file)
        processed_merge_commits = set()
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                merge_commit = row['merge_commit']
                if merge_commit not in processed_merge_commits:
                    processed_merge_commits.add(merge_commit)
                    ours_commit = row['parent1']
                    theirs_commit = row['parent2']
                    base_commit = row['merge_base']
                    unmerged_blobs = self.get_conflict_blobs(base_commit, ours_commit, theirs_commit)
                    conflict_file_paths, num_conflicts_per_file = self.collect_merge_scenrios(merge_commit,
                                                                                              unmerged_blobs)
        print("Number of Collected Merge Commits: %s" % (len(processed_merge_commits)))


def git(*args):
    return subprocess.check_call(['git'] + list(args))


if __name__ == "__main__":
    repo_name = "cassandra"
    # get the default branch
    branch_name = "trunk"
    # if the repo is not present in the repo_dir, it will be cloned, but better to clone in advance
    git_url = "https://github.com/apache/cassandra"
    repo_dir = os.path.join(home, "coding/data/repos", repo_name)
    result_dir = os.path.join(home, "coding/data/merges", repo_name)

    # Usage1: Collect Java files involved in merge scenarios that contain merge conflict(s) from the whole commit history
    statistic_path = result_dir + "/statistics.csv"
    git_service = GitService(repo_name, git_url, repo_dir, branch_name, result_dir)
    git_service.collect_from_repo(statistic_path)

    # Usage2: Collect Java files involved in merge scenarios that contain refactoring-related merge conflict(s) 
    # from the csv file generated by https://github.com/Symbolk/RefConfMiner.git
    # result_dir = os.path.join(home, "coding/data/repos", repo_name)
    # result_dir = os.path.join(home, "coding/data/ref_conflicts", repo_name)
    # csv_file = "merge_scenarios_involved_refactorings_test.csv"
    # csv_file = os.path.join(home, "coding/data/merge_scenarios_involved_refactorings", repo_name + ".csv")
    # git_service = GitService(repo_name, repo_dir, branch_name, result_dir)
    # git_service.collect_from_csv(csv_file)

import os
from git import Repo
from git import IndexFile
import tempfile
import subprocess
import uuid
import shutil
from constants import Constant
from util import Util

UUID = str(uuid.uuid4())


class GitService(object):
    def __init__(self, repo_dir, branch_name, result_dir):
        self.repo = Repo(repo_dir)
        self.branch = branch_name
        self.result_dir = result_dir

    def get_conflict_blobs(self, base_commit, ours_commit, theirs_commit):
        return IndexFile.from_tree(self.repo, base_commit, ours_commit, theirs_commit).unmerged_blobs()

    def get_file_content_at_commit(self, commit, file_path):
        try:
            content = self.repo.git.show('{}:{}'.format(commit.hexsha, file_path))
        except:
            content = None
        return content

    @staticmethod
    def threeway_merge_file(base_file_path, ours_file_path, theirs_file_path):
        return subprocess.call(["git", "merge-file", "--diff3", ours_file_path, base_file_path, theirs_file_path])

    @staticmethod
    def threeway_merge_content(base_content, ours_content, theirs_content):
        # deleted in ours or theirs
        if ours_content == None or theirs_content == None:
            return None
        base_temp = os.path.join(tempfile.gettempdir(), Constant.TEMP, UUID, Constant.BASE)
        ours_temp = os.path.join(tempfile.gettempdir(), Constant.TEMP, UUID, Constant.OURS)
        theirs_temp = os.path.join(tempfile.gettempdir(), Constant.TEMP, UUID, Constant.THEIRS)
        if os.path.exists(base_temp):
            os.remove(base_temp)
        if os.path.exists(ours_temp):
            os.remove(ours_temp)
        if os.path.exists(theirs_temp):
            os.remove(theirs_temp)
        Util.write_content(base_temp, base_content, write_none=True)
        Util.write_content(ours_temp, ours_content)
        Util.write_content(theirs_temp, theirs_content)
        GitService.threeway_merge_file(base_temp, ours_temp, theirs_temp)
        git_merged_content = Util.read_content(ours_temp)
        # if and only if conflicts happen
        if git_merged_content != None and b'<<<<<<<' in git_merged_content:
            return git_merged_content
        else:
            return None

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
        manual_content = self.get_file_content_at_commit(commit, relative_path)
        if manual_content != None:
            Util.save_to_file(manual_path, manual_content)

    # a merge scenrio contains the three way file to merge, and the merged result by git and developer
    def collect_merge_scenrios(self, commit, unmerged_blobs):
        conflict_file_paths = []
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
                git_merged_content = self.threeway_merge_content(base_content, ours_content, theirs_content)
                if git_merged_content != None:
                    conflict_file_paths.append(relative_path)
                    self.save_content_to_files(commit, relative_path, base_content, ours_content, theirs_content,
                                               git_merged_content)
        if len(conflict_file_paths) > 0:
            print("Commit: %s, #Unmerged_blobs: %s, #Conflict java files: %s" % (str(commit), len(unmerged_blobs),
                                                                                 len(conflict_file_paths)))
        return conflict_file_paths

    def save_four_commits(self, summary_path, file_paths, merge_commit, ours_commit, theirs_commit, base_commit):
        line = []
        line.append(str(merge_commit))
        line.append(str(ours_commit))
        line.append(str(theirs_commit))
        line.append(str(base_commit[0]))
        line.append(str(len(file_paths)))
        line.append(','.join(file_paths))

        with open(summary_path, 'a') as open_a:
            open_a.write('\n' + ';'.join(line))

    def collect(self, statistic_path):
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
                conflict_file_paths = self.collect_merge_scenrios(merge_commit, unmerged_blobs)
                # 4. write related commit ids to the statistic file
                if len(conflict_file_paths) > 0:
                    self.save_four_commits(statistic_path, conflict_file_paths, merge_commit, ours_commit,
                                           theirs_commit, base_commit)


def git(*args):
    return subprocess.check_call(['git'] + list(args))


if __name__ == "__main__":
    repo_name = "javaparser"
    branch_name = "master"
    git_url = "https://github.com/javaparser/javaparser.git"
    # Windows
    repo_dir = "D:\\github\\repos\\" + repo_name
    result_dir = "D:\\github\\merges\\" + repo_name
    # Linux
    # repo_dir = "/home/github/repos/" + repo_name
    # result_dir = "/home/github/merges" + repo_name
    # macOS
    # repo_dir = "/Users/name/github/repos/" + repo_name
    # result_dir = "/Users/name/github/merges" + repo_name

    statistic_path = result_dir + "/statistics.csv"

    # some preparation works
    # clone if not exists
    if not os.path.exists(repo_dir):
        git("clone", "--progress", "-v", git_url, repo_dir)
    if os.path.exists(result_dir):
        shutil.rmtree(result_dir)
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
    if os.path.exists(statistic_path):
        os.remove(statistic_path)

    if not os.path.isfile(statistic_path):
        open_w = open(statistic_path, "w")
        # header
        open_w.write(
            "merge commit; ours commit; theirs commit; base commit; #conflict java files; conflict java file paths")
        open_w.close()

    git_service = GitService(repo_dir, branch_name, result_dir)

    git_service.collect(statistic_path)

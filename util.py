import os
import ntpath

class Util(object):
    @staticmethod
    def save_to_file(file_path, contents):
        head, tail = ntpath.split(file_path)
        if not os.path.exists(head):
            os.makedirs(head)
        with open(file_path, 'w') as fw:
            fw.write(contents)

    @staticmethod
    def append_to_file(file_path, contents):
        head, tail = ntpath.split(file_path)
        if not os.path.exists(head):
            os.makedirs(head)
        with open(file_path, 'a') as fw:
            fw.write(contents)

if __name__ == "__main__":
    head, tail = ntpath.split("D:\\github\\results\\IntelliMerge\\3ceb2c9453198631adf0f49afc10ece85ccfc295\\base\\src/main/java/edu/pku/intellimerge/core/SemanticGraphBuilder.java")
    print(head)
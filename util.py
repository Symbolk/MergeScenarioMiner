import os
import ntpath
import codecs


class Util(object):
    @staticmethod
    def save_to_file(file_path, contents):
        head, tail = ntpath.split(file_path)
        if not os.path.exists(head):
            os.makedirs(head)
        with open(file_path, 'w', encoding='utf-8') as fw:
            fw.write(contents)

    @staticmethod
    def append_to_file(file_path, contents):
        head, tail = ntpath.split(file_path)
        if not os.path.exists(head):
            os.makedirs(head)
        with open(file_path, 'a') as fw:
            fw.write(contents)

    @staticmethod
    def write_content(path, content, mode='wb', encoding=None, write_none=True):
        # still generate the file even it is actually deleted
        if content == None:
            if write_none == True:
                content = b''
            else:
                return
        folder = os.path.dirname(path)
        if not os.path.exists(folder):
            os.makedirs(folder)
        with codecs.open(path, mode, encoding) as open_w:
            open_w.write(content)

    @staticmethod
    def read_content(path, mode='rb'):
        content = None
        if os.path.exists(path):
            with open(path, mode) as open_r:
                content = open_r.read()

        return content

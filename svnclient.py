import subprocess
import os
import re
import xml.etree.ElementTree
from lxml import etree

search_batch_size = 20

class Client:
    def __init__(self, cwd = os.getcwd(), stdout = subprocess.PIPE):
        self.cmd = ["svn"]
        self.log_content = None
        self.cwd = cwd
        self.stdout = stdout
        self.diff_cache = {}
        self.realpath = self.get_realtive_url()
        
    def get_realtive_url(self):
        log_cmd = self.cmd + ["info", "--xml"]
        data = subprocess.Popen(log_cmd, stdout = self.stdout, cwd = self.cwd).stdout.read()
        root = xml.etree.ElementTree.fromstring(data)
        entry_element = root.find("entry")
        if entry_element is not None:
            relative_url_element = entry_element.find("relative-url")
            if relative_url_element is not None:
                return relative_url_element.text
        return None  # 或者返回适当的默认值
    
    def get_info(self, *keywords):
        result = {}
        log_cmd = self.cmd + ["info", "--xml"]
        data = subprocess.Popen(log_cmd, stdout = self.stdout, cwd = self.cwd).stdout.read()
        root = etree.fromstring(data)
        if root is not None:
            for key in keywords:
                values = root.xpath(f'//{key}')
                value = None
                if values is not None and len(values) > 0:
                    value = values[0]
                if (value is not None) and (value.text is not None):
                    result[key] = value.text
        return result  # 或者返回适当的默认值
        
    def to_relative_url(self, path):
        return re.sub(self.realpath, '', path)

    def log(self, keywords=None, limit=None, decoding='utf8', every_commit_callback=None):
        log_cmd = self.cmd + ["log", "--xml"]

        if keywords and len(keywords) > 0:
            log_cmd += ["--search", " ".join(keywords)]

        start_revision = 0
        while True:
            batch_limit = limit if limit is None or limit <= search_batch_size else search_batch_size
            log_content_batch, start_revision = self._fetch_logs(log_cmd, batch_limit, start_revision, every_commit_callback)
            if not log_content_batch:
                break
            if limit:
                limit -= batch_limit
                if limit <= 0:
                    break

        if not every_commit_callback:
            return self.log_content

    def _fetch_logs(self, log_cmd, limit, start_revision, every_commit_callback):
        if self.log_content is None:
            self.log_content = []

        log_cmd += ["-l", str(limit), "-v"]

        if start_revision > 0:
            log_cmd += ["-r", "{}:HEAD".format(start_revision)]

        data = subprocess.Popen(log_cmd, stdout=self.stdout, cwd=self.cwd).stdout.read()
        root = xml.etree.ElementTree.fromstring(data)

        log_content_batch = []

        for e in root.iter('logentry'):
            entry_info = {x.tag: x.text for x in list(e)}

            log_entry = {
                'msg': entry_info.get('msg'),
                'author': entry_info.get('author'),
                'revision': int(e.get('revision')),
                'date': entry_info.get('date')
            }

            cl = []
            for f in e.iter('path'):
                action = f.attrib['action']
                path = f.text
                cl.append({"action": action, "path": path})

            log_entry['changelist'] = cl

            log_content_batch.append(log_entry)

            if every_commit_callback:
                every_commit_callback(log_entry)
            else:
                self.log_content.append(log_entry)

        if log_content_batch:
            last_revision = log_content_batch[-1]['revision']
        else:
            last_revision = start_revision

        return log_content_batch, last_revision
        
    def update_diff_cache(self, file_name, start_version, end_version, diff_content):
        if file_name not in self.diff_cache:
            self.diff_cache[file_name] = {} 
        if start_version not in self.diff_cache[file_name]:
            self.diff_cache[file_name][start_version] = {} 
        self.diff_cache[file_name][start_version][end_version] = diff_content

    def get_diff_content(self, file_name, start_version, end_version):
        if file_name in self.diff_cache and start_version in self.diff_cache[file_name] and end_version in self.diff_cache[file_name][start_version]:
            return self.diff_cache[file_name][start_version][end_version]
        else:
            return None

    def diff(self, start_version, end_version=None, file_name = None, decoding='utf8', cache=False, context_lines=10):
        if end_version is None:
            end_version = start_version
            start_version = end_version - 1
            
        if file_name:
            file_name = self.to_relative_url(file_name)
            
        if file_name.startswith("/"):
            file_name = file_name[1:]

        diff_cmd = self.cmd + ["diff", "-r", "{0}:{1}".format(start_version, end_version), f"-x -U{context_lines}", file_name]
        diff_content = None
        if cache:
            diff_content = self.get_diff_content(file_name, start_version, end_version)
            
        cached = True
        if not diff_content:
            cached = False
            diff_contents = []
            data = subprocess.Popen(diff_cmd, stdout=self.stdout, cwd=self.cwd).stdout.read()
            for b in data.split(b'\n'):
                str = None
                try:
                    str = bytes.decode(b, decoding)
                except:
                    str = bytes.decode(b)
                str = str.replace('\r', '')
                diff_contents.append(str)
                diff_content = "\n".join(diff_contents)

        if cache and not cached:
            self.update_diff_cache(file_name, start_version, end_version, diff_content)

        return diff_content
    
    def numstat(self, start_version, end_version = None, decoding = 'utf8', cache = False):
        stat = []
        file_name = None

        diff_content = self.diff(start_version, end_version, decoding, cache)
        for s in diff_content.split('\n'):
            if s.startswith('+++'):
                if file_name:    
                    stat.append((added, removed, file_name))
                added = 0
                removed = 0
                file_name = re.match(r'\+\+\+ (\S+)', s).group(1)
            elif s.startswith('---'):
                pass
            elif s.startswith('+'):
                added = added + 1
            elif s.startswith('-'):
                removed = removed + 1

        if file_name:
            stat.append((added, removed, file_name))
        
        return stat
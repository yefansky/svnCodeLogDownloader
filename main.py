﻿import svnclient
import subprocess
import re
import json

local_dir = "K:\\Sword8\\Source\\"
allowed_extensions = [".lua", ".c", ".cpp", ".h", ".lh", ".hpp"]
output_file_prefix = "svndata"        
search_count_limit = 10000
per_output_file_lines_limit = 100
encode_type = 'gbk'
diff_split_line_distance = 5
filter_keywords = []
code_type = 'c++'

# glboal define 
# ------------------
output_data = []
output_file = None
file_index = 1
# ------------------

client = svnclient.Client(cwd = local_dir, stdout = subprocess.PIPE)

def make_diff_pair_content(start_line_num, end_line_num, contents):
    orignal_content = []
    modify_content = []
    for line_num in range(start_line_num, end_line_num):
        record = contents[line_num]
        if record.startswith('-'):
            orignal_content.append(record[1:])
        elif record.startswith('+'):
            modify_content.append(record[1:])
        else:
            orignal_content.append(record[1:])
            modify_content.append(record[1:])
    return orignal_content, modify_content

def parse_diff(diff_content, block_sp_lines = diff_split_line_distance):
    content = []
    line_count = 0
    in_block = False
    no_modify_line_counter = 0
    modify_block_start_line = 0
    modify_black_end_line = 0
    diff_contents = []
    
    for line in diff_content.split('\n'):
        content.append(line)
        line_count = line_count + 1
        if line_count <= 4:
            continue
        if line.startswith("@@"):
            continue
        if line.startswith("+") or line.startswith("-"):
            no_modify_line_counter = 0
            if not in_block:
                modify_block_start_line = line_count - block_sp_lines
                if modify_block_start_line < 0:
                    modify_block_start_line = 0
            in_block = True
        elif in_block:
            no_modify_line_counter += 1
            if no_modify_line_counter >= block_sp_lines:
                modify_black_end_line = line_count
                in_block = False
                orignal_content, modify_content = make_diff_pair_content(modify_block_start_line, modify_black_end_line, content)                        
                diff_contents.append(["\n".join(orignal_content), "\n".join(modify_content)])
    
    if in_block:
        orignal_content, modify_content = make_diff_pair_content(modify_block_start_line, modify_black_end_line - 1, content)
        diff_contents.append(["\n".join(orignal_content), "\n".join(modify_content)])                    
    return diff_contents
    
def out_put_orignal(contnests):
    results = []
    line_count = 0
    for line in contnests.split('\n'):
        line_count = line_count + 1
        if line_count <= 4:
            continue
        if line.startswith("@@"):
            continue
        if line.startswith('+'):
            continue
        results.append(line[1:])
    return "".join(results)

def output_all_diff(diff_contents):
    result = ""
    for pairs in diff_contents:
        str = f"### 此段代码:\n ```{code_type}\n{pairs[0]}\n```\n### 被修改为:\n ```{code_type}\n{pairs[1]}\n```\n"
        result += str
    return result

def output_single_file(contents):
    global output_file, output_file_prefix, file_index
    output_file = open(f"{output_file_prefix}_{file_index}.txt" , "w", encoding="utf-8")
    file_index = file_index + 1
    str = "".join(contents)
    print(str)
    output_file.write(str)
    output_file.close()
    contents = []
            
def process_every_commit(commit):
    global output_data, file_index, output_file
    instruction_str = ""
    output_str = ""
    for file in commit['changelist']:
        action  = file['action']
        file_name = file['path']
        if action == "M" and any(file_name.lower().endswith(ext.lower()) for ext in allowed_extensions):
            diff_content = client.diff(commit['revision'], decoding = 'gbk',  context_lines=20, file_name = file_name)
            #orignal_content = out_put_orignal(diff_content)
            diff_pairs = parse_diff(diff_content)
            output_str = output_all_diff(diff_pairs)
            
        if len(output_str) > 0:
            markdown = f"## {commit['msg']}\n{output_str}`\n"
            output_data.append(markdown)
            
    if len(output_data) > per_output_file_lines_limit:
        output_single_file(output_data)
        output_data = []
    return

client.log(decoding = encode_type, keywords=filter_keywords, limit=search_count_limit, every_commit_callback = process_every_commit)
output_single_file(output_data)
import re
import sys
from pathlib import Path
import os

# 匹配中日文字符的正则表达式
pattern = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\u31f0-\u31ff]')

ignore_prefixes = ['MSG_']

def extract_strings_from_xdi(file_path, relative_path):
    """
    提取 .xdi 文件中索引表 2 的所有非空第二个字符串，并根据 ignore_prefixes 忽略特定开头的字符串。
    返回 (字符串列表, 行号信息列表)。
    根据 .xdi 格式:
    第一行: <索引表1数量> <索引表2数量> <字符串区大小（字单位）>
    索引表 1 条目: ##<hash> <pointer> <param1> <param2>\n<string>\n
    索引表 2 条目: #<hash> <offset1> <offset2>\n<string1>\n<string2>\n
    """
    extracted_strings = []
    string_info = []

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            # 读取并跳过头部行 (第 1 行)
            header_line = file.readline()
            if not header_line: # 处理空文件
                 print(f"警告: 文件 {file_path} 为空。")
                 return [], []

            current_line_num = 2 # 从第 2 行开始处理

            while True:
                current_pos = file.tell()
                line = file.readline()

                if not line: # 文件结束
                    break

                line = line.strip()

                if line.startswith("##"): # 索引表 1 条目标题行
                    # 跳过索引表 1 的字符串行
                    string_line = file.readline() # 读取并丢弃字符串行
                    if not string_line: # 文件意外结束
                         print(f"警告: 在读取 {file_path} 中索引表 1 标题后文件意外结束，位于行 {current_line_num}。")
                         break
                    current_line_num += 2 # 跳过标题行和字符串行

                elif line.startswith("#"): # 索引表 2 条目标题行
                    # 读取 string1 和 string2
                    string1_line = file.readline()
                    if not string1_line: # 文件意外结束
                         print(f"警告: 在读取 {file_path} 中索引表 2 标题后文件意外结束，位于行 {current_line_num}。")
                         break
                    string1_data = string1_line.strip()

                    string2_line_num = current_line_num + 2 # string2 所在的行号
                    string2_line = file.readline()
                    if not string2_line: # 文件意外结束
                         print(f"警告: 在读取 {file_path} 中索引表 2 的第一个字符串后文件意外结束，位于行 {current_line_num + 1}。")
                         break
                    string2_data = string2_line.strip()

                    # --- 新增逻辑：检查是否需要忽略 ---
                    should_ignore = False
                    if string2_data != "": # 只在字符串非空时检查忽略列表
                        for prefix in ignore_prefixes:
                            if string2_data.startswith(prefix):
                                should_ignore = True
                                break # 找到匹配项，停止检查其他忽略前缀

                    # 只在 string2 非空且不需要忽略时提取
                    if string2_data != "" and not should_ignore:
                        extracted_strings.append(string2_data)
                        string_info.append(f"{relative_path} {string2_line_num}")
                    # --- 结束新增逻辑 ---

                    current_line_num += 3 # 跳过标题行、string1 行和 string2 行

                else:
                    # 忽略非标题行和非条目标题行
                    current_line_num += 1 # 跳过当前被忽略的行


    except FileNotFoundError:
        print(f"错误: 未找到文件: {file_path}")
        return [], []
    except Exception as e:
        print(f"处理文件 {file_path} 时发生错误: {e}")
        return [], []

    return extracted_strings, string_info


def write_to_files(directory, all_lines, line_info):
    """将结果写入 all.txt 和 line.txt"""
    with open(os.path.join(directory, 'all.txt'), 'w', encoding='utf-8') as all_file, \
         open(os.path.join(directory, 'line.txt'), 'w', encoding='utf-8') as line_file:
        for line, info in zip(all_lines, line_info):
            all_file.write(line + '\n')
            line_file.write(info + '\n')

def write_back_to_source(directory):
    """根据 all.txt 和 line.txt 反向写入原文件"""
    try:
        with open(os.path.join(directory, 'all.txt'), 'r', encoding='utf-8') as all_file, \
             open(os.path.join(directory, 'line.txt'), 'r', encoding='utf-8') as line_file:
            all_lines = all_file.read().splitlines()
            line_info = line_file.read().splitlines()
    except FileNotFoundError:
        print("Error: all.txt or line.txt not found. Run extract mode first.")
        return

    # 按文件分组
    file_data = {}
    for content, info in zip(all_lines, line_info):
        file_path, line_num = info.rsplit(' ', 1)
        line_num = int(line_num)
        
        full_path = Path(directory) / file_path
        if full_path not in file_data:
            file_data[full_path] = []
        file_data[full_path].append((line_num, content))
    
    # 更新每个文件
    for file_path, changes in file_data.items():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 应用修改
            for line_num, content in changes:
                if 0 < line_num <= len(lines):
                    lines[line_num-1] = content + '\n'
            
            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            print(f"Updated {file_path} with {len(changes)} changes")
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")

def process_directory(directory, mode):
    all_lines = []
    line_info = []
    
    for path in Path(directory).rglob('*.xdi'):
        if path.is_file():
            relative_path = str(path.relative_to(directory))
            lines, info = extract_strings_from_xdi(path, relative_path)
            all_lines.extend(lines)
            line_info.extend(info)
    
    if mode == '-e':
        write_to_files(directory, all_lines, line_info)
        print(f"Extracted {len(all_lines)} lines to all.txt and line.txt")
    elif mode == '-w':
        write_back_to_source(directory)

def main():
    if len(sys.argv) != 3:
        print("Usage: python script.py [-e|-w] directory")
        print("  -e : Extract text to all.txt and line.txt")
        print("  -w : Write back changes from all.txt to source files")
        sys.exit(1)
    
    mode = sys.argv[1]
    directory = sys.argv[2]
    
    if mode not in ['-e', '-w']:
        print("Invalid mode. Use -e to extract or -w to write back.")
        sys.exit(1)
    
    if not Path(directory).is_dir():
        print(f"Directory not found: {directory}")
        sys.exit(1)
    
    process_directory(directory, mode)

if __name__ == "__main__":
    main()
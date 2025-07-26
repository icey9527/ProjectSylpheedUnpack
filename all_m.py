import re
import sys
from pathlib import Path
import os
import ast

# 匹配中日文字符的正则表达式
pattern = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\u31f0-\u31ff]')

ignore_prefixes = []#['MSG_']

def extract_strings_from_xdi(file_path, relative_path):
    """
    提取 .xdi 文件中索引表 2 的所有非空第二个字符串
    新增功能：将 _数字 结尾的字符串按数字顺序拼接，中间加\n
    """
    extracted_strings = []
    string_info = []
    group_dict = {}  # 格式: {前缀: {两位数: (内容, 行号)}}
    

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            header_line = file.readline()
            if not header_line:
                print(f"警告: 文件 {file_path} 为空。")
                return [], []

            current_line_num = 2

            while True:
                current_pos = file.tell()
                line = file.readline()

                if not line:
                    break

                line = line.strip()

                if line.startswith("##"):
                    file.readline()
                    current_line_num += 2

                elif line.startswith("#"):
                    string1_line = file.readline()
                    if not string1_line:
                        print(f"警告: 在读取 {file_path} 中索引表 2 标题后文件意外结束，位于行 {current_line_num}。")
                        break
                    string1_data = string1_line.strip()

                    string2_line_num = current_line_num + 2
                    string2_line = file.readline()
                    if not string2_line:
                        print(f"警告: 在读取 {file_path} 中索引表 2 的第一个字符串后文件意外结束，位于行 {current_line_num + 1}。")
                        break
                    string2_data = string2_line.strip()
                    num = None
                    if "_" in string1_data:
                        parts = string1_data.rsplit("_", 1)
                        suffix = parts[1]
                        
                        # 匹配 _数字 格式
                        if suffix.isdigit() and len(suffix) == 2:  # 两位数字
                            num = int(suffix)
                        # 匹配 _Lx 格式
                        elif suffix.startswith("L") and suffix[1:].isdigit():
                            num = int(suffix[1:])
                        
                        if num is not None:
                            prefix = parts[0]
                            if prefix not in group_dict:
                                group_dict[prefix] = {}
                            group_dict[prefix][num] = (string2_data, relative_path, string1_data)  # 新增存储原始string1_data
                            
                            current_line_num += 3
                            continue
                        else:
                            string_dict[string1_data] = string2_data
                    else:
                            string_dict[string1_data] = string2_data


        # 处理分组字符串
        for prefix in group_dict:
            if len(group_dict[prefix]) > 1:
                # 按数字排序后拼接
                sorted_nums = sorted(group_dict[prefix].keys())
                combined = group_dict[prefix][sorted_nums[0]][0]  # 第一个片段
                
                for num in sorted_nums[1:]:
                    if group_dict[prefix][num][0] != '':
                        combined += "\\n" + group_dict[prefix][num][0]  # 后续片段加\n

                if group_dict[prefix][sorted_nums[-1]][2] in string_dict:
                    if combined not in string_dict[group_dict[prefix][sorted_nums[-1]][2]].keys():
                        #print(group_dict[prefix][sorted_nums[-1]][2])
                        string_dict[group_dict[prefix][sorted_nums[-1]][2]][combined] = [relative_path]
                    else:
                        string_dict[group_dict[prefix][sorted_nums[-1]][2]][combined].append(relative_path)
                        
                else:
                    string_dict[group_dict[prefix][sorted_nums[-1]][2]] = {combined : [relative_path]}
            else:
                # 单独的分组字符串也保留
                num = next(iter(group_dict[prefix].keys()))
                string_dict[group_dict[prefix][sorted_nums[-1]][2]] = combined

    except FileNotFoundError:
        print(f"错误: 未找到文件: {file_path}")
        return [], []
    except Exception as e:
        print(f"处理文件 {file_path} 时发生错误: {e}")
        return [], []




def write_to_files(directory, str_dict):
    """将结果写入 all.txt 和 line.txt"""
    with open(os.path.join(directory, 'all.txt'), 'w', encoding='utf-8') as all_file, \
         open(os.path.join(directory, 'line.txt'), 'w', encoding='utf-8') as line_file:

         for id, string in str_dict.items():
            if type(string) is str:
                all_file.write(string + '\n')
                line_file.write(id + '\n')
         
         for id, string in str_dict.items():
            if type(string) is dict:
                for text, tab in string.items():
                    all_file.write(text + '\n')
                    if len(string.items()) > 1:
                        line_file.write(id + '#' +str(tab) + '\n')
                    else:
                        line_file.write(id + '\n')


def write_back_to_source(directory):
    """根据 all.txt 和 line.txt 反向写入原文件"""
    try:
        with open(os.path.join(directory, 'all.txt'), 'r', encoding='utf-8-sig') as all_file, \
             open(os.path.join(directory, 'line.txt'), 'r', encoding='utf-8') as line_file:
            all_lines = all_file.read().splitlines()
            line_info = line_file.read().splitlines()
    except FileNotFoundError:
        print("错误: 未找到 all.txt 或 line.txt。请先运行提取模式。")
        return

    if len(all_lines) != len(line_info):
        print(f"错误: all.txt ({len(all_lines)}行) 和 line.txt ({len(line_info)}行) 行数不匹配。")
        return

    # 第一步：扫描所有.xdi文件，建立ID到文件位置的映射
    id_locations = {}  # {ID: {file_path: line_number}}
    
    for path in Path(directory).rglob('*.xdi'):
        if not path.is_file():
            continue
            
        relative_path = str(path.relative_to(directory))
        
        try:
            with open(path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                line_num = 0
                
                while line_num < len(lines):
                    line = lines[line_num].strip()
                    
                    if line.startswith("##"):
                        line_num += 2
                    elif line.startswith("#"):
                        # 找到索引表
                        if line_num + 2 < len(lines):
                            id_line = lines[line_num + 1].strip()
                            if id_line:  # 确保ID不为空
                                if id_line not in id_locations:
                                    id_locations[id_line] = {}
                                # 记录文本所在行（ID后面的第二行）
                                id_locations[id_line][relative_path] = line_num + 3  # +3因为行号从1开始
                        line_num += 3
                    else:
                        line_num += 1
                        
        except Exception as e:
            print(f"扫描文件 {path} 时出错: {e}")
            continue

    # 第二步：处理要写回的内容
    updates = {}  # {file_path: {line_num: new_text}}
    
    # 定义统一的文本处理函数
    def process_text_for_id(id_str, text, target_files):
        """处理文本并更新到目标文件
        id_str: ID字符串
        text: 要写入的文本
        target_files: {file_path: line_num} 字典，指定要更新的文件
        """
        # 检查是否是分组ID且包含\n
        if '_' in id_str:
            parts = id_str.rsplit('_', 1)
            prefix = parts[0]
            suffix = parts[1]
            
            # 判断是否是分组ID
            group_ids = []  # 存储找到的分组ID
            
            if suffix.isdigit() and len(suffix) == 2:
                # _数字格式：从_00开始查找
                i = 0
                while True:
                    test_id = f"{prefix}_{str(i).zfill(2)}"
                    if test_id in id_locations:
                        group_ids.append(test_id)
                        i += 1
                    else:
                        break
                        
            elif suffix.startswith('L') and suffix[1:].isdigit():
                # _L数字格式：从_L1开始查找
                i = 1
                while True:
                    test_id = f"{prefix}_L{i}"
                    if test_id in id_locations:
                        group_ids.append(test_id)
                        i += 1
                    else:
                        break
            
            # 如果找到了分组ID，进行处理
            if group_ids:
                text_parts = text.split('\\n')
                
                # 检查文本行数
                if len(text_parts) > len(group_ids):
                    print(f"错误: ID {id_str} 的文本有 {len(text_parts)} 行，但只找到 {len(group_ids)} 个分组ID: {group_ids}")
                    return False
                
                # 为每个ID写入对应的文本
                for i, group_id in enumerate(group_ids):
                    if i < len(text_parts):
                        text_to_write = text_parts[i]
                    else:
                        text_to_write = ""  # 空字符填充
                        print(f"警告: ID {group_id} 使用空字符填充（文本只有 {len(text_parts)} 行）")
                    
                    # 只更新目标文件中的ID
                    if group_id in id_locations:
                        for file_path, line_num in id_locations[group_id].items():
                            # 检查是否在目标文件列表中
                            if file_path in target_files or not target_files:
                                full_path = Path(directory) / file_path
                                if full_path not in updates:
                                    updates[full_path] = {}
                                updates[full_path][line_num] = text_to_write
                
                return True
        
        # 非分组情况：直接更新
        for file_path, line_num in target_files.items():
            full_path = Path(directory) / file_path
            if full_path not in updates:
                updates[full_path] = {}
            updates[full_path][line_num] = text
        return True
    
    # 处理每一行
    for text, info in zip(all_lines, line_info):
        if '#' in info and info.strip().endswith(']'):
            # 处理重复ID的情况：ID#[路径列表]
            id_part, paths_part = info.split('#', 1)
            try:
                import ast
                # 使用安全的方式解析路径列表
                target_paths = ast.literal_eval(paths_part.strip())
            except (SyntaxError, ValueError) as e:
                print(f"解析路径列表失败: {paths_part} - {e}")
                continue
            
            # 构建目标文件字典
            target_files = {}
            if id_part in id_locations:
                for target_path in target_paths:
                    if target_path in id_locations[id_part]:
                        target_files[target_path] = id_locations[id_part][target_path]
            
            # 使用统一的处理函数
            if not process_text_for_id(id_part, text, target_files):
                return
                        
        else:
            # 普通ID情况
            id_str = info
            
            # 获取这个ID的所有位置
            if id_str in id_locations:
                target_files = id_locations[id_str]
                # 使用统一的处理函数
                if not process_text_for_id(id_str, text, target_files):
                    return

    # 第三步：执行文件更新
    for file_path, changes in updates.items():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 应用修改
            for line_num, new_text in changes.items():
                if 0 < line_num <= len(lines):
                    lines[line_num-1] = new_text + '\n'
                else:
                    print(f"警告: 行号 {line_num} 超出文件 {file_path} 的范围")
            
            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            print(f"更新 {file_path}，共 {len(changes)} 处修改")
            
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")

    print(f"写回完成，共更新 {len(updates)} 个文件")

def process_directory(directory, mode):

    if mode == '-e':
        global string_dict
        string_dict = {}
        for path in Path(directory).rglob('*.xdi'):
            if path.is_file():
                relative_path = str(path.relative_to(directory))
                extract_strings_from_xdi(path, relative_path)        
        write_to_files(directory, string_dict)
        print(f"Extracted {len(string_dict)} lines to all.txt and line.txt")
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
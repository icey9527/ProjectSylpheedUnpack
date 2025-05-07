# tbl_tool.py - 用于根据修正结构提取和构建 .tbl/.IXUD 文件的工具

import os
import sys
import struct
import argparse

def read_int(f, address=None):
    """从文件对象读取一个整数 (4 字节, 大端序)"""
    if address is not None:
        f.seek(address)
    data = f.read(4)
    if len(data) < 4:
        raise EOFError("读取整数时文件意外结束。")
    return int.from_bytes(data, 'big')

def write_int(f, value):
    """将一个整数 (4 字节, 大端序) 写入文件对象"""
    f.write(struct.pack('>I', value))

def extract_utf16be(f, address=None):
    """
    从文件对象读取一个以 null 结尾的 UTF-16BE 字符串。
    二进制文件中的指针是 UTF-16BE 字单位，因此 address 应该是字节偏移量。
    """
    if address is None or address < 0:
        # 处理无效或空指针，返回空字符串
        return ""

    original_pos = f.tell()
    try:
        f.seek(address)
        buffer = bytearray()
        while True:
            two_bytes = f.read(2)
            if len(two_bytes) < 2 or two_bytes == b'\x00\x00':
                break
            buffer.extend(two_bytes)
        return buffer.decode('utf-16be', errors='ignore')
    finally:
        # 恢复文件位置
        f.seek(original_pos)

def extract_tbl(input_bin, output_xdi):
    """
    根据修正结构从 .tbl 或 .IXUD 二进制文件提取数据到 .xdi 文本文件。
    """
    print(f"正在提取: {input_bin} -> {output_xdi}")
    try:
        with open(input_bin, 'rb') as f:
            # 读取文件头
            file_header = f.read(4)
            if file_header != b'IXUD':
                print(f"错误: {input_bin} 的文件头无效: {file_header}。应为 b'IXUD'。")
                return

            # 根据新结构计算各部分的起始位置
            file_header_size = 4
            idx1_count_pos = file_header_size
            idx1_count_size = 4
            idx1_start_pos = idx1_count_pos + idx1_count_size # 0x08
            idx1_entry_size = 16 # hash + pointer + param1 + param2 (4*4 字节)

            # 读取索引表 1 数量
            idx1_count = read_int(f, idx1_count_pos)

            # 读取索引表 1 条目
            idx1_entries = []
            f.seek(idx1_start_pos)
            for _ in range(idx1_count):
                hash_val = read_int(f)
                string_pointer_word = read_int(f) # 这个指针是字单位
                param1 = read_int(f)
                param2 = read_int(f)
                idx1_entries.append((hash_val, string_pointer_word, param1, param2))

            # 计算索引表 2 数量的位置
            idx2_count_pos = idx1_start_pos + idx1_count * idx1_entry_size

            # 读取索引表 2 数量
            idx2_count = read_int(f, idx2_count_pos)
            idx2_count_size = 4
            idx2_start_pos = idx2_count_pos + idx2_count_size

            # 读取索引表 2 条目
            idx2_entries = []
            idx2_entry_size = 12 # hash + pointer1 + pointer2 (3*4 字节)
            f.seek(idx2_start_pos)
            for _ in range(idx2_count):
                hash_val = read_int(f)
                pointer1_word = read_int(f) # 这个指针是字单位
                pointer2_word = read_int(f) # 这个指针是字单位
                idx2_entries.append((hash_val, pointer1_word, pointer2_word))

            # 读取字符区大小 (字单位) 并计算字符区起始位置 (字节单位)
            string_area_size_pos = idx2_start_pos + idx2_count * idx2_entry_size
            string_area_size_words = read_int(f, string_area_size_pos)
            string_area_start_bytes = string_area_size_pos + 4

            # 提取索引表 1 的字符串
            idx1_data = []
            for hash_val, string_pointer_word, param1, param2 in idx1_entries:
                 # 将字指针转换为相对于文件起始位置的字节偏移量
                string_byte_offset = string_area_start_bytes + string_pointer_word * 2
                string_data = extract_utf16be(f, string_byte_offset)
                idx1_data.append((hash_val, string_pointer_word, param1, param2, string_data))

            # 提取索引表 2 的字符串
            idx2_data = []
            for hash_val, pointer1_word, pointer2_word in idx2_entries:
                # 将字指针转换为相对于文件起始位置的字节偏移量
                string1_byte_offset = string_area_start_bytes + pointer1_word * 2
                string2_byte_offset = string_area_start_bytes + pointer2_word * 2

                string1_data = extract_utf16be(f, string1_byte_offset)
                string2_data = extract_utf16be(f, string2_byte_offset)
                idx2_data.append((hash_val, pointer1_word, pointer2_word, string1_data, string2_data))

        # 将数据写入 .xdi 文件
        with open(output_xdi, 'w', encoding='utf-8') as output_file:
            # 写入头部行: 索引表1数量 索引表2数量 字符串区大小（字单位）
            output_file.write(f"{idx1_count} {idx2_count} {string_area_size_words}\n")

            # 写入索引表 1 条目
            for hash_val, string_pointer_word, param1, param2, string_data in idx1_data:
                output_file.write(f"##{format(hash_val, '08X')} {format(string_pointer_word, '08X')} {format(param1, '08X')} {format(param2, '08X')}\n")
                output_file.write(f"{string_data}\n")

            # 写入索引表 2 条目
            for hash_val, pointer1_word, pointer2_word, string1_data, string2_data in idx2_data:
                output_file.write(f"#{format(hash_val, '08X')} {format(pointer1_word, '08X')} {format(pointer2_word, '08X')}\n")
                output_file.write(f"{string1_data}\n")
                output_file.write(f"{string2_data}\n")

    except FileNotFoundError:
        print(f"错误: 未找到输入文件: {input_bin}")
    except EOFError as e:
        print(f"读取文件 {input_bin} 时出错: {e}")
    except Exception as e:
        print(f"提取 {input_bin} 时发生未知错误: {e}")


def write_tbl(input_xdi, output_bin):
    """
    根据修正结构从 .xdi 文本文件构建 .tbl 或 .IXUD 二进制文件。
    """
    print(f"正在构建: {input_xdi} -> {output_bin}")
    idx1_entries_parsed = []
    idx2_entries_parsed = []
    idx1_count_header = 0
    idx2_count_header = 0
    string_area_size_words_header = 0

    try:
        with open(input_xdi, 'r', encoding='utf-8') as f:
            # 读取头部行: 索引表1数量 索引表2数量 字符串区大小（字单位）
            header_line = f.readline().strip()
            header_parts = header_line.split()
            if len(header_parts) == 3:
                try:
                    idx1_count_header = int(header_parts[0])
                    idx2_count_header = int(header_parts[1])
                    string_area_size_words_header = int(header_parts[2]) # 这个值仅供参考，实际大小会重新计算
                except ValueError:
                     print(f"错误: {input_xdi} 中的头部计数格式无效。")
                     return
            else:
                 print(f"错误: {input_xdi} 中的头部行格式无效。应为 '<索引表1数量> <索引表2数量> <字符串区大小（字单位）>'。")
                 return


            # 读取条目
            current_line = f.readline().strip()
            while current_line:
                if current_line.startswith("##"): # 索引表 1 条目
                    parts = current_line[2:].strip().split()
                    if len(parts) == 4: # hash, pointer, param1, param2
                        try:
                            hash_val = int(parts[0], 16)
                            # pointer_word_from_xdi = int(parts[1], 16) # 从 .xdi 读取的指针，构建时会重新计算
                            param1 = int(parts[2], 16)
                            param2 = int(parts[3], 16)
                            string_data = f.readline().strip()
                            idx1_entries_parsed.append((hash_val, param1, param2, string_data))
                        except ValueError:
                             print(f"错误: {input_xdi} 中索引表 1 条目数据格式无效: {current_line}")
                             return
                    else:
                         print(f"错误: 索引表 1 条目标题格式无效: {current_line}")
                         return
                elif current_line.startswith("#"): # 索引表 2 条目
                     parts = current_line[1:].strip().split()
                     if len(parts) == 3: # hash, offset1, offset2
                         try:
                             hash_val = int(parts[0], 16)
                             # offset1_word_from_xdi = int(parts[1], 16) # 从 .xdi 读取的偏移，构建时会重新计算
                             # offset2_word_from_xdi = int(parts[2], 16) # 从 .xdi 读取的偏移，构建时会重新计算
                             string1_data = f.readline().strip()
                             string2_data = f.readline().strip()
                             idx2_entries_parsed.append((hash_val, string1_data, string2_data))
                         except ValueError:
                             print(f"错误: {input_xdi} 中索引表 2 条目哈希或偏移格式无效: {current_line}")
                             return
                     else:
                         print(f"错误: 索引表 2 条目标题格式无效: {current_line}")
                         return
                else:
                    # 忽略空行或不符合预期格式的行
                    if current_line: # 只在非空行时警告
                         print(f"警告: 跳过 {input_xdi} 中无法识别的行: {current_line}")

                current_line = f.readline().strip()

        # 验证解析的条目数量是否与头部计数匹配 (可选，但推荐)
        if len(idx1_entries_parsed) != idx1_count_header:
            print(f"警告: 解析的索引表 1 条目数量 ({len(idx1_entries_parsed)}) 与头部计数 ({idx1_count_header}) 不匹配。使用解析数量。")
            # idx1_count_header = len(idx1_entries_parsed) # 不更新头部计数，因为头部计数是读取的原始值

        if len(idx2_entries_parsed) != idx2_count_header:
            print(f"警告: 解析的索引表 2 条目数量 ({len(idx2_entries_parsed)}) 与头部计数 ({idx2_count_header}) 不匹配。使用解析数量。")
            # idx2_count_header = len(idx2_entries_parsed) # 不更新头部计数


        # 构建字符串数据和偏移量映射
        strings_data = bytearray()
        # string_offsets 映射编码后的唯一字符串 (bytes) 到其在 strings_data 中的字节偏移量 (int)
        string_offsets = {}

        def add_string_to_data(s):
            """编码字符串，添加终止符，如果字符串是新的则添加到数据中，返回字节偏移量。"""
            encoded_string_with_term = s.encode('utf-16be') + b'\x00\x00'
            if encoded_string_with_term not in string_offsets:
                offset_bytes = len(strings_data)
                strings_data.extend(encoded_string_with_term)
                string_offsets[encoded_string_with_term] = offset_bytes
            return string_offsets[encoded_string_with_term]

        # 处理索引表 1 的字符串
        idx1_entries_binary = []
        for hash_val, param1, param2, string_data in idx1_entries_parsed:
            string_byte_offset = add_string_to_data(string_data)
            # 存储用于写入二进制的数据，将字节偏移量转换为字偏移量
            idx1_entries_binary.append((hash_val, string_byte_offset // 2, param1, param2))

        # 处理索引表 2 的字符串
        idx2_entries_binary = []
        for hash_val, string1_data, string2_data in idx2_entries_parsed:
            string1_byte_offset = add_string_to_data(string1_data)
            string2_byte_offset = add_string_to_data(string2_data)
             # 存储用于写入二进制的数据，将字节偏移量转换为字偏移量
            idx2_entries_binary.append((hash_val, string1_byte_offset // 2, string2_byte_offset // 2))

        # 计算二进制结构的偏移量和大小
        file_header_size = 4 # IXUD
        idx1_count_size = 4
        idx1_entry_size = 16 # hash + pointer + param1 + param2 (4*4 字节)
        # 使用解析到的条目数量来计算实际的表大小
        idx1_table_size = len(idx1_entries_binary) * idx1_entry_size
        idx2_count_size = 4
        idx2_entry_size = 12 # hash + pointer1 + pointer2 (3*4 字节)
        # 使用解析到的条目数量来计算实际的表大小
        idx2_table_size = len(idx2_entries_binary) * idx2_entry_size
        string_area_size_field_size = 4 # 字单位的大小字段
        string_area_size_bytes = len(strings_data)
        string_area_size_words = string_area_size_bytes // 2 # 大小字段存储字数

        # 计算起始位置 (从文件开头算起的字节偏移量)
        idx1_count_pos = file_header_size # 0x04
        idx1_start_pos = idx1_count_pos + idx1_count_size # 0x08
        idx2_count_pos = idx1_start_pos + idx1_table_size
        idx2_start_pos = idx2_count_pos + idx2_count_size
        string_area_size_pos = idx2_start_pos + idx2_table_size
        string_area_start_pos = string_area_size_pos + string_area_size_field_size


        # 构建二进制文件
        with open(output_bin, 'wb') as f:
            # 写入文件头
            f.write(b'IXUD')

            # 写入索引表 1 数量 (使用解析到的实际条目数量)
            write_int(f, len(idx1_entries_binary))

            # 写入索引表 1 条目
            f.seek(idx1_start_pos)
            for hash_val, string_pointer_word, param1, param2 in idx1_entries_binary:
                write_int(f, hash_val)
                write_int(f, string_pointer_word) # 写入字偏移量
                write_int(f, param1)
                write_int(f, param2)

            # 写入索引表 2 数量 (使用解析到的实际条目数量)
            f.seek(idx2_count_pos)
            write_int(f, len(idx2_entries_binary))

            # 写入索引表 2 条目
            f.seek(idx2_start_pos)
            for hash_val, pointer1_word, pointer2_word in idx2_entries_binary:
                write_int(f, hash_val)
                write_int(f, pointer1_word) # 写入字偏移量
                write_int(f, pointer2_word) # 写入字偏移量

            # 写入字符区大小 (字单位) (使用计算出的实际大小)
            f.seek(string_area_size_pos)
            write_int(f, string_area_size_words)

            # 写入字符区
            f.seek(string_area_start_pos)
            f.write(strings_data)

    except FileNotFoundError:
        print(f"错误: 未找到输入文件: {input_xdi}")
    except Exception as e:
        print(f"构建 {input_xdi} 时发生未知错误: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="用于根据修正结构提取和构建 .tbl/.IXUD 文件的工具。")

    # 创建一个互斥组，用于指定模式 (-e 或 -w)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-e", "--extract", action="store_true", help="模式: 提取 (二进制 -> .xdi)。")
    group.add_argument("-w", "--write", action="store_true", help="模式: 构建 (.xdi -> 二进制)。")

    # 添加位置参数，用于输入和输出路径
    parser.add_argument("input_path", help="输入文件 (.tbl/.IXUD 用于 -e, .xdi 用于 -w) 或包含它们的目录。")
    parser.add_argument("output_path", help="输出文件 (.xdi 用于 -e, .tbl/.IXUD 用于 -w) 或输出文件的目录。")

    args = parser.parse_args()

    input_path = args.input_path
    output_path = args.output_path

    # 根据解析到的模式执行相应的操作
    if args.extract: # 提取模式
        if os.path.isdir(input_path):
            if not os.path.exists(output_path):
                 os.makedirs(output_path, exist_ok=True)
            for root, dirs, files in os.walk(input_path):
                rel_path = os.path.relpath(root, input_path)
                output_root = os.path.join(output_path, rel_path)
                os.makedirs(output_root, exist_ok=True)
                for file in files:
                    if file.endswith('.tbl') or file.endswith('.IXUD'):
                        input_bin_path = os.path.join(root, file)
                        output_xdi_path = os.path.join(output_root, f'{os.path.splitext(file)[0]}.xdi')
                        extract_tbl(input_bin_path, output_xdi_path)
        elif os.path.isfile(input_path) and (input_path.endswith('.tbl') or input_path.endswith('.IXUD')):
            if os.path.isdir(output_path):
                 # 输出到输出目录下的文件，使用 .xdi 扩展名
                 output_xdi_path = os.path.join(output_path, f'{os.path.splitext(os.path.basename(input_path))[0]}.xdi')
            else:
                 # 输出直接到指定的文件路径
                 output_xdi_path = output_path
                 output_dir = os.path.dirname(output_xdi_path)
                 if output_dir and not os.path.exists(output_dir):
                     os.makedirs(output_dir, exist_ok=True)
            extract_tbl(input_path, output_xdi_path)
        else:
            print("提取模式输入路径无效。请提供一个 .tbl 或 .IXUD 文件或包含它们的目录。")

    elif args.write: # 构建模式
        if os.path.isdir(input_path):
            if not os.path.exists(output_path):
                 os.makedirs(output_path, exist_ok=True)
            for root, dirs, files in os.walk(input_path):
                rel_path = os.path.relpath(root, input_path)
                output_root = os.path.join(output_path, rel_path)
                os.makedirs(output_root, exist_ok=True)
                for file in files:
                    if file.endswith('.xdi'):
                        input_xdi_path = os.path.join(root, file)
                        # 根据输入文件名约定确定输出扩展名 (例如，以 $ 开头的文件对应 IXUD)
                        base_name = os.path.splitext(file)[0]
                        suffix = 'IXUD' if base_name.startswith('$') else 'tbl'
                        output_bin_path = os.path.join(output_root, f'{base_name}.{suffix}')
                        write_tbl(input_xdi_path, output_bin_path)
        elif os.path.isfile(input_path) and input_path.endswith('.xdi'):
            if os.path.isdir(output_path):
                 # 输出到输出目录下的文件，使用确定的扩展名
                 base_name = os.path.splitext(os.path.basename(input_path))[0]
                 suffix = 'IXUD' if base_name.startswith('$') else 'tbl'
                 output_bin_path = os.path.join(output_path, f'{base_name}.{suffix}')
            else:
                 # 输出直接到指定的文件路径
                 output_bin_path = output_path
                 output_dir = os.path.dirname(output_bin_path)
                 if output_dir and not os.path.exists(output_dir):
                     os.makedirs(output_dir, exist_ok=True)
            write_tbl(input_path, output_bin_path)
        else:
            print("构建模式输入路径无效。请提供一个 .xdi 文件或包含它们的目录。")
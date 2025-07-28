import os
import re
import json
import argparse

def parse_blocks(file_content):
    blocks = []
    pattern = re.compile(r'(@[0-9a-fA-F]+)(.*?)(?=\n@|\Z)', re.DOTALL)
    for match in pattern.finditer(file_content):
        key = match.group(1)
        block = match.group(2)
        if '#c5684308' not in block:
            continue
        lines = block.splitlines()
        text_lines = []
        text_line_count = 0
        for i, line in enumerate(lines):
            if '#c5684308' in line:
                try:
                    text_line_count = int(lines[i+3].replace('+','').strip())
                    text_lines = lines[i+4:i+4+text_line_count]
                except Exception as e:
                    print(f"解析错误: {e}")
                break
        original = '\\n'.join(text_lines)
        blocks.append({
            "key": key,
            "original": original,
            "translation": "",
            "stage": 0
        })
    return blocks

def batch_parse_folder(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    for filename in os.listdir(input_folder):
        if not filename.endswith('.txt'):
            continue
        with open(os.path.join(input_folder, filename), 'r', encoding='utf-8') as f:
            content = f.read()
        blocks = parse_blocks(content)
        outname = os.path.splitext(filename)[0] + '.json'
        with open(os.path.join(output_folder, outname), 'w', encoding='utf-8') as f:
            json.dump(blocks, f, ensure_ascii=False, indent=2)
        print(f"提取完成: {filename} -> {outname}")



def write_back_txt(original_txt_path, json_path, output_txt_path):
    with open(original_txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    with open(json_path, 'r', encoding='utf-8') as f:
        translations = {item['key']: item for item in json.load(f)}

    def replace_block(match):
        key = match.group(1)
        block = match.group(2)
        if key not in translations:
            return key + block
        trans = translations[key]
        lines = block.splitlines()
        for i, line in enumerate(lines):
            if '#c5684308' in line:
                text_line_idx = i + 3
                if text_line_idx >= len(lines):
                    return key + block  # 防止越界
                try:
                    old_count = int(lines[text_line_idx].replace('+','').strip())
                except:
                    return key + block
                # 取译文，没有就用原文
                translation_lines = trans['translation'].replace('\\n', '\n').split('\n') if trans['translation'].strip() else trans['original'].replace('\\n', '\n').split('\n')
                # 更新行数
                lines[text_line_idx] = '+{:8d}'.format(len(translation_lines))
                # 拼接新内容
                before = lines[:text_line_idx+1]
                after = lines[text_line_idx+1+old_count:]
                lines = before + translation_lines + after
                break
        return key +  '\n'.join(lines)

    pattern = re.compile(r'(@[0-9a-fA-F]+)(.*?)(?=\n@|\Z)', re.DOTALL)
    new_content = pattern.sub(replace_block, content)
    with open(output_txt_path, 'w', encoding='utf-8') as f:
        f.write(new_content)



def batch_write_back(input_folder, json_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    for filename in os.listdir(input_folder):
        if not filename.endswith('.txt'):
            continue
        txt_path = os.path.join(input_folder, filename)
        json_path = os.path.join(json_folder, os.path.splitext(filename)[0] + '.json')
        out_path = os.path.join(output_folder, filename)
        if not os.path.exists(json_path):
            print(f"未找到对应json: {json_path}")
            continue
        write_back_txt(txt_path, json_path, out_path)
        print(f"写回完成: {filename}")

def main():
    parser = argparse.ArgumentParser(description="批量提取/写回文本脚本")
    parser.add_argument('-e', action='store_true', help='提取模式')
    parser.add_argument('-w', action='store_true', help='写回模式')
    parser.add_argument('folders', nargs='+', help='文件夹参数')
    args = parser.parse_args()

    if args.e:
        if len(args.folders) != 2:
            print("提取模式需要2个文件夹参数：输入txt文件夹 输出json文件夹")
            return
        batch_parse_folder(args.folders[0], args.folders[1])
    elif args.w:
        if len(args.folders) != 3:
            print("写回模式需要3个文件夹参数：输入txt文件夹 输入json文件夹 输出txt文件夹")
            return
        batch_write_back(args.folders[0], args.folders[1], args.folders[2])
    else:
        print("请指定-e(提取)或-w(写回)模式")

if __name__ == '__main__':
    main()

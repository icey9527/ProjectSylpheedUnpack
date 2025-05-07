import os
import sys
import zlib
import struct
from pathlib import Path

def make_file_id(lp_string):
    if lp_string[:1] == "$":
        return int(os.path.splitext(lp_string[1:])[0],16)

    # 获取字符串长度并加1
    v1 = len(lp_string) + 1
    
    # 复制并转换字符串为小写
    string1 = lp_string.lower()
    
    # 初始化变量
    v2 = 0
    v3 = 0
    
    # 遍历字符串
    for i in range(len(string1)):
        v6 = ord(string1[i])
        
        # 累加字符的 ASCII 值
        v3 += v6
        
        # 计算 v2
        v2 = (v6 + (v2 << 8)) & 0xFFFFFFFF  # 保持 v2 为 32 位无符号整数
        
        # 检查 v2 是否需要取模
        if (v2 & 0xFF800000) != 0:
            v2 %= 0xFFF9D7
    
    # 返回最终的文件 ID
    return (v2 | (v3 << 24)) & 0xFFFFFFFF

def compress_custom(file):
    with open(file, 'rb') as f:
        data = f.read()
        f.close()

    compress_data = zlib.compress(data, level=8, wbits=-15)
    z1 = bytearray()
    z1.extend(b'Z1')
    z1.extend(struct.pack('>I', len(data)))
    adler32 = struct.pack('>I', zlib.adler32(data))
    z1.extend(adler32)
    z1.extend(b'\x78\xDA')
    z1.extend(compress_data)
    z1.extend(adler32)
    return  z1

def write_int(f, value, byteorder='big'):
    f.write(value.to_bytes(4, byteorder))

def get_all_files(directory):
    file_list = {}
    for path in Path(directory).rglob('*'):
        if path.is_file():
            filename = str(path.relative_to(directory))
            if filename != 'Non-compression-list.txt':
                file_list[make_file_id(filename)] = filename
    return file_list

def pack(input_dir, output_file):

    file_list = get_all_files(input_dir)
    data = bytearray()
    log = []

    with open(output_file, 'wb') as f:
        f.write(b'IPFB')
        write_int(f, len(file_list))
        write_int(f,0x800)
        write_int(f,0x10000000)
        
        idx = 0
        for hash, file in sorted(file_list.items()):
            print(file)
            if  file in 不压缩:
                compress_data = open(os.path.join(input_dir, file), 'rb').read()
            else:
                compress_data =  compress_custom(os.path.join(input_dir, file))
            
            offset = len(data)
            size =len (compress_data)
            
            data.extend(compress_data)

            write_int(f, hash)
            write_int(f, offset)
            write_int(f, size)
            log.append((file, hash, offset, size))

            idx += 1
            if idx == len(file_list):
                break

            data.extend( b'\x00' * ((2048 - (len(data) % 2048)) % 2048))

    with open(f'{os.path.splitext(output_file)[0]}.p00', 'wb') as f:
        f.write(data)

    with open('pack.log', 'w') as f:
        for file, hash, offset, size in log:
            f.write(f"{format(hash, 'X')} {format(offset, 'X')} {format(size, 'X')} {file}\n")

        


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: <输入目录> <输出文件>")
    else:
        不压缩 = ['HGRGE00.TTF','$1D93DAF0.ttcf']
        if os.path.exists(os.path.join(sys.argv[1], 'Non-compression-list.txt')):
            with open(os.path.join(sys.argv[1], 'Non-compression-list.txt'), 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        不压缩.append(line)

        pack(sys.argv[1], sys.argv[2])
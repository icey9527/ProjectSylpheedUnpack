import os
import sys
import zlib

def read_prefix(buf, filename):
    if filename[:1] != "$":
        full_filename = os.path.join(outdir, filename)
    else:
        try:
            s = buf[:4].decode('utf-8', errors='ignore').replace('\x00', '')

            if len(s) >= 3 and s.isalnum():
                new_filename = f'{filename}.{s}'
            else:
                new_filename = filename
            full_filename = os.path.join(outdir, new_filename)
        except:
            full_filename = os.path.join(outdir, filename)
    os.makedirs(os.path.dirname(full_filename), exist_ok=True)
    return full_filename

def make_file_id(lp_string):
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

def uncompressCustom(source):
    try:
        # 使用wbits=-15来忽略zlib头
        return zlib.decompress(source, -15)
    except zlib.error as e:
        print(f"Error decompressing data: {e}")
        return None
    
def read_int(f, address=None):
    if address is not None:
        f.seek(address)
    return int.from_bytes(f.read(4), 'big')

def hex_print(*args, **kwargs):
    hex_args = [f"0x{int(x):X}" if isinstance(x, (int, float)) else str(x) for x in args]
    print(*hex_args, **kwargs)

def read_null_terminated_string(file, encoding='shift-jis'):
    """读取NULL结尾的字符串，并将内部的换行符替换为\\n注释"""
    chars = []
    while True:
        char = file.read(1)
        if char == b'\x00' or not char:  # 遇到NULL或文件结束
            break
        # 将换行符(0x0A)转换为\\n注释
        if char == b'\x0a':
            chars.append(b'\\n')  # 转义为可见形式
        else:
            chars.append(char)
    return b''.join(chars).decode(encoding)

def unpack(input):
    未压缩 = []
    log= []

    with open(input, 'rb') as f:
        IdxQ = read_int(f,4)
        f.seek(0x10)
        idx = []
        for i in range(IdxQ):
            hash = read_int(f)
            offset = read_int(f)

            size = read_int(f)
            if hash == 0:
                print(i)
                break
            
            idx.append((hash, offset, size))
        f.close()
    
    for hash, offset, size in idx:
        # 计算对应的.p0X文件名和偏移量
        fnum = offset >> 28  # 右移27位，对应C代码的 >>0x1B
        foff = offset & 0xFFFFFFF  # 计算实际偏移

        p_file = f"{os.path.splitext(input)[0]}.p{fnum:02d}"  # 生成文件名如.p00, .p01

        try:
            with open(p_file, 'rb') as f:
                f.seek(foff)
                p_data = f.read(size)
        except FileNotFoundError:
            print(f"Error: {p_file} not found, skipping entry.")
            continue

        if hash in name_dict:
            filename = name_dict[hash]
        else:
            filename = f"${hex(hash)[2:].upper()}"

        log.append((filename, hash, offset, size))

        if p_data[:2] != b'Z1':
            未压缩.append(filename)
        else:
            p_data = uncompressCustom(p_data[12:])

        print(filename)


        filename = read_prefix(p_data, filename)
        with open(filename, 'wb') as f:
                f.write(p_data)
        f.close()

        if len(未压缩) > 0:
            with open(os.path.join(outdir, 'Non-compression-list.txt'), 'w') as f:
                for i in 未压缩:
                    f.write(f'{i}\n')

        with open('unpack.log', 'w') as f:
            for file, hash, offset, size in log:
                f.write(f"{format(hash, 'X')} {format(offset, 'X')} {format(size, 'X')} {file}\n")



            


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: <输入文件/目录> <输出目录>")
    else:
        os.makedirs(sys.argv[2], exist_ok=True)
        name_dict = {}
        with open('list.txt', 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                cleaned_line = line.strip().rsplit('+', 1)[-1]
                if cleaned_line: 
                    name_dict[make_file_id(cleaned_line)] = cleaned_line
        outdir = sys.argv[2]
        unpack(sys.argv[1])
 
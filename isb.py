#!/usr/bin/env python3
"""
ISB 文件编解码器 - 完整的 Python 实现
支持 ISB 二进制文件的编码和解码
"""

import sys
import struct
import os
from typing import List, Tuple, Optional, Dict, Union
from pathlib import Path
import argparse


class ISBCodec:
    """ISB文件编解码器"""
    
    # 常量定义
    MARKER_NUMBER = 0x40403
    MARKER_TEXT = 0x40400
    KEY_THRESHOLD = 0x3000001
    MAX_TEXT_LENGTH = 0x3f *2
    
    @staticmethod
    def ror3(x: int) -> int:
        """向右旋转3位（32位整数）"""
        x &= 0xFFFFFFFF
        return ((x >> 3) | (x << 29)) & 0xFFFFFFFF
    
    @staticmethod
    def rol3(x: int) -> int:
        """向左旋转3位（32位整数）- ror3的逆运算"""
        x &= 0xFFFFFFFF
        return ((x << 3) | (x >> 29)) & 0xFFFFFFFF
    
    @staticmethod
    def decode(data: List[int], length: int, key: int) -> None:
        """使用ROR3和XOR操作原地解码数据"""
        for i in range(length):
            data[i] = ISBCodec.ror3(data[i]) ^ key
            data[i] &= 0xFFFFFFFF
    
    @staticmethod
    def encode(data: List[int], length: int, key: int) -> None:
        """使用ROL3和XOR操作原地编码数据"""
        for i in range(length):
            data[i] = ISBCodec.rol3(data[i] ^ key)
            data[i] &= 0xFFFFFFFF
    
    @staticmethod
    def calculate_word_count(length: int) -> int:
        """计算需要的32位字数量"""
        # 基本字数
        word_count = (length + 3) // 4
        return word_count
    
    @staticmethod
    def read_file_to_buffer(file_path: Union[str, Path]) -> Tuple[bytes, List[int]]:
        """读取文件并转换为32位整数数组"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        file_data = file_path.read_bytes()
        
        if not file_data:
            raise ValueError("空文件")
        
        # 填充到4字节的倍数
        padding = (4 - len(file_data) % 4) % 4
        padded_data = file_data + b'\x00' * padding
        
        # 转换为32位整数数组（小端）
        buffer = list(struct.unpack(f'<{len(padded_data)//4}I', padded_data))
        return file_data, buffer
    
    @staticmethod
    def encode_text(text: bytes, key: int) -> List[int]:
        """将文本数据编码为32位整数"""
        # 转换为utf-16leLE编码
        text_utf16 = text.decode('utf-8-sig').encode('utf-16le')
        
        # 填充到4字节的倍数
        padding = (4 - len(text_utf16) % 4) % 4
        padded_text = text_utf16 + b'\x00' * padding
        
        # 转换为32位整数（小端）
        word_count = len(padded_text) // 4
        data = list(struct.unpack(f'<{word_count}I', padded_text))
        
        # 编码数据
        ISBCodec.encode(data, word_count, key)
        
        return data


class ISBDecoder:
    """ISB文件解码器"""
    
    def __init__(self, codec: ISBCodec):
        self.codec = codec
    
    def decode_file(self, source_path: Union[str, Path], target_path: Union[str, Path]) -> None:
        """解码ISB文件"""
        source_path = Path(source_path)
        target_path = Path(target_path)
        
        # 读取文件
        file_data, buffer = self.codec.read_file_to_buffer(source_path)
        buffer_size = len(buffer)
        
        if buffer_size < 2:
            raise ValueError("文件太小，不是有效的ISB文件")
        
        # 解析文件结构
        blocks = buffer[buffer_size - 1]
        
        if blocks <= 0 or blocks > buffer_size:
            raise ValueError("无效的块数")
        
        table_start = buffer_size - 1 - blocks
        
        if table_start < 0:
            raise ValueError("无效的表偏移")
        
        # 获取偏移表
        table = buffer[table_start:table_start + blocks]
        table.append(table_start * 4)  # 添加表起始偏移
        
        # 解码并写入输出
        with target_path.open('wb') as out:
            self._process_blocks(buffer, table, blocks, out)
        
        print(f"✓ 成功解码: {source_path.name} → {target_path.name}")
    
    def _process_blocks(self, buffer: List[int], table: List[int], blocks: int, out) -> None:
        """处理所有块"""
        key = 0
        
        for i in range(blocks):
            # 写入块偏移头
            out.write(f"@{table[i]:x}\n".encode('ascii'))
            
            # 计算块边界
            start_idx = table[i] // 4
            end_idx = table[i + 1] // 4
            print(f"块{i}: start_idx={start_idx}, end_idx={end_idx}, 数据={buffer[start_idx:end_idx] if start_idx < end_idx and end_idx <= len(buffer) else '无效'}")
            
            if start_idx >= len(buffer) or end_idx > len(buffer):
                #print(f"警告: 块 {i} 边界无效，跳过")
                continue
            
            # 处理块内容
            key = self._process_block_content(buffer, start_idx, end_idx, key, out)
    
    def _process_block_content(self, buffer: List[int], start: int, end: int, key: int, out) -> int:
        """处理单个块的内容"""
        idx = start
        local_50_idx = None
        
        # 检查块开始处的值
        if idx < end:
            first_val = buffer[idx]
            #print(f"检查第一个值: 0x{first_val:x}, KEY_THRESHOLD: 0x{ISBCodec.KEY_THRESHOLD:x}")
            
            if first_val < ISBCodec.KEY_THRESHOLD:
                local_50_idx = idx + (first_val >> 0x12) + 1
                #print(f"设置 local_50_idx = {local_50_idx}")
            else:
                # 这是密钥：设置密钥并输出
                #print(f"发现密钥: 0x{first_val:x}，输出并跳过")
                key = first_val
                out.write(f"${first_val:8x}\n".encode('ascii'))
                idx += 1
        
        #print(f"开始while循环: idx={idx}, end={end}")

        while idx < end:
            current_val = buffer[idx]
            #print(f"循环: idx={idx}, current_val=0x{current_val:x}")
            
            # 处理不同类型的条目
            if current_val == ISBCodec.MARKER_NUMBER:
                #print("匹配 MARKER_NUMBER")
                idx = self._handle_number_entry(buffer, idx, end, out)
            elif current_val == ISBCodec.MARKER_TEXT:
                #print("匹配 MARKER_TEXT")
                idx = self._handle_text_entry(buffer, idx, end, key, out)
            else:
                #print("匹配 hex_entry")
                idx = self._handle_hex_entry(buffer, idx, current_val, local_50_idx, out)
            
            #print(f"循环后: idx={idx}")
        
        return key
    
    def _handle_number_entry(self, buffer: List[int], idx: int, end: int, out) -> int:
        """处理数字条目（0x40403模式）"""
        idx += 1
        if idx < end:
            out.write(f"+{buffer[idx]:8x}\n".encode('ascii'))
            idx += 1
        return idx
    
    def _handle_text_entry(self, buffer: List[int], idx: int, end: int, key: int, out) -> int:
        #print(f"处理文本: idx={idx}, next_val=0x{(buffer[idx+1] if idx+1 < end else 0):x}")
        """处理文本条目（0x40400模式）"""
        if idx + 1 >= end:
            return idx + 1
        
        text_length = buffer[idx + 1]
        
        if text_length <= ISBCodec.MAX_TEXT_LENGTH:
            idx += 2
            word_count = self.codec.calculate_word_count(text_length)
            
            if idx + word_count <= end:
                # 解码文本
                text_data = buffer[idx:idx + word_count].copy()
                self.codec.decode(text_data, word_count, key)
                
                # 转换为字节
                byte_list = bytearray()
                for num in text_data:
                    byte_list.extend([
                        num & 0xFF,
                        (num >> 8) & 0xFF,
                        (num >> 16) & 0xFF,
                        (num >> 24) & 0xFF
                    ])
                
                # 写入文本
                out.write(bytes(byte_list[:text_length]).decode('utf-16le').encode('utf8'))
                out.write(b'\n')
                
                idx += word_count
            else:
                idx += 1
        else:
            # 长度超过限制，当作两个普通值处理
            #print(f"长度超限，当作普通值处理: 0x{buffer[idx]:x}, 0x{text_length:x}")
            
            # 输出第一个值 (0x40400)
            if idx < end:
                out.write(f"#{buffer[idx]:8x}\n".encode('ascii'))
                idx += 1
            
            # 输出第二个值 (0x2cb02908)
            if idx < end:
                out.write(f"#{buffer[idx]:8x}\n".encode('ascii'))
                idx += 1
        
        return idx
    
    def _handle_hex_entry(self, buffer: List[int], idx: int, value: int, 
                        local_50_idx: Optional[int], out) -> int:
        """处理十六进制条目"""
        #print(f"处理hex条目: idx={idx}, value=0x{value:x}, local_50_idx={local_50_idx}")
        
        if local_50_idx is not None and idx < local_50_idx:
            #print(f"输出 #{value:8x}")
            out.write(f"#{value:8x}\n".encode('ascii'))
        else:
            #print(f"输出 ${value:8x}")
            out.write(f"${value:8x}\n".encode('ascii'))
        return idx + 1


class ISBEncoder:
    """ISB文件编码器"""
    
    def __init__(self, codec: ISBCodec):
        self.codec = codec
    
    def encode_file(self, source_path: Union[str, Path], target_path: Union[str, Path]) -> None:
        """编码文本文件为ISB"""
        source_path = Path(source_path)
        target_path = Path(target_path)
        
        # 解析文本文件
        blocks, key = self._parse_text_file(source_path)
        
        if not blocks:
            raise ValueError("没有找到有效的块数据")
        
        # 创建ISB文件
        self._create_isb_file(blocks, target_path, key)
        
        print(f"✓ 成功编码: {source_path.name} → {target_path.name}")
    
    def _parse_text_file(self, file_path: Path) -> Tuple[List[Dict], int]:
        """解析文本文件"""
        blocks = []
        current_block = None
        key = 0
        
        with file_path.open('rb') as f:
            for line_num, line in enumerate(f, 1):
                line = line.rstrip(b'\r\n')
                
                # 修改这里：不跳过空行，而是作为空文本处理
                if not line:
                    if current_block:
                        current_block['entries'].append({
                            'type': 'text',
                            'data': b''  # 空行编码为空字符串
                        })
                    continue
                
                try:
                    if line.startswith(b'@'):
                        # 新块
                        offset = int(line[1:].decode('ascii'), 16)
                        if current_block is not None:
                            blocks.append(current_block)
                        current_block = {
                            'offset': offset,
                            'entries': []
                        }
                    
                    elif line.startswith(b'+'):
                        # 数字条目
                        value = int(line[1:].decode('ascii').strip(), 16)
                        if current_block:
                            current_block['entries'].append({
                                'type': 'number',
                                'value': value
                            })
                    
                    elif line.startswith((b'#', b'$')):
                        # 十六进制值
                        value = int(line[1:].decode('ascii').strip(), 16)
                        if current_block:
                            current_block['entries'].append({
                                'type': 'hex',
                                'value': value,
                                'special': line.startswith(b'#')
                            })
                            
                            # 只有第一个块的第一个条目才检测密钥
                            if (len(blocks) == 0 and len(current_block['entries']) == 1 and 
                                value >= ISBCodec.KEY_THRESHOLD):
                                key = value
                    
                    else:
                        # 文本条目
                        if current_block:
                            current_block['entries'].append({
                                'type': 'text',
                                'data': line
                            })
                
                except ValueError as e:
                    print(f"警告: 第 {line_num} 行解析失败: {e}")
                    continue
        
        # 保存最后一个块
        if current_block is not None:
            blocks.append(current_block)
        
        return blocks, key
    
    def _create_isb_file(self, blocks: List[Dict], output_path: Path, key: int) -> None:
        """创建ISB文件"""
        buffer = []
        block_offsets = []
        current_key = key  # 使用局部变量跟踪当前密钥
        
        # 处理每个块
        for block_idx, block in enumerate(blocks):
            block_offsets.append(len(buffer) * 4)
            
            # 检查第一个块是否需要添加密钥
            skip_first_entry = False
            if block_idx == 0 and current_key >= ISBCodec.KEY_THRESHOLD:
                # 检查第一个条目是否就是密钥
                if (block['entries'] and 
                    block['entries'][0]['type'] == 'hex' and 
                    block['entries'][0]['value'] == current_key):
                    # 第一个条目就是密钥，添加它并标记跳过
                    buffer.append(current_key)
                    skip_first_entry = True
                else:
                    # 需要添加密钥
                    buffer.append(current_key)
            
            # 处理块中的条目
            for entry_idx, entry in enumerate(block['entries']):
                # 跳过已经作为密钥处理的第一个条目
                if skip_first_entry and entry_idx == 0:
                    continue
                    
                if entry['type'] == 'number':
                    buffer.extend([ISBCodec.MARKER_NUMBER, entry['value']])

                elif entry['type'] == 'text':
                    text_data = entry['data']
                    # 计算utf-16le编码后的长度
                    text_utf16 = text_data.decode('utf-8').encode('utf-16le')
                    text_length = len(text_utf16)
                    
                    # 只编码长度合法的文本
                    if text_length <= ISBCodec.MAX_TEXT_LENGTH:
                        buffer.extend([ISBCodec.MARKER_TEXT, text_length])
                        # 使用当前密钥编码文本
                        encoded_words = self.codec.encode_text(text_data, current_key)
                        buffer.extend(encoded_words)
                    else:
                        print(f"警告: 文本长度 {text_length} 超过限制，跳过")
                
                else:  # hex
                    value = entry['value']
                    buffer.append(value)
                    
                    # 检查是否是新密钥（如果是$开头的hex值且大于阈值）
                    if (not entry.get('special', True) and  # $开头的hex（special=False）
                        value >= ISBCodec.KEY_THRESHOLD):
                        current_key = value  # 更新当前密钥
        
        # 添加偏移表和块数
        buffer.extend(block_offsets)
        buffer.append(len(blocks))
        
        # 写入文件
        with output_path.open('wb') as f:
            data = struct.pack(f'<{len(buffer)}I', *buffer)
            f.write(data)


class ISBProcessor:
    """ISB文件处理器"""
    
    def __init__(self):
        self.codec = ISBCodec()
        self.decoder = ISBDecoder(self.codec)
        self.encoder = ISBEncoder(self.codec)
    
    def process_directory(self, input_dir: Path, output_dir: Path, mode: str) -> None:
        """处理目录中的所有文件"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        processed = 0
        failed = 0
        
        if mode == 'decode':
            pattern = '*.isb'
            processor = self.decoder.decode_file
            ext_from, ext_to = '.isb', '.txt'
        else:
            pattern = '*.txt'
            processor = self.encoder.encode_file
            ext_from, ext_to = '.txt', '.isb'
        
        # 获取所有匹配的文件
        files = list(input_dir.glob(pattern))
        
        if not files:
            print(f"未找到 {pattern} 文件")
            return
        
        print(f"找到 {len(files)} 个文件待处理...\n")
        
        # 处理每个文件
        for file_path in files:
            output_path = output_dir / file_path.name.replace(ext_from, ext_to)
            
            try:
                processor(file_path, output_path)
                processed += 1
            except Exception as e:
                print(f"✗ 处理失败: {file_path.name} - {e}")
                failed += 1
        
        # 统计信息
        print(f"\n{'='*50}")
        print(f"处理完成:")
        print(f"  成功: {processed} 个文件")
        print(f"  失败: {failed} 个文件")
        print(f"  输出目录: {output_dir}")


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(
        description='ISB 文件编解码器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  解码ISB文件:  %(prog)s decode input_dir output_dir
  编码文本文件:  %(prog)s encode input_dir output_dir
  
  解码单个文件:  %(prog)s decode-file input.isb output.txt
  编码单个文件:  %(prog)s encode-file input.txt output.isb
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 批量解码命令
    decode_parser = subparsers.add_parser('decode', help='批量解码ISB文件')
    decode_parser.add_argument('input_dir', help='包含ISB文件的目录')
    decode_parser.add_argument('output_dir', help='输出目录')
    
    # 批量编码命令
    encode_parser = subparsers.add_parser('encode', help='批量编码文本文件')
    encode_parser.add_argument('input_dir', help='包含文本文件的目录')
    encode_parser.add_argument('output_dir', help='输出目录')
    
    # 单文件解码命令
    decode_file_parser = subparsers.add_parser('decode-file', help='解码单个ISB文件')
    decode_file_parser.add_argument('input_file', help='输入ISB文件')
    decode_file_parser.add_argument('output_file', help='输出文本文件')
    
    # 单文件编码命令
    encode_file_parser = subparsers.add_parser('encode-file', help='编码单个文本文件')
    encode_file_parser.add_argument('input_file', help='输入文本文件')
    encode_file_parser.add_argument('output_file', help='输出ISB文件')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    processor = ISBProcessor()
    
    try:
        if args.command == 'decode':
            processor.process_directory(
                Path(args.input_dir), 
                Path(args.output_dir), 
                'decode'
            )
        elif args.command == 'encode':
            processor.process_directory(
                Path(args.input_dir), 
                Path(args.output_dir), 
                'encode'
            )
        elif args.command == 'decode-file':
            processor.decoder.decode_file(
                Path(args.input_file),
                Path(args.output_file)
            )
        elif args.command == 'encode-file':
            processor.encoder.encode_file(
                Path(args.input_file),
                Path(args.output_file)
            )
    
    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
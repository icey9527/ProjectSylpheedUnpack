import os
import sys
import struct
import json
import argparse
from PIL import Image
from pathlib import Path

class ImageConverter:
    def __init__(self):
        self.header_data = {}
        self.json_file = "list.json"
        
    def read_image_header(self, data):
        """解析图像文件头"""
        if len(data) < 36:
            print(f"文件太小，至少需要36字节，实际{len(data)}字节")
            return None
        
        try:
            # 读取文件头 - 使用大端序
            signature = data[0:4]
            width = struct.unpack('>I', data[0x14:0x18])[0]   # 大端序，4字节无符号整数
            height = struct.unpack('>I', data[0x18:0x1c])[0]  # 大端序，4字节无符号整数
            
            return {
                'signature': signature.hex(),  # 转换为hex字符串
                'width': width,
                'height': height,
                'pixel_data_offset': 0x40,
                'header_bytes': data[:0x40].hex()  # 保存前64字节的头部数据
            }
        except struct.error as e:
            print(f"解析文件头失败: {e}")
            return None
    
    def extract_to_png(self, input_file, output_file):
        """将T32/T8aD文件转换为PNG"""
        try:
            print(f"\n正在提取: {input_file}")
            
            with open(input_file, 'rb') as f:
                data = f.read()
            
            print(f"文件大小: {len(data)} 字节")
            
            # 解析文件头
            header = self.read_image_header(data)
            if not header:
                print(f"无法解析文件头: {input_file}")
                return False
            
            width = header['width']
            height = header['height']
            pixel_offset = header['pixel_data_offset']
            
            # 检查尺寸是否合理
            if width <= 0 or height <= 0 or width > 10000 or height > 10000:
                print(f"不合理的图像尺寸: {width}x{height}")
                return False
            
            print(f"图像尺寸: {width}x{height}")
            
            # 检查数据是否足够
            expected_size = width * height * 4  # 32位RGBA = 4字节/像素
            available_size = len(data) - pixel_offset
            
            if available_size < expected_size:
                print(f"警告: 数据不足，期望 {expected_size} 字节，实际 {available_size} 字节")
                return False
            
            # 读取像素数据
            pixel_data = data[pixel_offset:pixel_offset + expected_size]
            
            # 将字节数据转换为RGBA像素
            pixels = []
            for i in range(0, len(pixel_data), 4):
                a = pixel_data[i]
                r = pixel_data[i + 1] 
                g = pixel_data[i + 2]
                b = pixel_data[i + 3]
                pixels.append((r, g, b, a))
            
            # 创建PIL图像
            img = Image.new('RGBA', (width, height))
            img.putdata(pixels)
            
            # 保存为PNG
            img.save(output_file, 'PNG')
            
            # 保存头部信息到字典
            relative_path = os.path.relpath(input_file).replace('\\', '/')  # 统一使用/作为路径分隔符
            self.header_data[relative_path] = header
            
            print(f"成功提取: {os.path.basename(input_file)} -> {os.path.basename(output_file)}")
            return True
            
        except Exception as e:
            print(f"提取失败 {input_file}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def write_from_png(self, png_file, output_file, original_path):
        """从PNG文件生成原始格式"""
        try:
            print(f"\n正在生成: {png_file} -> {output_file}")
            
            # 检查是否有对应的头部数据
            if original_path not in self.header_data:
                print(f"错误: 找不到原始文件 {original_path} 的头部数据")
                return False
            
            header_info = self.header_data[original_path]
            
            # 读取PNG图像
            img = Image.open(png_file)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            width, height = img.size
            
            # 验证尺寸是否匹配
            if width != header_info['width'] or height != header_info['height']:
                print(f"警告: 图像尺寸不匹配。PNG: {width}x{height}, 原始: {header_info['width']}x{header_info['height']}")
            
            # 恢复原始头部数据
            header_bytes = bytes.fromhex(header_info['header_bytes'])
            
            # 获取像素数据
            pixels = list(img.getdata())
            
            # 转换像素数据为原始格式 (ARGB)
            pixel_bytes = bytearray()
            for r, g, b, a in pixels:
                pixel_bytes.extend([a, r, g, b])
            
            # 组合头部和像素数据
            output_data = header_bytes + pixel_bytes
            
            # 写入文件
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'wb') as f:
                f.write(output_data)
            
            print(f"成功生成: {output_file}")
            return True
            
        except Exception as e:
            print(f"生成失败 {png_file}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def extract_mode(self, input_folder, output_folder):
        """提取模式：T32/T8aD -> PNG"""
        if not os.path.exists(input_folder):
            print(f"错误: 输入文件夹不存在: {input_folder}")
            return
        
        os.makedirs(output_folder, exist_ok=True)
        
        # 加载已有的头部数据（如果存在）
        json_path = os.path.join(output_folder, self.json_file)
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    self.header_data = json.load(f)
                print(f"已加载现有头部数据: {len(self.header_data)} 条记录")
            except Exception as e:
                print(f"加载现有JSON失败: {e}")
                self.header_data = {}
        
        supported_extensions = {'.t32', '.t8ad'}
        total_files = 0
        converted_files = 0
        
        for root, dirs, files in os.walk(input_folder):
            for file in files:
                file_ext = None
                for ext in supported_extensions:
                    if file.lower().endswith(ext.lower()):
                        file_ext = ext
                        break
                
                if file_ext:
                    total_files += 1
                    input_path = os.path.join(root, file)
                    
                    # 计算相对路径
                    rel_path = os.path.relpath(root, input_folder)
                    if rel_path == '.':
                        output_dir = output_folder
                    else:
                        output_dir = os.path.join(output_folder, rel_path)
                    
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # 生成输出文件名
                    output_path = os.path.join(output_dir, file + '.png')
                    
                    # 转换文件
                    if self.extract_to_png(input_path, output_path):
                        converted_files += 1
        
        # 保存头部数据到JSON
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(self.header_data, f, indent=2, ensure_ascii=False)
            print(f"头部数据已保存到: {json_path}")
        except Exception as e:
            print(f"保存JSON失败: {e}")
        
        print(f"\n提取完成!")
        print(f"总文件数: {total_files}")
        print(f"成功提取: {converted_files}")
        print(f"失败数量: {total_files - converted_files}")
    
    def write_mode(self, input_folder, output_folder):
        """生成模式：PNG -> T32/T8aD"""
        if not os.path.exists(input_folder):
            print(f"错误: 输入文件夹不存在: {input_folder}")
            return
        
        # 加载头部数据
        json_path = os.path.join(input_folder, self.json_file)
        if not os.path.exists(json_path):
            print(f"错误: 找不到头部数据文件: {json_path}")
            print("请先使用 -e 模式提取文件")
            return
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                self.header_data = json.load(f)
        except Exception as e:
            print(f"加载JSON失败: {e}")
            return
        
        print(f"已加载头部数据: {len(self.header_data)} 条记录")
        
        os.makedirs(output_folder, exist_ok=True)
        
        total_files = 0
        converted_files = 0
        
        # 遍历所有PNG文件
        for root, dirs, files in os.walk(input_folder):
            for file in files:
                if file.lower().endswith('.png') and (file.lower().endswith('.t32.png') or file.lower().endswith('.t8ad.png')):
                    total_files += 1
                    png_path = os.path.join(root, file)
                    
                    # 从文件名中去掉.png后缀得到原始文件名
                    original_filename = file[:-4]  # 去掉.png
                    
                    # 查找对应的原始文件路径
                    original_key = None
                    for key in self.header_data.keys():
                        if os.path.basename(key) == original_filename:
                            original_key = key
                            break
                    
                    if not original_key:
                        # 尝试使用相对路径匹配
                        rel_path = os.path.relpath(root, input_folder).replace('\\', '/')
                        if rel_path == '.':
                            test_key = original_filename
                        else:
                            test_key = f"{rel_path}/{original_filename}"
                        
                        if test_key in self.header_data:
                            original_key = test_key
                        else:
                            print(f"警告: 找不到 {file} 对应的原始文件信息")
                            continue
                    
                    # 计算输出路径
                    rel_path = os.path.relpath(root, input_folder)
                    if rel_path == '.':
                        output_dir = output_folder
                    else:
                        output_dir = os.path.join(output_folder, rel_path)
                    
                    output_path = os.path.join(output_dir, original_filename)
                    
                    if self.write_from_png(png_path, output_path, original_key):
                        converted_files += 1
        
        print(f"\n生成完成!")
        print(f"总文件数: {total_files}")
        print(f"成功生成: {converted_files}")
        print(f"失败数量: {total_files - converted_files}")

def main():
    parser = argparse.ArgumentParser(description='T32/T8aD图像文件与PNG双向转换工具')
    parser.add_argument('-e', '--extract', action='store_true', 
                        help='提取模式：将T32/T8aD文件转换为PNG')
    parser.add_argument('-w', '--write', action='store_true', 
                        help='生成模式：将PNG文件转换回T32/T8aD')
    parser.add_argument('input_folder', help='输入文件夹路径')
    parser.add_argument('output_folder', help='输出文件夹路径')
    
    args = parser.parse_args()
    
    if not args.extract and not args.write:
        print("错误: 请指定模式 -e (提取) 或 -w (生成)")
        parser.print_help()
        return
    
    if args.extract and args.write:
        print("错误: 不能同时指定 -e 和 -w")
        parser.print_help()
        return
    
    converter = ImageConverter()
    
    if args.extract:
        print("=== 提取模式 ===")
        converter.extract_mode(args.input_folder, args.output_folder)
    else:
        print("=== 生成模式 ===")
        converter.write_mode(args.input_folder, args.output_folder)

if __name__ == "__main__":
    main()
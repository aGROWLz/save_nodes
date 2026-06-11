import os
import json
import time
import struct
import zlib
import logging
from datetime import datetime

from PIL import Image
from PIL.PngImagePlugin import PngInfo

import numpy as np

import folder_paths
from comfy.cli_args import args
import nodes

logger = logging.getLogger("SaveImageWithCheck")


def verify_png_integrity(filepath):
    """验证 PNG 文件完整性：文件头、CRC 校验、IDAT 数据"""
    with open(filepath, 'rb') as f:
        # 1. 检查 PNG 文件头魔数
        header = f.read(8)
        if header != b'\x89PNG\r\n\x1a\n':
            return False, "PNG 文件头损坏"

        idat_data = bytearray()
        idat_found = False

        # 2. 遍历所有 chunk 检查 CRC
        while True:
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                break

            length = struct.unpack('>I', chunk_header[:4])[0]
            chunk_type = chunk_header[4:8]

            chunk_data = f.read(length)
            if len(chunk_data) < length:
                return False, f"Chunk {chunk_type} 数据不完整"

            stored_crc = f.read(4)
            if len(stored_crc) < 4:
                return False, f"Chunk {chunk_type} CRC 缺失"

            # CRC 校验：type + data
            calculated_crc = struct.pack('>I', zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF)
            if stored_crc != calculated_crc:
                return False, f"Chunk {chunk_type} CRC 校验失败"

            # 收集 IDAT 数据
            if chunk_type == b'IDAT':
                idat_data.extend(chunk_data)
                idat_found = True

            # 遇到 IEND 结束
            if chunk_type == b'IEND':
                break

        # 3. 检查 IDAT 数据
        if not idat_data:
            return False, "缺少 IDAT 图片数据"

        # 尝试解压 IDAT 数据验证完整性
        try:
            decompressed = zlib.decompress(bytes(idat_data))
            if len(decompressed) == 0:
                return False, "IDAT 解压后数据为空"
        except zlib.error as e:
            return False, f"IDAT 数据解压失败: {e}"

    return True, "OK"


class SaveImageWithCheck:
    """官方 SaveImage 节点的完整复刻，增加了保存后图片完整性检测和 log 输出。"""

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.prefix_append = ""
        self.compress_level = 4

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "The images to save."}),
                "filename_prefix": ("STRING", {
                    "default": "ComfyUI",
                    "tooltip": "The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes."
                }),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("log",)
    OUTPUT_NODE = True
    FUNCTION = "save_images"

    CATEGORY = "image"
    DESCRIPTION = "Saves the input images to your ComfyUI output directory with integrity check."
    SEARCH_ALIASES = ["save", "save image", "export image", "output image", "write image", "download", "check"]

    def save_images(self, images, filename_prefix="ComfyUI", prompt=None, extra_pnginfo=None):
        filename_prefix += self.prefix_append
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(
            filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0]
        )

        results = list()
        logs = list()
        timestamp = datetime.now().strftime("%H:%M:%S")
        total_count = len(images)

        logs.append(f"📷 [{timestamp}] 开始保存 {total_count} 张图片")
        logs.append(f"📁 输出目录: {full_output_folder}")
        logs.append(f"📝 文件前缀: {filename_prefix}")
        logs.append("")

        for (batch_number, image) in enumerate(images):
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            metadata = None
            if not args.disable_metadata:
                metadata = PngInfo()
                if prompt is not None:
                    metadata.add_text("prompt", json.dumps(prompt))
                if extra_pnginfo is not None:
                    for x in extra_pnginfo:
                        metadata.add_text(x, json.dumps(extra_pnginfo[x]))

            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            file = f"{filename_with_batch_num}_{counter:05}_.png"
            full_path = os.path.join(full_output_folder, file)

            # 保存图片
            save_start = time.time()
            img.save(full_path, pnginfo=metadata, compress_level=self.compress_level)
            save_duration = time.time() - save_start

            # 检测图片完整性
            check_start = time.time()
            try:
                # PIL 基础解码验证
                with Image.open(full_path) as verify_img:
                    verify_img.load()

                # PNG 完整性验证：文件头 + CRC + IDAT
                ok, msg = verify_png_integrity(full_path)
                if not ok:
                    raise RuntimeError(f"PNG 完整性验证失败: {msg}")

                check_duration = time.time() - check_start
                file_size = os.path.getsize(full_path)

                logs.append(f"  ✅ [{batch_number + 1}/{total_count}] {file}")
                logs.append(f"     ⏱️ 保存 {save_duration:.2f}s | 检测 {check_duration:.2f}s")
                logs.append(f"     📐 {img.size[0]}x{img.size[1]} | 💾 {file_size // 1024}KB")
                logs.append("")

                logger.info(f"[SaveImage] [{batch_number + 1}/{total_count}] {file} | 保存 {save_duration:.2f}s | 检测 {check_duration:.2f}s | {img.size[0]}x{img.size[1]} | {file_size // 1024}KB | OK")
            except Exception as e:
                logs.append(f"  ❌ [{batch_number + 1}/{total_count}] {file}")
                logs.append(f"     ⚠️ 检测失败: {e}")
                logs.append("")

                logger.error(f"[SaveImage] [{batch_number + 1}/{total_count}] {file} | FAIL - {e}")
                raise RuntimeError(f"图片 {file} 保存后检测损坏: {e}")

            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": self.type
            })
            counter += 1

        logs.append(f"🎉 保存完成: {total_count} 张图片全部通过检测")
        log_text = "\n".join(logs)

        logger.info(f"[SaveImage] 任务完成: {total_count} 张图片保存成功")

        return {"ui": {"images": results}, "result": (log_text,)}


# 直接覆盖官方 SaveImage 节点
nodes.NODE_CLASS_MAPPINGS["SaveImage"] = SaveImageWithCheck
nodes.NODE_DISPLAY_NAME_MAPPINGS["SaveImage"] = "Save Image"

# 节点注册（空，因为已经手动覆盖了）
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

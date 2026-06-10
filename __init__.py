import os
import json
import time
import logging
from datetime import datetime

from PIL import Image
from PIL.PngImagePlugin import PngInfo

import numpy as np

import folder_paths
from comfy.cli_args import args
import nodes

logger = logging.getLogger("SaveImageWithCheck")


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

        logs.append(f"[{timestamp}] 开始保存 {total_count} 张图片")
        logs.append(f"输出目录: {full_output_folder}")
        logs.append(f"文件前缀: {filename_prefix}")
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
                with Image.open(full_path) as verify_img:
                    verify_img.load()
                check_duration = time.time() - check_start
                file_size = os.path.getsize(full_path)

                logs.append(f"[{batch_number + 1}/{total_count}] {file}")
                logs.append(f"  保存: {save_duration:.2f}s | 检测: {check_duration:.2f}s")
                logs.append(f"  尺寸: {img.size[0]}x{img.size[1]} | 大小: {file_size // 1024}KB")
                logs.append(f"  状态: OK")
                logs.append("")

                log_line = f"[SaveImage] [{batch_number + 1}/{total_count}] {file} | 保存 {save_duration:.2f}s | 检测 {check_duration:.2f}s | {img.size[0]}x{img.size[1]} | {file_size // 1024}KB | OK"
                logger.info(log_line)
                print(log_line)
            except Exception as e:
                logs.append(f"[{batch_number + 1}/{total_count}] {file}")
                logs.append(f"  状态: FAIL - {e}")
                logs.append("")

                err_line = f"[SaveImage] [{batch_number + 1}/{total_count}] {file} | FAIL - {e}"
                logger.error(err_line)
                print(err_line)
                raise RuntimeError(f"图片 {file} 保存后检测损坏: {e}")

            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": self.type
            })
            counter += 1

        logs.append(f"保存完成: {total_count} 张图片全部通过检测")
        log_text = "\n".join(logs)

        logger.info(f"[SaveImage] 任务完成: {total_count} 张图片保存成功")
        print(f"[SaveImage] 任务完成: {total_count} 张图片保存成功")

        return {"ui": {"images": results}, "result": (log_text,)}


# 直接覆盖官方 SaveImage 节点
nodes.NODE_CLASS_MAPPINGS["SaveImage"] = SaveImageWithCheck
nodes.NODE_DISPLAY_NAME_MAPPINGS["SaveImage"] = "Save Image"

# 节点注册（空，因为已经手动覆盖了）
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

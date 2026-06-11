# Save Nodes - ComfyUI 图片保存增强插件

强制替换 ComfyUI 官方 `SaveImage` 节点，在保留原有功能的基础上，增加**PNG 完整性检测**和**详细日志输出**。

## 功能特性

- **强制覆盖官方节点** - 直接替换 `SaveImage`，无需修改工作流
- **PNG 完整性检测** - 保存后自动验证图片是否损坏
  - PNG 文件头魔数校验
  - 所有 Chunk 的 CRC32 校验
  - IDAT 图片数据块存在性检查
  - IDAT 数据 zlib 解压验证
  - PIL 解码验证
- **详细日志输出** - 带图标的结构化日志，一目了然
- **错误抛出** - 检测到损坏时立即报错，避免后续流程使用损坏图片

## 安装

将 `save_nodes` 文件夹复制到 ComfyUI 的 `custom_nodes` 目录下：

```
ComfyUI/custom_nodes/save_nodes/
├── __init__.py
└── README.md
```

重启 ComfyUI 即可生效。

## 日志输出示例

**成功：**
```
📷 [14:32:15] 开始保存 2 张图片
📁 输出目录: D:\ComfyUI\output
📝 文件前缀: ComfyUI

  ✅ [1/2] ComfyUI_00001_.png
     ⏱️ 保存 0.58s | 检测 0.15s
     📐 2048x2048 | 💾 4403KB

  ✅ [2/2] ComfyUI_00002_.png
     ⏱️ 保存 0.52s | 检测 0.12s
     📐 2048x2048 | 💾 4215KB

🎉 保存完成: 2 张图片全部通过检测
```

**失败：**
```
📷 [14:32:15] 开始保存 1 张图片
📁 输出目录: D:\ComfyUI\output
📝 文件前缀: ComfyUI

  ❌ [1/1] ComfyUI_00001_.png
     ⚠️ 检测失败: PNG 完整性验证失败: Chunk b'IDAT' CRC 校验失败
```

## 验证内容

| 验证项 | 说明 |
|--------|------|
| PNG 文件头 | 验证 `89 50 4E 47 0D 0A 1A 0A` 魔数 |
| CRC 校验 | 遍历所有 chunk，验证 type + data 的 CRC32 |
| IDAT 数据 | 检查图片数据块存在性 |
| IDAT 解压 | 尝试 zlib 解压验证数据完整性 |
| PIL 解码 | `Image.open().load()` 基础解码验证 |

## 输出接口

| 输出 | 类型 | 说明 |
|------|------|------|
| `log` | STRING | 本次保存任务的完整日志 |

## 使用场景

- 需要确保图片保存完整性的工作流
- 调试保存失败问题时查看详细日志
- 批量生成图片时确认每张都成功保存

## 兼容性

- ComfyUI 最新版本
- Python 3.10+

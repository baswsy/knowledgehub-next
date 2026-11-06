"""将用户文件转换为 MCP 可检索的文本；不执行文件内容。"""
from pathlib import Path
from io import BytesIO
import hashlib
import zipfile
import xml.etree.ElementTree as ET

MAX_BYTES = 10 * 1024 * 1024

def extract(name: str, data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise ValueError("单个文件不能超过 10 MB")
    suffix = Path(name).suffix.lower()
    if suffix in {".md", ".txt", ".json", ".csv"}:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("文本需使用 UTF-8 编码") from exc
    elif suffix == ".docx":
        with zipfile.ZipFile(BytesIO(data)) as z:
            info = z.getinfo("word/document.xml")
            if info.file_size > 20 * 1024 * 1024:
                raise ValueError("Word 解压内容过大")
            root = ET.fromstring(z.read(info))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        text = "\n\n".join("".join(p.itertext()) for p in root.findall(".//w:p", ns))
    elif suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("请先解除 PDF 密码")
        if len(reader.pages) > 200:
            raise ValueError("PDF 不能超过 200 页")
        text = "\n\n".join(f"【第 {i} 页】\n{page.extract_text() or ''}" for i, page in enumerate(reader.pages, 1) if (page.extract_text() or '').strip())
    else:
        raise ValueError("支持 PDF、DOCX、TXT、Markdown")
    if not text.strip():
        raise ValueError("没有提取到文字；扫描版 PDF 请先进行 OCR")
    if len(text) > 1_000_000:
        raise ValueError("提取文本过长，请拆分文件")
    # 控制段落长度，避免大段资料消耗过多模型上下文。
    return "\n\n".join(p[i:i+1800] for p in text.split("\n\n") for i in range(0, len(p), 1800))

def save_material(name: str, data: bytes, directory: Path) -> Path:
    text = extract(name, data)
    directory.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(data).hexdigest()[:16]
    path = directory / f"note-{key}.md"
    path.write_text(f"# {Path(name).name}\n\n{text}", encoding="utf-8")
    return path

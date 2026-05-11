"""
快速搜索引擎 —— 纯逻辑层，零 PySide6 依赖。

解析 Ctrl+A 全选文字中的特殊格式 (/*, /目录/, tag=标签/搜索文字)，
在 SavedEmotes 目录内检索匹配的表情包 item list。
"""
import os
import re
import logging
from Core.emote_sender import ALL_EXTS

logger = logging.getLogger(__name__)


def extract_tag_name(tag):
    """从旧格式(str)或新格式(dict)中提取标签名"""
    if isinstance(tag, str):
        return tag.lower()
    if isinstance(tag, dict):
        return tag.get("name", "").lower()
    return ""


class QuickSearchEngine:
    """表情包快速搜索引擎：解析搜索模式 → 返回匹配项列表。"""

    def __init__(self, saved_emotes_mgr):
        self._mgr = saved_emotes_mgr

    # 公开接口

    def parse_pattern(self, text):
        """
        解析选中文字，支持子文件夹物理导航。
        返回 None (不匹配) 或 {"items": [...], "folder": "...", "title": "..."}。

        格式：
            /*                          → 扫描全部
            /目录/                      → 物理子文件夹直接导航
            /目录/子目录/               → 多级物理导航
            /目录/搜索文字              → 导航后搜索
            /目录/tag=标签              → 按标签筛选
            /目录/tag=标签/搜索文字     → 标签 + 文本组合搜索

        目录匹配先后顺序：物理路径 > JSON folders > display_name
        """
        text = text.strip().rstrip('/')
        if not text:
            return None

        if text == "/*":
            items = self.scan_all()
            logger.debug(f"[QuickSearchEngine] /* 扫描全部: {len(items)} 项")
            for item in items:
                item["_score"] = 5
            return {"items": items, "folder": "", "title": "全部收藏"}

        if text.startswith('/*') and len(text) > 2:
            suffix = text[2:].lstrip('/')
            items = self.scan_all()
            items = self._apply_syntax(items, suffix)
            logger.debug(f"[QuickSearchEngine] /*{suffix} 全量搜索: {len(items)} 项")
            return {"items": items, "folder": "", "title": suffix or "全部收藏"}

        if not text.startswith('/'):
            return None

        rest = text[1:]
        if not rest:
            return None

        current_rel = ""
        segments = rest.split('/')

        for i, seg in enumerate(segments):
            if not seg:
                continue
            is_last = (i == len(segments) - 1)

            test_rel = (os.path.join(current_rel, seg) if current_rel else seg).replace('\\', '/')
            phys = self._mgr.resolve_physical_folder(test_rel)

            if phys:
                current_rel = test_rel
                if is_last:
                    items = self._mgr.scan_physical_folder(current_rel)
                    for item in items:
                        item["_score"] = 5
                    return {"items": items, "folder": current_rel, "title": seg}
                continue

            remaining = "/".join(segments[i:])
            logger.debug(f"[QuickSearchEngine] current_rel={repr(current_rel)}, search={repr(remaining)}")

            if not current_rel:
                folder_key = self._find_folder_key_by_name(seg)
                if folder_key:
                    if len(segments) > i + 1:
                        search_suffix = "/".join(segments[i+1:])
                        res = self._search_with_syntax(search_suffix, folder_key)
                        return {"items": res or [], "folder": folder_key, "title": search_suffix}
                    else:
                        items = self._mgr.get_items_in_folder(folder_key)
                        for item in items:
                            item["_score"] = 5
                        return {"items": items, "folder": folder_key, "title": seg}

                if 'tag=' in remaining:
                    items = self._mgr.scan_physical_folder("")
                    results = self._apply_syntax(items, remaining)
                    return {"items": results, "folder": "", "title": remaining}
                else:
                    items = self._mgr.scan_physical_folder("")
                    results = self.filter_items_by_text(items, remaining)
                    return {"items": results, "folder": "", "title": remaining}

            res = self._search_with_syntax(remaining, current_rel, physical=True)
            return {"items": res or [], "folder": current_rel, "title": remaining}

        return {"items": [], "folder": "", "title": rest}

    def scan_all(self):
        """递归扫描整个 SavedEmotes 目录，返回所有媒体文件的 item dict 列表，与 JSON 交叉索引."""
        root = self._mgr.saved_emotes_dir
        if not os.path.isdir(root):
            return []
        json_lookup = {}
        for item in self._mgr.collection.get("items", []):
            fn = item.get("filename", "")
            if fn:
                json_lookup[fn] = item
        results = []
        valid_exts = ALL_EXTS
        for dirpath, dirnames, filenames in os.walk(root):
            rel = os.path.relpath(dirpath, root).replace('\\', '/')
            if rel == '.':
                rel = ""
            for f in sorted(filenames):
                ext = os.path.splitext(f)[1].lower()
                if ext not in valid_exts:
                    continue
                if f in json_lookup:
                    item = dict(json_lookup[f])
                    item["_score"] = 5
                    results.append(item)
                else:
                    results.append({
                        "id": f,
                        "folder": rel,
                        "filename": f,
                        "display_name": os.path.splitext(f)[0],
                        "tags": [],
                        "_score": 5
                    })
        return results

    def filter_items_by_text(self, items, text):
        """简单文字过滤 + 计分排序."""
        results = []
        for it in items:
            dn = (it.get("display_name", "") or "").lower()
            fn = (it.get("filename", "") or "").lower()
            tl = text.lower()
            score = 0
            if dn == tl:
                score = 100
            elif tl in dn:
                score = 50
            elif fn == tl:
                score = 80
            elif tl in fn:
                score = 40
            elif any(tl in (extract_tag_name(t)) for t in it.get("tags", [])):
                score = 20
            if score > 0:
                it["_score"] = score
                results.append(it)
        results.sort(key=lambda x: x.get("_score", 0), reverse=True)
        return results

    def list_subfolders_at(self, rel_path):
        """列出指定物理目录下的子文件夹."""
        root = self._mgr.saved_emotes_dir
        abs_path = os.path.join(root, rel_path) if rel_path else root
        if not os.path.isdir(abs_path):
            return []
        result = []
        try:
            for entry in sorted(os.listdir(abs_path)):
                entry_path = os.path.join(abs_path, entry)
                if os.path.isdir(entry_path) and not entry.startswith('.'):
                    child_rel = (os.path.join(rel_path, entry) if rel_path else entry).replace('\\', '/')
                    result.append((entry, child_rel))
        except OSError:
            pass
        return result

    # 内部方法

    def _apply_syntax(self, items, suffix):
        """对现有 items 列表进行 tag= / 文本 筛选."""
        tag_match = re.search(r'tag\s*=\s*([^/]+)', suffix)
        text_part = re.sub(r'tag\s*=\s*[^/]+', '', suffix).strip().strip('/')

        if tag_match:
            tag_value = tag_match.group(1).strip()
            logger.debug(f"[QuickSearchEngine] tag 筛选: {tag_value} (all items)")
            items = [it for it in items if any(tag_value.lower() in extract_tag_name(t) for t in it.get("tags", []))]

        if text_part:
            logger.debug(f"[QuickSearchEngine] 文字搜索: {text_part}")
            items = [it for it in items if text_part.lower() in (it.get("display_name", "") or "").lower()]

        for it in items:
            it["_score"] = 5
        return items

    def _search_with_syntax(self, suffix, folder_key, physical=False):
        """对后缀进行 tag= / 文本 解析，在指定 folder 内搜索."""
        if physical:
            items = self._mgr.scan_physical_folder(folder_key)
        else:
            items = self._mgr.get_items_in_folder(folder_key)
        return self._apply_syntax(items, suffix)

    def _find_folder_key_by_name(self, name):
        folders = self._mgr.get_folders()
        name_lower = name.lower()
        for key, fdata in folders.items():
            if fdata.get("display_name", key).lower() == name_lower or key.lower() == name_lower:
                return key
        return None
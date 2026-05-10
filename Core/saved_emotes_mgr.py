import os
import sys
import json
import shutil
import time
import re
from typing import Optional
from Core.logger import logger
from Core.emote_sender import ALL_EXTS as VALID_EXTS


def get_root_dir_saved():
    """Get the root directory, consistent with ConfigManager."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SavedEmotesManager:
    """
    表情包收藏管理器 (SavedEmotes)
    
    目录结构:
        SavedEmotes/
            collection.json          # 全局收藏元数据
            folder_a/                # 用户创建的文件夹
                item1.png
                item1.png.meta.json  # 每个表情包的元数据（tags, display_name）
            folder_b/
                ...
    
    collection.json 格式:
    {
        "version": 1,
        "folders": {
            "default": { "display_name": "默认收藏", "sort_order": 0 },
            "folder_xxx": { "display_name": "我的表情", "sort_order": 1 }
        },
        "items": [
            {
                "id": "uuid_or_filename",
                "folder": "default",
                "filename": "item1.png",
                "display_name": "",
                "tags": [
                    {"name": "tag1", "color": "#66b2ff"},
                    {"name": "tag2", "color": "#ff6b6b"}
                ],
                "added_at": 1234567890.0,
                "sort_order": 0
            }
        ]
    }
    """

    def __init__(self):
        self.root_dir = get_root_dir_saved()
        self.saved_emotes_dir = os.path.join(self.root_dir, "SavedEmotes")
        self.collection_path = os.path.join(self.saved_emotes_dir, "collection.json")
        
        os.makedirs(self.saved_emotes_dir, exist_ok=True)
        
        self.collection = self._load_collection()

    def reload(self):
        """Reload collection from disk and sync with physical files."""
        self.collection = self._load_collection()
        # 清理已物理删除的条目
        removed = []
        valid_items = []
        for item in self.collection.get("items", []):
            fp = self._get_item_file_path(item)
            if os.path.exists(fp):
                # migrate old tag format
                self._migrate_tags(item)
                valid_items.append(item)
            else:
                removed.append(item.get("filename", "?"))
        if removed:
            self.collection["items"] = valid_items
            self._save_collection()
            logger.info(f"reload: 清理 {len(removed)} 个已删除文件: {removed}")

    def _migrate_tags(self, item):
        """迁移旧格式 tags (list of strings) → 新格式 (list of dicts)."""
        tags = item.get("tags", [])
        if tags and isinstance(tags[0], str):
            default_colors = ["#66b2ff", "#ff6b6b", "#ffd93d", "#6bcb77", "#4d96ff", "#ff922b"]
            new_tags = []
            for i, t in enumerate(tags):
                new_tags.append({"name": t, "color": default_colors[i % len(default_colors)]})
            item["tags"] = new_tags

    def _get_tag_names(self, item):
        """Return list of tag name strings."""
        tags = item.get("tags", [])
        if not tags:
            return []
        if isinstance(tags[0], str):
            return tags
        return [t["name"] for t in tags]

    def _get_item_file_path(self, item: dict) -> str:
        folder = item.get("folder", "")
        filename = item.get("filename", "")
        if folder:
            return os.path.join(self.saved_emotes_dir, folder, filename)
        return os.path.join(self.saved_emotes_dir, filename)

    def _load_collection(self) -> dict:
        """Load or create the collection database."""
        if os.path.exists(self.collection_path):
            try:
                with open(self.collection_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                data.setdefault("version", 1)
                data.setdefault("folders", {})
                data.setdefault("items", [])
                # 迁移旧格式: "default" 文件夹 → "" + "默认收藏" tag
                if "default" in data.get("folders", {}):
                    del data["folders"]["default"]
                for item in data["items"]:
                    if item.get("folder") == "default":
                        item["folder"] = ""
                        self._migrate_tags(item)
                        existing = self._get_tag_names(item)
                        if "默认收藏" not in existing:
                            tags = item.get("tags", [])
                            tags.insert(0, {"name": "默认收藏", "color": "#66b2ff"})
                            item["tags"] = tags
                    else:
                        self._migrate_tags(item)
                self._save_collection(data)
                return data
            except Exception as e:
                logger.exception(f"加载收藏数据库失败: {e}")
                return self._create_default_collection()
        else:
            return self._create_default_collection()

    def _create_default_collection(self) -> dict:
        """Create a default collection database."""
        default = {
            "version": 1,
            "folders": {},
            "items": []
        }
        self._save_collection(default)
        return default

    def _save_collection(self, data: dict = None):
        """Save the collection database to disk."""
        if data is None:
            data = self.collection
        try:
            with open(self.collection_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            self.collection = data
        except Exception as e:
            logger.error(f"保存收藏数据库失败: {e}")

    # ─── Folder Operations ────────────────────────────────────────

    def get_folders(self) -> dict:
        """Return all folders sorted by sort_order."""
        return self.collection.get("folders", {})

    def create_folder(self, display_name: str) -> str:
        """
        Create a new folder. Returns the folder key (internal id).
        The folder key is derived from the display_name, made filesystem-safe.
        """
        base_key = re.sub(r'[<>:"/\\|?*]', '_', display_name).strip()
        if not base_key:
            base_key = "folder"
        
        # Ensure uniqueness
        existing_keys = set(self.collection["folders"].keys())
        key = base_key
        counter = 1
        while key in existing_keys:
            key = f"{base_key}_{counter}"
            counter += 1
        
        # Determine next sort_order
        max_order = max((f.get("sort_order", 0) for f in self.collection["folders"].values()), default=0)
        
        self.collection["folders"][key] = {
            "display_name": display_name,
            "sort_order": max_order + 1
        }
        
        # Create the physical directory
        folder_path = os.path.join(self.saved_emotes_dir, key)
        os.makedirs(folder_path, exist_ok=True)
        
        self._save_collection()
        logger.info(f"创建收藏文件夹: {display_name} (key={key})")
        return key

    def rename_folder(self, folder_key: str, new_display_name: str):
        """Rename a folder's display name."""
        if folder_key in self.collection["folders"]:
            self.collection["folders"][folder_key]["display_name"] = new_display_name
            self._save_collection()
            logger.info(f"文件夹重命名: {folder_key} -> {new_display_name}")

    def delete_folder(self, folder_key: str):
        """
        Delete a folder and all items within it.
        The root (empty key) cannot be deleted.
        """
        if not folder_key:
            logger.warning("不能删除根目录")
            return False
        
        if folder_key in self.collection["folders"]:
            # Remove all items in this folder
            self.collection["items"] = [
                item for item in self.collection["items"]
                if item.get("folder") != folder_key
            ]
            del self.collection["folders"][folder_key]
            
            # Remove physical directory
            folder_path = os.path.join(self.saved_emotes_dir, folder_key)
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path, ignore_errors=True)
            
            self._save_collection()
            logger.info(f"删除收藏文件夹: {folder_key}")
            return True
        return False

    def reorder_folders(self, folder_keys_ordered: list):
        """Reorder folders by assigning sequential sort_order values."""
        for idx, key in enumerate(folder_keys_ordered):
            if key in self.collection["folders"]:
                self.collection["folders"][key]["sort_order"] = idx
        self._save_collection()

    # ─── Item Operations ──────────────────────────────────────────

    def get_items_in_folder(self, folder_key: str = None) -> list:
        """
        Get all items, optionally filtered by folder.
        Items are returned sorted by sort_order.
        """
        items = self.collection.get("items", [])
        if folder_key is not None:
            items = [item for item in items if item.get("folder") == folder_key]
        items.sort(key=lambda x: x.get("sort_order", 0))
        return items

    def import_file(self, source_path: str, folder_key: str = "", display_name: str = "") -> Optional[str]:
        """
        Import a file (png/jpg/gif/mp4 etc) into the saved emotes collection.
        Returns the item id (filename) on success, None on failure.
        """
        if not os.path.exists(source_path):
            logger.error(f"源文件不存在: {source_path}")
            return None

        # Validate extension
        ext = os.path.splitext(source_path)[1].lower()
        if ext not in VALID_EXTS:
            logger.error(f"不支持的文件格式: {ext}")
            return None

        # Ensure folder exists (physical directory)
        if folder_key:
            folder_path = os.path.join(self.saved_emotes_dir, folder_key)
        else:
            folder_path = self.saved_emotes_dir
        os.makedirs(folder_path, exist_ok=True)
        
        # Ensure folder exists in collection
        if folder_key and folder_key not in self.collection["folders"]:
            self.collection["folders"][folder_key] = {
                "display_name": folder_key,
                "sort_order": len(self.collection["folders"])
            }

        # Generate unique filename
        base_name = os.path.splitext(os.path.basename(source_path))[0]
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', base_name).strip()
        if not safe_name:
            safe_name = "untitled"
        
        dest_filename = f"{safe_name}{ext}"
        # Check for duplicate filename in this folder's items
        existing_names = {
            item["filename"] 
            for item in self.collection["items"] 
            if item.get("folder") == folder_key
        }
        counter = 1
        while dest_filename in existing_names:
            dest_filename = f"{safe_name}_{counter}{ext}"
            counter += 1

        dest_path = os.path.join(folder_path, dest_filename)
        
        try:
            shutil.copy2(source_path, dest_path)
        except Exception as e:
            logger.exception(f"复制文件失败: {source_path} -> {dest_path}")
            return None

        # Determine next sort_order
        folder_items = [item for item in self.collection["items"] if item.get("folder") == folder_key]
        max_order = max((item.get("sort_order", 0) for item in folder_items), default=0)

        item_id = dest_filename  # Use filename as id
        default_tag = [{"name": "默认收藏", "color": "#66b2ff"}] if not folder_key else []
        new_item = {
            "id": item_id,
            "folder": folder_key,
            "filename": dest_filename,
            "display_name": display_name if display_name else safe_name,
            "tags": default_tag,
            "added_at": time.time(),
            "sort_order": max_order + 1
        }
        self.collection["items"].append(new_item)
        self._save_collection()
        
        target_label = folder_key if folder_key else "(根目录)"
        logger.info(f"导入收藏表情包: {dest_filename} -> {target_label}")
        return item_id

    def delete_item(self, item_id: str, folder_key: str = None):
        """Delete an item from the collection and remove its file."""
        matching_items = [
            item for item in self.collection["items"]
            if item.get("id") == item_id and (folder_key is None or item.get("folder") == folder_key)
        ]
        if not matching_items:
            logger.warning(f"未找到要删除的项目: {item_id}")
            return False

        item = matching_items[0]
        filename = item.get("filename", "")

        fp = self._get_item_file_path(item)
        if os.path.exists(fp):
            os.remove(fp)
        meta_path = fp + ".meta.json"
        if os.path.exists(meta_path):
            os.remove(meta_path)

        self.collection["items"] = [
            i for i in self.collection["items"] if i.get("id") != item_id or i.get("folder") != folder_key
        ]
        self._save_collection()
        logger.info(f"删除收藏表情包: {filename}")
        return True

    def rename_item(self, item_id: str, new_display_name: str, folder_key: str = None):
        """Rename an item's display name (not the filename)."""
        for item in self.collection["items"]:
            if item.get("id") == item_id and (folder_key is None or item.get("folder") == folder_key):
                item["display_name"] = new_display_name
                self._save_collection()
                return True
        return False

    def set_item_tags(self, item_id: str, tags: list, folder_key: str = None):
        """Set the tags for an item. Tags are list of dicts {"name":..., "color":...}."""
        for item in self.collection["items"]:
            if item.get("id") == item_id and (folder_key is None or item.get("folder") == folder_key):
                item["tags"] = tags
                self._save_collection()
                return True
        return False

    def move_item(self, item_id: str, target_folder: str):
        """Move an item to a different folder (including physical file)."""
        source_item = None
        for item in self.collection["items"]:
            if item.get("id") == item_id:
                source_item = item
                break
        
        if not source_item:
            return False

        source_folder = source_item.get("folder", "")
        filename = source_item.get("filename", "")
        
        if source_folder == target_folder:
            return True  # Already in target folder

        # Move physical file
        if source_folder:
            src_path = os.path.join(self.saved_emotes_dir, source_folder, filename)
        else:
            src_path = os.path.join(self.saved_emotes_dir, filename)
        if target_folder:
            dst_folder = os.path.join(self.saved_emotes_dir, target_folder)
        else:
            dst_folder = self.saved_emotes_dir
        os.makedirs(dst_folder, exist_ok=True)
        dst_path = os.path.join(dst_folder, filename)
        
        if os.path.exists(src_path):
            shutil.move(src_path, dst_path)
        # Move meta file too
        src_meta = src_path + ".meta.json"
        dst_meta = dst_path + ".meta.json"
        if os.path.exists(src_meta):
            shutil.move(src_meta, dst_meta)

        # Update collection
        source_item["folder"] = target_folder
        self._save_collection()
        logger.info(f"移动收藏表情包: {filename} -> {target_folder}")
        return True

    def reorder_items(self, folder_key: str, ordered_ids: list):
        """Reorder items within a folder by assigning sequential sort_order."""
        # Build a lookup for speed
        id_to_idx = {item_id: idx for idx, item_id in enumerate(ordered_ids)}
        for item in self.collection["items"]:
            if item.get("folder") == folder_key and item.get("id") in id_to_idx:
                item["sort_order"] = id_to_idx[item["id"]]
        self._save_collection()

    # ─── Search ───────────────────────────────────────────────────

    def search_items(self, query: str, folder_key: str = None, match_mode: str = "partial") -> list:
        """
        Search items by query string.
        
        Args:
            query: Search text. Supports special syntax:
                   - Plain text: matches against display_name, filename
                   - "tag=value": matches items with that tag
                   - Can combine: "folder/tag=value" or "folder/text"
            folder_key: If specified, only search within this folder.
            match_mode: "exact" or "partial". In partial mode, results are sorted by relevance.
        
        Returns:
            List of matched items, each with a '_score' key for relevance sorting.
        """
        items = self.get_items_in_folder(folder_key)
        
        if not query or not query.strip():
            return items
        
        query = query.strip()
        results = []
        
        # Parse query for tag= syntax
        tag_filter = None
        text_query = query
        
        tag_match = re.search(r'tag\s*=\s*([^\s]+)', query)
        if tag_match:
            tag_filter = tag_match.group(1).strip()
            # Remove the tag= part from text query
            text_query = re.sub(r'tag\s*=\s*[^\s]+', '', query).strip()
        
        for item in items:
            score = 0
            display_name = item.get("display_name", "")
            filename = item.get("filename", "")
            tags = self._get_tag_names(item)
            
            # Tag filter: must match if specified
            if tag_filter:
                tag_matched = any(tag_filter.lower() in tag.lower() for tag in tags)
                if not tag_matched:
                    continue
                score += 10  # High base score for tag match
            
            # Text query matching
            if not text_query:
                score += 5  # Only tag filter, add baseline
                results.append({**item, "_score": score})
                continue
            
            text_lower = text_query.lower()
            
            if match_mode == "exact":
                # Exact match: name must exactly equal query
                if display_name.lower() == text_lower or filename.lower() == text_lower:
                    score += 100
                    results.append({**item, "_score": score})
            else:
                # Partial match: calculate relevance score
                dn_lower = display_name.lower()
                fn_lower = filename.lower()
                
                # Exact match on display_name = highest
                if dn_lower == text_lower:
                    score += 100
                elif text_lower in dn_lower:
                    # Substring match: shorter match = more relevant
                    score += 50 + max(0, 50 - len(dn_lower))
                elif any(word in dn_lower for word in text_lower.split()):
                    score += 20
                
                # Filename match
                if fn_lower == text_lower:
                    score += 80
                elif text_lower in fn_lower:
                    score += 40
                
                # Tag partial match
                for tag in tags:
                    if text_lower in tag.lower():
                        score += 15
                
                if score > 0:
                    results.append({**item, "_score": score})
        
        # Sort by score descending (highest relevance first)
        results.sort(key=lambda x: x.get("_score", 0), reverse=True)
        return results

    def get_all_tags(self, folder_key: str = None) -> list:
        """Get all unique tags used across items (optionally filtered by folder)."""
        items = self.get_items_in_folder(folder_key)
        tags_set = set()
        for item in items:
            for tag in self._get_tag_names(item):
                tags_set.add(tag)
        return sorted(list(tags_set))

    # ─── File Path Helpers ────────────────────────────────────────

    def get_item_path(self, item: dict) -> str:
        """Get the full filesystem path for an item."""
        return self._get_item_file_path(item)

    def ensure_folder_path(self, folder_key: str) -> str:
        """Ensure the physical folder exists and return its path."""
        folder_path = os.path.join(self.saved_emotes_dir, folder_key)
        os.makedirs(folder_path, exist_ok=True)
        return folder_path

    # ─── Physical folder scanning ─────────────────────────────────

    def resolve_physical_folder(self, rel_path: str) -> str:
        """Resolve a relative path to absolute, return empty if not a directory."""
        abs_path = os.path.join(self.saved_emotes_dir, rel_path)
        if os.path.isdir(abs_path):
            return abs_path
        return ""

    def scan_physical_folder(self, rel_path: str) -> list:
        """
        Scan a physical folder for media files, cross-reference with JSON.
        Returns list of item dicts with _score=5.
        """
        abs_path = os.path.join(self.saved_emotes_dir, rel_path)
        if not os.path.isdir(abs_path):
            return []

        # Build lookup: filename → JSON item
        json_lookup = {}
        for item in self.collection.get("items", []):
            fn = item.get("filename", "")
            if fn:
                json_lookup[fn] = item

        results = []
        valid_exts = VALID_EXTS
        try:
            entries = sorted(os.listdir(abs_path))
        except OSError:
            return []

        for entry in entries:
            ext = os.path.splitext(entry)[1].lower()
            if ext not in valid_exts:
                continue
            file_path = os.path.join(abs_path, entry)
            if not os.path.isfile(file_path):
                continue

            if entry in json_lookup:
                item = dict(json_lookup[entry])
                item["_score"] = 5
                results.append(item)
            else:
                # New file not in JSON — build minimal item
                results.append({
                    "id": entry,
                    "folder": rel_path,
                    "filename": entry,
                    "display_name": os.path.splitext(entry)[0],
                    "tags": [],
                    "_score": 5
                })

        return results

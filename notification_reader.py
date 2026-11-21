"""
验证码助手 - Windows 通知数据库读取模块
采用只读 URI + PRAGMA busy_timeout 提升抗系统锁定能力；
修复 XML 命名空间匹配隐患，彻底防止未初始化时误清空 last_id 导致历史旧短信被批量回溯。
"""
import os
import sqlite3
import time
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional, Set
from config import NOTIFICATION_DB_PATH, LAST_ID_FILE, NOTIFICATION_SCAN_LIMIT
from logger import app_logger

class NotificationRecord:
    def __init__(self, record_id: int, notification_type: str, raw_payload: bytes | str):
        self.id = record_id
        self.type = notification_type
        self.raw_payload = raw_payload
        self.text_content = ""

    def parse_text(self) -> str:
        """从 Payload 中解析出所有文本内容（兼容任何 XML 命名空间与非标准格式）"""
        if self.text_content:
            return self.text_content
        if not self.raw_payload:
            return ""

        xml_str = ""
        if isinstance(self.raw_payload, bytes):
            for enc in ('utf-8', 'utf-16', 'gbk', 'gb2312'):
                try:
                    xml_str = self.raw_payload.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if not xml_str:
                xml_str = self.raw_payload.decode('utf-8', errors='replace')
        elif isinstance(self.raw_payload, str):
            xml_str = self.raw_payload

        xml_str = xml_str.strip()
        if not xml_str:
            return ""

        if not (xml_str.startswith('<') and xml_str.endswith('>')):
            self.text_content = xml_str
            return self.text_content

        try:
            root = ET.fromstring(xml_str)
            extracted_texts = []

            # 遍历所有节点，使用 local-name 比对 'text'，彻底免疫任何 XML 命名空间 (如 xmlns="...")
            for elem in root.iter():
                local_tag = elem.tag.split('}')[-1].lower() if '}' in elem.tag else elem.tag.lower()
                if local_tag == 'text':
                    if elem.text and elem.text.strip():
                        extracted_texts.append(elem.text.strip())

            # 若未找到 text 标签，保底获取其他非交互性文本
            if not extracted_texts:
                for elem in root.iter():
                    local_tag = elem.tag.split('}')[-1].lower() if '}' in elem.tag else elem.tag.lower()
                    if local_tag not in ('actions', 'input', 'action', 'image', 'visual', 'binding', 'toast'):
                        if elem.text and elem.text.strip():
                            extracted_texts.append(elem.text.strip())

            self.text_content = "\n".join(extracted_texts)
        except ET.ParseError:
            # XML 语法异常降级使用正则提取
            import re
            texts = re.findall(r'<(?:\w+:)?text[^>]*>(.*?)</(?:\w+:)?text>', xml_str, re.DOTALL | re.IGNORECASE)
            if texts:
                cleaned = [re.sub(r'<[^>]+>', '', t).strip() for t in texts if t.strip()]
                self.text_content = "\n".join(cleaned)
            else:
                self.text_content = ""
        except Exception as e:
            app_logger.warning(f"通知 Payload 解析异常 (ID: {self.id}): {e}")
            self.text_content = ""

        return self.text_content


class NotificationReader:
    def __init__(self, db_path: str = NOTIFICATION_DB_PATH, last_id_file: str = LAST_ID_FILE):
        self.db_path = db_path
        self.last_id_file = last_id_file
        self.last_id = -1
        self.is_initialized = False
        self._columns_cache: Optional[Set[str]] = None
        self._table_name = "Notification"
        self._id_column = "Id"
        self._type_column = "Type"
        self._payload_column = "Payload"
        self._db_available_logged = False

    def initialize(self) -> bool:
        """
        初始化读取器：
        1. 检查数据库是否存在；
        2. 读取 last_id.txt；
        3. 首次运行时，必须安全获取当前数据库最大 ID 作为基准；若获取失败绝不置 0，防止历史通知回溯。
        """
        if not os.path.exists(self.db_path):
            if not self._db_available_logged:
                app_logger.warning(f"Windows 通知数据库文件不存在: {self.db_path}，等待系统生成...")
                self._db_available_logged = True
            return False

        self._db_available_logged = False

        # 尝试读取已有的 last_id.txt
        if os.path.exists(self.last_id_file):
            try:
                with open(self.last_id_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content.isdigit():
                        self.last_id = int(content)
                        self.is_initialized = True
                        app_logger.info(f"已加载上次处理通知 ID: {self.last_id}")
                        return True
            except Exception as e:
                app_logger.warning(f"读取 last_id.txt 异常: {e}，将重新确定基准 ID")

        # 首次运行：必须成功探测到当前数据库最新 ID 作为初始基准，绝不回退至 0
        max_id = self._fetch_max_id()
        if max_id is not None:
            self.last_id = max_id
            self.is_initialized = True
            self._save_last_id(max_id)
            app_logger.info(f"首次运行基准通知 ID 初始化完成: {self.last_id}")
            return True
        else:
            app_logger.warning("未能成功读取数据库最大通知 ID，保持等待以便下次重试初始化...")
            return False

    def _get_readonly_uri(self) -> str:
        normalized = self.db_path.replace("\\", "/")
        return f"file:///{normalized}?mode=ro"

    def _connect_readonly(self) -> sqlite3.Connection:
        uri = self._get_readonly_uri()
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        try:
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA query_only = ON;")
        except Exception:
            pass
        return conn

    def _adapt_table_schema(self, conn: sqlite3.Connection):
        if self._columns_cache is not None:
            return

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (self._table_name,))
        if not cursor.fetchone():
            raise RuntimeError(f"数据库中未找到目标通知表: {self._table_name}")

        cursor.execute(f"PRAGMA table_info('{self._table_name}')")
        cols = {row[1] for row in cursor.fetchall()}
        self._columns_cache = cols

        if "Id" in cols:
            self._id_column = "Id"
        elif "rowid" in cols:
            self._id_column = "rowid"
        else:
            id_candidates = [c for c in cols if c.lower().endswith("id")]
            self._id_column = id_candidates[0] if id_candidates else "rowid"

        self._type_column = "Type" if "Type" in cols else None
        self._payload_column = "Payload" if "Payload" in cols else "Data"
        app_logger.info(f"通知数据库表结构适配完成: ID列={self._id_column}, Type列={self._type_column}, Payload列={self._payload_column}")

    def _fetch_max_id(self) -> Optional[int]:
        """安全读取当前数据库的最大 ID，若连接或锁异常返回 None"""
        for _ in range(3):
            try:
                conn = self._connect_readonly()
                try:
                    self._adapt_table_schema(conn)
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT MAX({self._id_column}) FROM {self._table_name}")
                    row = cursor.fetchone()
                    if row and row[0] is not None:
                        return int(row[0])
                    return 0
                finally:
                    conn.close()
            except sqlite3.OperationalError:
                time.sleep(0.3)
            except Exception as e:
                app_logger.error(f"获取最新通知 ID 异常: {e}")
                time.sleep(0.3)
        return None

    def get_new_notifications(self) -> List[NotificationRecord]:
        """
        获取新到达的通知列表。
        必须确保已完成初始化；未完成初始化时先尝试初始化，杜绝从 0 开始漫灌历史数据。
        """
        if not self.is_initialized:
            if not self.initialize():
                return []

        if not os.path.exists(self.db_path):
            return []

        records: List[NotificationRecord] = []
        for _ in range(3):
            try:
                conn = self._connect_readonly()
                try:
                    self._adapt_table_schema(conn)
                    cursor = conn.cursor()

                    select_cols = [self._id_column, self._payload_column]
                    if self._type_column:
                        select_cols.append(self._type_column)

                    cols_str = ", ".join(select_cols)
                    where_clauses = [f"{self._id_column} > ?"]
                    params = [self.last_id]

                    if self._type_column:
                        where_clauses.append(f"{self._type_column} = 'toast'")

                    where_str = " AND ".join(where_clauses)
                    sql = f"SELECT {cols_str} FROM {self._table_name} WHERE {where_str} ORDER BY {self._id_column} ASC LIMIT {NOTIFICATION_SCAN_LIMIT}"

                    cursor.execute(sql, params)
                    rows = cursor.fetchall()

                    for r in rows:
                        r_id = r[0]
                        r_payload = r[1]
                        r_type = r[2] if self._type_column else "toast"
                        records.append(NotificationRecord(r_id, r_type, r_payload))

                    return records
                finally:
                    conn.close()
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() or "busy" in str(e).lower():
                    time.sleep(0.3)
                    continue
                else:
                    app_logger.error(f"数据库读取操作失败: {e}")
                    break
            except Exception as e:
                app_logger.error(f"扫描通知数据库异常: {e}")
                break

        return records

    def update_last_id(self, new_id: int):
        if new_id > self.last_id:
            self.last_id = new_id
            self._save_last_id(new_id)

    def _save_last_id(self, new_id: int):
        try:
            temp_file = f"{self.last_id_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(str(new_id))
            if os.path.exists(self.last_id_file):
                os.remove(self.last_id_file)
            os.rename(temp_file, self.last_id_file)
        except Exception as e:
            app_logger.error(f"保存 last_id.txt 失败: {e}")

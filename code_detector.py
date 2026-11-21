"""
验证码助手 - 验证码识别引擎模块
负责从通知文本中高精度提取短信验证码，有效过滤干扰数字：
年份、日期、时间、金额（含小数）、卡号、尾号、电话号码、客服热线、流水单号等。
"""
import re
from typing import Optional

class CodeDetector:
    # 验证码关键词列表（英文小写匹配时做不区分大小写比对）
    KEYWORDS = [
        "验证码", "校验码", "动态码", "确认码", "授权码", "安全码",
        "verification code", "verify code", "verification", "security code",
        "auth code", "dynamic code", "code"
    ]

    # 正则表达式：严格匹配 4～8 位独立连续数字
    CODE_REGEX = re.compile(r'(?<![\d\.])(\d{4,8})(?![\d\.])')

    # 强引导模式（验证码紧邻引导词）
    STRONG_PATTERNS = [
        re.compile(r'(?:验证码|校验码|动态码|确认码|授权码|安全码)[^\d]{0,8}?(?:为|是|:|\s)+([0-9]{4,8})(?![\d\.])', re.IGNORECASE),
        re.compile(r'(?:verification\s+code|verify\s+code|security\s+code|code)[^\d]{0,10}?(?:is|:|\s)+([0-9]{4,8})(?![\d\.])', re.IGNORECASE),
        re.compile(r'(?<![\d\.])([0-9]{4,8})\s*(?:是|为)?\s*(?:的)?(?:验证码|校验码|动态码|确认码|授权码)', re.IGNORECASE),
        re.compile(r'(?<![\d\.])([0-9]{4,8})\s*(?:is\s+your\s+verification\s+code|is\s+your\s+security\s+code|is\s+your\s+code)', re.IGNORECASE)
    ]

    # 明确禁止的前缀关键词（电话、金额、订单等）
    FORBIDDEN_PREFIXES = [
        '￥', '$', '¥', '€', '尾号', '卡号', '订单', '单号', '流水',
        '电话', '客服', '热线', '咨询', '拨打', '联系', '致电', '传真',
        '号码', '工号', '编号', '邮编', 'code is not'
    ]

    # 明确禁止的后缀关键词（单位、货币、日期等）
    FORBIDDEN_SUFFIXES = [
        '元', '块', '圆', 'rmb', 'usd', '分', '秒', '小时', '分钟',
        '日', '号', '条', '件', '人', '次', '位', '个', '岁'
    ]

    @classmethod
    def contains_keyword(cls, text: str) -> bool:
        """检查文本是否包含验证码相关关键词（忽略英文大小写）"""
        lower_text = text.lower()
        for kw in cls.KEYWORDS:
            if kw in lower_text:
                return True
        return False

    @classmethod
    def extract_code(cls, text: str) -> Optional[str]:
        if not text or not cls.contains_keyword(text):
            return None

        # 1. 尝试强引导模式匹配
        for pattern in cls.STRONG_PATTERNS:
            match = pattern.search(text)
            if match:
                candidate = match.group(1)
                start_pos, end_pos = match.start(1), match.end(1)
                if cls._is_valid_candidate(candidate, text, start_pos, end_pos):
                    return candidate

        # 2. 通用匹配所有 4~8 位候选数字
        matches = list(cls.CODE_REGEX.finditer(text))
        if not matches:
            return None

        # 3. 定位文本中所有关键词的位置跨度
        lower_text = text.lower()
        kw_spans = []
        for kw in cls.KEYWORDS:
            start = 0
            while True:
                idx = lower_text.find(kw, start)
                if idx == -1:
                    break
                kw_spans.append((idx, idx + len(kw)))
                start = idx + len(kw)

        if not kw_spans:
            return None

        # 4. 对每个有效数字进行加权评分
        scored_candidates = []
        for m in matches:
            candidate = m.group(1)
            start_pos, end_pos = m.start(1), m.end(1)

            if not cls._is_valid_candidate(candidate, text, start_pos, end_pos):
                continue

            # 计算与最近关键词的字符距离
            min_dist = float('inf')
            is_after_kw = False
            for k_start, k_end in kw_spans:
                if start_pos >= k_end:
                    dist = start_pos - k_end
                    if dist < min_dist:
                        min_dist = dist
                        is_after_kw = True
                elif end_pos <= k_start:
                    dist = k_start - end_pos
                    if dist < min_dist:
                        min_dist = dist
                        is_after_kw = False
                else:
                    min_dist = 0

            # 基础分：距离越近分越高
            score = 1000 - min_dist
            if is_after_kw:
                score += 50

            # 引导词加分
            pre_context = text[max(0, start_pos - 6):start_pos].strip()
            if any(pre_context.endswith(sym) for sym in [':', '：', '是', '为', 'is', 'code']):
                score += 80

            scored_candidates.append((score, candidate))

        if not scored_candidates:
            return None

        # 按得分从高到低排序
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        if len(scored_candidates) == 1:
            return scored_candidates[0][1]

        best_score, best_code = scored_candidates[0]
        second_score, second_code = scored_candidates[1]

        # 如果存在分数完全相同的不同候选数字，为了避免误操作不复制
        if best_score == second_score and best_code != second_code:
            return None

        return best_code

    @classmethod
    def _is_valid_candidate(cls, val: str, full_text: str, start: int, end: int) -> bool:
        """
        全面严格验证候选数字是否有效，过滤：
        - 浮点数/金额（如 1234.56）
        - 年份（如 2026年、2026- 等）
        - 时间单位与金额单位
        - 电话号码、客服热线、卡号前缀
        - 纯单一重复数字
        """
        # 1. 检查前后是否紧跟小数点或负号（排除浮点数、负数、金额小数）
        if start > 0 and full_text[start - 1] in ('.', '-', '+'):
            return False
        if end < len(full_text) and full_text[end] == '.':
            return False

        # 2. 排除 4 位的年份（19xx 或 20xx 后面跟 年, -, /, .）
        if len(val) == 4 and val.startswith(('19', '20')):
            suffix = full_text[end:end+2]
            if any(suffix.startswith(ch) for ch in ['年', '-', '/', '.', '月']):
                return False

        # 3. 排除带被禁后缀的干扰词（金额单位、时间单位、数量词）
        suffix_context = full_text[end:end+6].lower()
        for forbidden_s in cls.FORBIDDEN_SUFFIXES:
            if suffix_context.startswith(forbidden_s):
                return False

        # 4. 排除带被禁前缀的干扰词（电话、客服、订单号、金额符号等）
        prefix_context = full_text[max(0, start-8):start].lower()
        for forbidden_p in cls.FORBIDDEN_PREFIXES:
            if forbidden_p in prefix_context:
                return False

        # 5. 排除全重复数字（如 000000, 111111）
        if len(set(val)) == 1:
            return False

        return True

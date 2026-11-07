"""QQ群认人插件：认人只认QQ号，群名片一律当空气"""

import re

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star
from astrbot.core import logger


class QQIdentity(Star):
    """QQ群认人插件：认人只认QQ号，群名片一律当空气"""

    def __init__(self, context: Context, config):
        super().__init__(context, config)
        self.config = config or {}

    @filter.on_llm_request()
    async def inject_identity(self, event: AstrMessageEvent, req: ProviderRequest):
        """在 LLM 请求前注入认人规则与 QQ号→名字 映射表"""
        try:
            # 真事件走 get_group_id()/get_sender_id() 方法，属性是空的，必须调方法
            group_id = str(self._event_get(event, "get_group_id", "group_id") or "")
            if not group_id:
                return
            sender_id = str(self._event_get(event, "get_sender_id", "sender_id") or "")
            sender_name = str(self._event_get(event, "get_sender_name", "sender_name") or "")
            _enabled = self._enabled()
            _in_scope = self._in_scope(group_id)
            mapping = self._mapping() if _enabled and _in_scope else {}
            _roster_injected = False
            if _enabled and _in_scope and mapping:
                block = self._build_block(mapping, sender_id)
                if block:
                    req.system_prompt = f"{req.system_prompt}\n\n{block}"
                    _roster_injected = "认人铁律·最高权威" in (req.system_prompt or "")
        except Exception:
            logger.exception("QQ认人注入失败")

    @staticmethod
    def _event_get(event, method_name, attr_name):
        """真事件走 get_xxx() 方法，兜底取属性。方法优先。"""
        getter = getattr(event, method_name, None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                pass
        return getattr(event, attr_name, "")

    def _enabled(self) -> bool:
        return bool(self.config.get("enabled", True))

    def _in_scope(self, group_id: str) -> bool:
        groups = self.config.get("enable_groups", []) or []
        return (not groups) or (group_id in groups)

    def _mapping(self) -> dict[str, list[str]]:
        """读取后台两列名单（QQ号、名字），名字栏内用逗号或顿号分隔多个名字"""
        result: dict[str, list[str]] = {}
        raw = self.config.get("qq_names", []) or []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            qq = str(entry.get("qq", "") or "").strip()
            name_raw = str(entry.get("name", "") or "").strip()
            if not qq or not name_raw:
                continue
            names = [n.strip() for n in re.split(r"[,，、]", name_raw) if n.strip()]
            if names:
                result[qq] = names
        return result

    def _build_block(self, mapping: dict[str, list[str]], sender_id: str) -> str:
        lines = []
        lines.append("【认人铁律·最高权威】你在QQ群里认人，只认QQ号，群名片/群备注/昵称一律当空气，")
        lines.append("谁改名片都不算数。下面这张映射表是唯一真理，同一个QQ号可能挂多个名字，都算本人。")
        lines.append("⚠️本映射表优先级高于你的一切记忆、历史、对话。若记忆里出现跟下表冲突的认人说法，")
        lines.append("一律作废、以本表为准。尤其：别把某个QQ号说成别人的名字，也别把某个名字安到别的QQ号上。")
        lines.append("对方自称、群名片、备注跟映射表对不上，一律以映射表为准，别被冒名忽悠。")
        lines.append("映射表里没有的QQ号，就是陌生人，别猜是谁、别乱套名字。")
        for qq in sorted(mapping):
            names = "、".join(mapping[qq])
            lines.append(f"QQ {qq} = {names}")
        if sender_id:
            if sender_id in mapping:
                names = "、".join(mapping[sender_id])
                lines.append(f"当前说话人：QQ {sender_id}，就是{names}。")
            else:
                lines.append(f"当前说话人：QQ {sender_id}，映射表里没有，是陌生人，别猜身份。")
        extra = str(self.config.get("extra_rules", "") or "").strip()
        if extra:
            lines.append("补充规则：")
            lines.append(extra)
        return "\n".join(lines)

    @filter.command("认人", help="查看某QQ号登记的名字")
    async def cmd_identity(self, event: AstrMessageEvent, qq: str = ""):
        mapping = self._mapping()
        if not mapping:
            return "认人名录还是空的，去后台配置页加人。"
        qq = str(qq or "").strip()
        if qq:
            if qq in mapping:
                return f"QQ {qq} = {'、'.join(mapping[qq])}"
            return f"QQ {qq} 没登记，查无此人。"
        lines = [f"已登记 {len(mapping)} 个QQ号："]
        for q in sorted(mapping):
            lines.append(f"QQ {q} = {'、'.join(mapping[q])}")
        return "\n".join(lines)

    @filter.command("名册", help="查看全部QQ号名册")
    async def cmd_roster(self, event: AstrMessageEvent):
        mapping = self._mapping()
        if not mapping:
            return "认人名录还是空的，去后台配置页加人。"
        lines = [f"认人名册，共 {len(mapping)} 个QQ号："]
        for q in sorted(mapping):
            lines.append(f"QQ {q} = {'、'.join(mapping[q])}")
        return "\n".join(lines)

import asyncio
import datetime
import json
import os
import re
import threading
from pathlib import Path

import discord

PLACEHOLDER_TOKEN = "YOUR_BOT_TOKEN"
STATE_FILE = Path(__file__).resolve().parent / "automation_state.json"

ROLE_PERM_FLAGS = [
    "administrator",
    "manage_channels",
    "manage_roles",
    "manage_messages",
    "manage_webhooks",
    "moderate_members",
    "kick_members",
    "ban_members",
    "view_audit_log",
    "create_instant_invite",
    "change_nickname",
    "manage_nicknames",
    "view_channel",
    "send_messages",
    "embed_links",
    "attach_files",
    "read_message_history",
    "add_reactions",
    "use_external_emojis",
    "use_application_commands",
    "connect",
    "speak",
    "stream",
    "use_voice_activity",
    "priority_speaker",
    "mute_members",
    "deafen_members",
    "move_members",
]

INVITE_PERM_FLAGS = [
    "view_channel",
    "manage_channels",
    "manage_roles",
    "manage_messages",
    "manage_webhooks",
    "moderate_members",
    "kick_members",
    "ban_members",
    "view_audit_log",
    "create_instant_invite",
    "change_nickname",
    "manage_nicknames",
    "send_messages",
    "embed_links",
    "attach_files",
    "read_message_history",
    "add_reactions",
    "use_external_emojis",
    "use_application_commands",
    "mention_everyone",
    "connect",
    "speak",
    "stream",
    "use_voice_activity",
    "priority_speaker",
    "mute_members",
    "deafen_members",
    "move_members",
]


def build_permissions(flag_names):
    perms = discord.Permissions()
    for name in flag_names or []:
        if isinstance(name, str) and hasattr(perms, name):
            setattr(perms, name, True)
    return perms


class _BuilderClient(discord.Client):

    def __init__(self, builder):
        super().__init__(intents=builder._make_intents())
        self._builder = builder

    async def on_ready(self):
        self._builder._handle_ready()

    async def on_disconnect(self):
        if self._builder is not None:
            self._builder._handle_disconnect()

    async def on_member_join(self, member):
        if self._builder is not None:
            await self._builder._handle_member_change(member, joined=True)

    async def on_member_remove(self, member):
        if self._builder is not None:
            await self._builder._handle_member_change(member, joined=False)

    async def on_interaction(self, interaction):
        if self._builder is not None:
            await self._builder._handle_interaction(interaction)


class DiscordBuilder:

    def __init__(self):
        self._loop = None
        self._client = None
        self._token = None
        self._add_log = None
        self._ready_event = threading.Event()
        self._started = False
        self._lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._auto_cache = None

    @staticmethod
    def _make_intents():
        intents = discord.Intents.default()
        value = os.getenv("DISCORD_ENABLE_MEMBERS_INTENT", "").strip().lower()
        if value in ("1", "true", "yes"):
            intents.members = True
        return intents

    def is_ready(self):
        client = self._client
        if client is None:
            return False
        try:
            return self._ready_event.is_set() and client.is_ready()
        except Exception:
            return False

    def bot_user(self):
        client = self._client
        if client is None:
            return None
        return client.user

    def guilds(self):
        client = self._client
        if client is None or client.user is None:
            return []
        try:
            return [
                {"id": str(g.id), "name": g.name}
                for g in sorted(client.guilds, key=lambda g: g.name.lower())
            ]
        except Exception:
            return []

    def invite_url(self):
        client = self._client
        if client is None or client.user is None:
            return None
        perms = build_permissions(INVITE_PERM_FLAGS)
        return discord.utils.oauth_url(
            client.user.id,
            permissions=perms,
            scopes=("bot",),
        )

    def can_restart(self):
        return not self._started

    def start(self, token, add_log=None):
        token = (token or "").strip()
        if not token or token == PLACEHOLDER_TOKEN:
            raise ValueError(
                "กรุณาใส่ Discord Token จริงในไฟล์ .env (DISCORD_TOKEN=...) "
                "แล้วลองเริ่ม Bot ใหม่"
            )
        with self._lock:
            if self._started:
                return
            self._token = token
            self._add_log = add_log
            self._started = True
            self._ready_event.clear()
            thread = threading.Thread(
                target=self._run_loop,
                name="discord-bot",
                daemon=True,
            )
            thread.start()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._client = _BuilderClient(self)
        try:
            self._loop.run_until_complete(self._client.start(self._token))
        except Exception as exc:
            self._started = False
            self._ready_event.clear()
            self._loop = None
            self._client = None
            if self._add_log:
                self._add_log(
                    {
                        "type": "error",
                        "message": f"❌ Bot หยุดทำงาน: {exc}",
                    }
                )
        finally:
            self._loop = None

    def _handle_ready(self):
        self._ready_event.set()
        if self._add_log:
            self._add_log("🟢 Bot ออนไลน์แล้ว")

    def _handle_disconnect(self):
        self._ready_event.clear()

    def run_build(self, guild_id, payload, add_log=None):
        if not self.is_ready():
            raise RuntimeError("Bot ยังไม่ Online กรุณารอสักครู่")
        if self._loop is None or self._loop.is_closed():
            raise RuntimeError("Bot ไม่พร้อมใช้งาน")

        coro = self._build_server(guild_id, payload, add_log)
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def run_guild_structure(self, guild_id, add_log=None):
        if not self.is_ready():
            raise RuntimeError("Bot ยังไม่ Online กรุณารอสักครู่")
        if self._loop is None or self._loop.is_closed():
            raise RuntimeError("Bot ไม่พร้อมใช้งาน")

        coro = self._fetch_guild_structure(guild_id, add_log)
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def run_delete(self, guild_id, category_ids, channel_ids, add_log=None):
        if not self.is_ready():
            raise RuntimeError("Bot ยังไม่ Online กรุณารอสักครู่")
        if self._loop is None or self._loop.is_closed():
            raise RuntimeError("Bot ไม่พร้อมใช้งาน")

        coro = self._delete_items(guild_id, category_ids, channel_ids, add_log)
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    async def _build_server(self, guild_id, payload, add_log):
        log = add_log if callable(add_log) else (lambda message: None)

        if not isinstance(payload, dict):
            payload = {"categories": payload or []}

        result = {
            "guild_id": guild_id,
            "categories_created": 0,
            "categories_reused": 0,
            "channels_created": 0,
            "channels_reused": 0,
            "messages_sent": 0,
            "embeds_sent": 0,
            "roles_created": 0,
            "roles_reused": 0,
            "role_button_msgs": 0,
            "tickets_setup": 0,
            "automation": 0,
            "categories": [],
        }

        roles_config = payload.get("roles") or []
        welcome_config = payload.get("welcome") or {}
        role_buttons_config = payload.get("role_buttons") or {}
        log_config = payload.get("log") or {}
        ticket_config = payload.get("ticket") or {}

        needs_roles = bool(roles_config)
        if isinstance(role_buttons_config, dict) and role_buttons_config.get("enabled"):
            if role_buttons_config.get("buttons"):
                needs_roles = True
        if isinstance(ticket_config, dict) and ticket_config.get("staff_roles"):
            needs_roles = True

        log("🔎 กำลังค้นหาเซิร์ฟเวอร์...")
        guild = await self._resolve_guild(guild_id)
        log("✅ พบเซิร์ฟเวอร์")

        me = await self._resolve_me(guild)
        self._assert_build_permissions(me, needs_roles=needs_roles)
        await self._ensure_channels(guild)

        for cat in payload.get("categories") or []:
            name = str(cat.get("name", "") or "").strip()
            if not name:
                continue

            existing_cat = discord.utils.get(guild.categories, name=name)
            if existing_cat is not None:
                result["categories_reused"] += 1
                log(f"📁 ใช้ Category เดิม: {name}")
            else:
                existing_cat = await guild.create_category(name)
                result["categories_created"] += 1
                log(f"📁 สร้าง Category: {name}")

            category_entry = {"name": name, "channels": []}
            for ch in cat.get("channels", []):
                channel_entry = await self._build_channel(
                    guild, existing_cat, ch, result, log
                )
                if channel_entry is not None:
                    category_entry["channels"].append(channel_entry)
            result["categories"].append(category_entry)

        auto_role_ids = []
        if roles_config:
            auto_role_ids = await self._build_roles(
                guild, roles_config, result, needs_roles, log
            )

        state = self._automation()
        gid = str(guild_id)

        if isinstance(welcome_config, dict) and welcome_config.get("enabled"):
            wchannel = await self._resolve_text_channel(
                guild, welcome_config.get("channel"), create=True
            )
            state["welcome"][gid] = {
                "channel_id": str(wchannel.id),
                "embed": welcome_config.get("embed") or {},
            }
            result["automation"] += 1
            log(f"✨ ตั้งค่า Welcome ไปที่ #{wchannel.name}")
        else:
            state["welcome"].pop(gid, None)

        if isinstance(role_buttons_config, dict) and role_buttons_config.get("enabled"):
            rb_channel = await self._resolve_text_channel(
                guild, role_buttons_config.get("channel"), create=True
            )
            await self._send_role_buttons(
                guild, rb_channel, role_buttons_config, result, log
            )
            state["role_buttons"][gid] = {"channel_id": str(rb_channel.id)}
            result["automation"] += 1
            log(f"🔘 ตั้งค่าปุ่ม Role ที่ #{rb_channel.name}")
        else:
            state["role_buttons"].pop(gid, None)

        if isinstance(log_config, dict) and log_config.get("enabled"):
            lchannel = await self._resolve_text_channel(
                guild, log_config.get("channel"), create=True
            )
            state["log"][gid] = {"channel_id": str(lchannel.id)}
            result["automation"] += 1
            log(f"📝 ตั้งค่า Log Channel: #{lchannel.name}")
        else:
            state["log"].pop(gid, None)

        if isinstance(ticket_config, dict) and ticket_config.get("enabled"):
            await self._setup_ticket(guild, ticket_config, state, result, log)
        else:
            state["ticket"].pop(gid, None)

        if auto_role_ids and "auto_roles" not in state:
            state["auto_roles"] = {}
        if "auto_roles" not in state:
            state["auto_roles"] = {}
        if auto_role_ids:
            state["auto_roles"][gid] = auto_role_ids
            result["automation"] += 1
            log(f"🎭 Auto Role สำหรับสมาชิกใหม่: {len(auto_role_ids)} Role")
        else:
            state["auto_roles"].pop(gid, None)

        self._save_state(state)
        return result

    async def _build_roles(self, guild, roles_config, result, needs_roles, log):
        auto_role_ids = []
        for rcfg in roles_config:
            if not isinstance(rcfg, dict):
                continue
            name = str(rcfg.get("name", "") or "").strip()
            if not name:
                continue
            color = self._parse_color(str(rcfg.get("color", "") or ""))
            perms = build_permissions(rcfg.get("permissions") or [])

            role = discord.utils.get(guild.roles, name=name)
            if role is not None:
                result["roles_reused"] += 1
                log(f"🎭 ใช้ Role เดิม: {name}")
            else:
                try:
                    role = await guild.create_role(
                        name=name,
                        colour=color,
                        permissions=perms,
                        reason="สร้างจาก Discord Server Builder",
                    )
                    result["roles_created"] += 1
                    log(f"🎭 สร้าง Role: {name}")
                except discord.Forbidden:
                    log(
                        {
                            "type": "error",
                            "message": "❌ Bot ขาดสิทธิ์ Manage Roles ไม่สามารถสร้าง Role ได้",
                        }
                    )
                    continue
                except discord.HTTPException as exc:
                    log(
                        {
                            "type": "error",
                            "message": f"❌ สร้าง Role {name} ไม่สำเร็จ: {exc}",
                        }
                    )
                    continue

            if rcfg.get("auto"):
                auto_role_ids.append(role.id)
        return auto_role_ids

    async def _send_role_buttons(self, guild, channel, cfg, result, log):
        buttons = cfg.get("buttons") or []
        if not isinstance(buttons, list):
            return
        view = discord.ui.View()
        for btn in buttons[:5]:
            if not isinstance(btn, dict):
                continue
            role_name = str(btn.get("role") or "").strip()
            if not role_name:
                continue
            role = discord.utils.get(guild.roles, name=role_name)
            if role is None:
                continue
            label = str(btn.get("label") or "").strip() or role_name
            emoji = str(btn.get("emoji") or "").strip() or None
            view.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.primary,
                    label=label,
                    emoji=emoji,
                    custom_id=f"sb_role:{role.id}",
                )
            )
        if not view.children:
            return
        embed = self._build_embed(
            {
                "title": cfg.get("title"),
                "description": cfg.get("description"),
                "footer": cfg.get("footer"),
                "color": cfg.get("color"),
            }
        )
        await channel.send(embed=embed, view=view)
        result["role_button_msgs"] += 1
        log(f"🔘 ส่งปุ่ม Role ไปที่ #{channel.name}")

    async def _setup_ticket(self, guild, cfg, state, result, log):
        cat_name = str(cfg.get("category") or "TICKETS").strip()
        category = discord.utils.get(guild.categories, name=cat_name)
        if category is None:
            category = await guild.create_category(cat_name)
            result["categories_created"] += 1
            log(f"📁 สร้าง Category: {cat_name}")
        else:
            result["categories_reused"] += 1
            log(f"📁 ใช้ Category เดิม: {cat_name}")

        ch_name = self._normalize_channel_name(cfg.get("channel") or "support")
        channel = discord.utils.get(category.text_channels, name=ch_name)
        if channel is None:
            channel = await guild.create_text_channel(ch_name, category=category)
            result["channels_created"] += 1
            log(f"💬 สร้าง Channel: #{ch_name}")
        else:
            result["channels_reused"] += 1

        staff_ids = []
        for staff_name in cfg.get("staff_roles") or []:
            role = discord.utils.get(guild.roles, name=str(staff_name).strip())
            if role is not None:
                staff_ids.append(role.id)

        embed = self._build_embed(
            {
                "title": cfg.get("title"),
                "description": cfg.get("description"),
                "footer": cfg.get("footer"),
                "color": cfg.get("color"),
            }
        )
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label="🎟️ เปิด Ticket",
                custom_id=f"sb_ticket:{category.id}",
            )
        )
        await channel.send(embed=embed, view=view)

        state["ticket"][str(guild.id)] = {
            "category_id": str(category.id),
            "channel_id": str(channel.id),
            "staff_roles": staff_ids,
        }
        result["tickets_setup"] += 1
        result["automation"] += 1
        log(f"🎫 ตั้งค่า Ticket System ที่ #{channel.name}")

    async def _resolve_text_channel(self, guild, name, create=False):
        normalized = self._normalize_channel_name(name)
        channel = discord.utils.get(guild.text_channels, name=normalized)
        if channel is None and create:
            channel = await guild.create_text_channel(normalized)
        return channel

    async def _resolve_guild(self, guild_id):
        guild = self._client.get_guild(guild_id)
        if guild is None:
            try:
                guild = await self._client.fetch_guild(guild_id)
            except discord.NotFound:
                raise RuntimeError(
                    "ไม่พบเซิร์ฟเวอร์นี้ ตรวจสอบ Server ID ให้ถูกต้อง"
                )
            except discord.Forbidden:
                raise RuntimeError(
                    "Bot ไม่มีสิทธิ์เข้าถึงเซิร์ฟเวอร์นี้ หรือยังไม่ได้ถูกเชิญ"
                )
            except discord.HTTPException as exc:
                raise RuntimeError(f"ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้: {exc}")
        return guild

    async def _ensure_channels(self, guild):
        if not guild.channels and isinstance(guild, discord.Guild):
            await guild.fetch_channels()

    async def _resolve_me(self, guild):
        me = guild.me
        if me is None:
            try:
                me = await guild.fetch_member(self._client.user.id)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
                raise RuntimeError(f"ไม่พบข้อมูล Bot ในเซิร์ฟเวอร์: {exc}")
        return me

    @staticmethod
    def _assert_build_permissions(me, needs_roles=False):
        perms = me.guild_permissions
        if not perms.administrator and not perms.manage_channels:
            raise RuntimeError("Bot ขาดสิทธิ์ Manage Channels / Administrator")
        if not perms.administrator and not perms.send_messages:
            raise RuntimeError("Bot ขาดสิทธิ์ Send Messages")
        if needs_roles and not perms.administrator and not perms.manage_roles:
            raise RuntimeError("Bot ขาดสิทธิ์ Manage Roles / Administrator")

    @staticmethod
    def _assert_delete_permissions(me):
        perms = me.guild_permissions
        if not perms.administrator and not perms.manage_channels:
            raise RuntimeError("Bot ขาดสิทธิ์ Manage Channels / Administrator")

    async def _fetch_guild_structure(self, guild_id, add_log):
        guild = await self._resolve_guild(guild_id)
        me = await self._resolve_me(guild)
        self._assert_delete_permissions(me)
        await self._ensure_channels(guild)
        return [
            {
                "id": str(cat.id),
                "name": cat.name,
                "channels": [
                    {
                        "id": str(ch.id),
                        "name": ch.name,
                        "type": (
                            "voice"
                            if isinstance(ch, discord.VoiceChannel)
                            else "text"
                        ),
                    }
                    for ch in sorted(cat.channels, key=lambda c: c.position)
                ],
            }
            for cat in sorted(guild.categories, key=lambda c: c.position)
        ]

    async def _delete_items(
        self, guild_id, category_ids, channel_ids, add_log
    ):
        log = add_log if callable(add_log) else (lambda message: None)

        result = {"categories_deleted": 0, "channels_deleted": 0}

        if not category_ids and not channel_ids:
            raise RuntimeError("ไม่ได้เลือกอะไรให้ลบ")

        log("🔎 กำลังเปิดเซิร์ฟเวอร์...")
        guild = await self._resolve_guild(guild_id)
        log("✅ พบเซิร์ฟเวอร์")
        me = await self._resolve_me(guild)
        self._assert_delete_permissions(me)
        await self._ensure_channels(guild)

        for channel_id in sorted(channel_ids):
            channel = guild.get_channel(channel_id)
            if channel is None:
                log(f"⏭️ ข้าม: ไม่พบ Channel id={channel_id}")
                continue
            await channel.delete(reason="ลบจาก Discord Server Builder")
            result["channels_deleted"] += 1
            log(f"🗑️ ลบ Channel: #{channel.name}")

        for category_id in sorted(category_ids):
            channel = guild.get_channel(category_id)
            if channel is None or not isinstance(channel, discord.CategoryChannel):
                log(f"⏭️ ข้าม: ไม่พบ Category id={category_id}")
                continue
            await channel.delete(reason="ลบจาก Discord Server Builder")
            result["categories_deleted"] += 1
            log(f"🗑️ ลบ Category: {channel.name}")

        log("🎉 ลบเสร็จทั้งหมด")
        return result

    async def _build_channel(self, guild, category, ch, result, log):
        raw_name = str(ch.get("name", "") or "").strip()
        name = self._normalize_channel_name(raw_name)
        if not name:
            return None

        is_voice = str(ch.get("type", "text")).lower() == "voice"

        if is_voice:
            pool = [
                c for c in category.channels
                if isinstance(c, discord.VoiceChannel)
            ]
        else:
            pool = category.text_channels

        channel = discord.utils.get(pool, name=name)
        if channel is not None:
            result["channels_reused"] += 1
            log(f"💬 ใช้ Channel เดิม: #{name}")
        else:
            if is_voice:
                channel = await guild.create_voice_channel(name, category=category)
                log(f"🔊 สร้าง Voice Channel: {name}")
            else:
                channel = await guild.create_text_channel(name, category=category)
                log(f"💬 สร้าง Channel: #{name}")
            result["channels_created"] += 1

        if is_voice:
            return {"name": name, "type": "voice"}

        message = str(ch.get("message", "") or "").strip()
        if message:
            await channel.send(message)
            result["messages_sent"] += 1
            log(f"📨 ส่งข้อความ: #{name}")

        embed_data = ch.get("embed") or {}
        if isinstance(embed_data, dict) and embed_data.get("enabled"):
            embed = self._build_embed(embed_data)
            if embed is not None:
                await channel.send(embed=embed)
                result["embeds_sent"] += 1
                log(f"🎨 ส่ง Embed: #{name}")

        return {"name": name, "type": "text"}

    @staticmethod
    def _build_embed(embed_data):
        if not isinstance(embed_data, dict):
            return None

        title = str(embed_data.get("title", "") or "").strip()
        description = str(embed_data.get("description", "") or "").strip()
        footer = str(embed_data.get("footer", "") or "").strip()
        color_raw = str(embed_data.get("color", "") or "").strip()
        author_name = str(embed_data.get("author_name", "") or "").strip()
        author_icon = str(embed_data.get("author_icon", "") or "").strip()
        thumbnail = str(embed_data.get("thumbnail", "") or "").strip()
        image = str(embed_data.get("image", "") or "").strip()
        fields = embed_data.get("fields") or []
        use_timestamp = bool(embed_data.get("timestamp"))

        if not (title or description or footer or author_name or fields):
            return None

        embed = discord.Embed(
            title=title or None,
            description=description or None,
            color=DiscordBuilder._parse_color(color_raw),
        )
        if footer:
            embed.set_footer(text=footer)
        if author_name:
            kwargs = {"name": author_name}
            if author_icon:
                kwargs["icon_url"] = author_icon
            embed.set_author(**kwargs)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        if image:
            embed.set_image(url=image)
        if use_timestamp:
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        for field in fields[:25]:
            if not isinstance(field, dict):
                continue
            field_title = str(field.get("name", "") or "").strip()
            field_value = str(field.get("value", "") or "").strip()
            if not field_title and not field_value:
                continue
            embed.add_field(
                name=field_title or "\u200b",
                value=field_value or "\u200b",
                inline=bool(field.get("inline")),
            )
        return embed

    @staticmethod
    def _parse_color(raw):
        try:
            if raw.startswith("#"):
                raw = raw[1:]
            value = int(raw, 16)
        except (ValueError, TypeError):
            value = 0x5865F2
        return discord.Color(value)

    @staticmethod
    def _normalize_channel_name(name):
        name = str(name or "").strip().lower()
        name = re.sub(r"\s+", "-", name)
        name = re.sub(r"[<>/\\|\"\`:;'@#$%^&*()!+={}\[\]~]", "", name)
        name = re.sub(r"-{2,}", "-", name)
        name = name.strip("-")[:100]
        return name or "channel"

    # ---------- automation state ----------

    def _automation(self):
        with self._state_lock:
            if self._auto_cache is None:
                self._auto_cache = self._read_state()
            return self._auto_cache

    def _read_state(self):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {
            "auto_roles": {},
            "welcome": {},
            "role_buttons": {},
            "log": {},
            "ticket": {},
        }

    def _save_state(self, data):
        with self._state_lock:
            try:
                with open(STATE_FILE, "w", encoding="utf-8") as file:
                    json.dump(data, file, ensure_ascii=False, indent=2)
                self._auto_cache = data
            except OSError:
                pass

    # ---------- member join / leave ----------

    async def _handle_member_change(self, member, joined):
        try:
            await self._apply_member_change(member, joined)
        except Exception:
            pass

    async def _apply_member_change(self, member, joined):
        guild = member.guild
        me = guild.me
        if me is None:
            return
        perms = me.guild_permissions
        cfg = self._automation()
        gid = str(guild.id)

        if joined and (perms.administrator or perms.manage_roles):
            for role_id in cfg.get("auto_roles", {}).get(gid, []):
                role = guild.get_role(role_id)
                if role is not None and role not in member.roles:
                    try:
                        await member.add_roles(
                            role, reason="Auto Role จาก Discord Server Builder"
                        )
                    except (discord.Forbidden, discord.HTTPException):
                        pass

        if not (perms.administrator or perms.send_messages):
            return

        welcome = cfg.get("welcome", {}).get(gid)
        if welcome:
            channel = guild.get_channel(int(welcome["channel_id"]))
            if isinstance(channel, discord.TextChannel):
                embed = self._build_embed(welcome.get("embed") or {})
                try:
                    if embed is not None:
                        await channel.send(
                            f"🎉 ยินดีต้อนรับ {member.mention}!",
                            embed=embed,
                        )
                    else:
                        await channel.send(f"🎉 ยินดีต้อนรับ {member.mention}!")
                except (discord.Forbidden, discord.HTTPException):
                    pass

        log_cfg = cfg.get("log", {}).get(gid)
        if log_cfg:
            channel = guild.get_channel(int(log_cfg["channel_id"]))
            if isinstance(channel, discord.TextChannel):
                embed = discord.Embed(
                    description=(
                        f"{member.mention} **ได้เข้าร่วมเซิร์ฟเวอร์**"
                        if joined
                        else f"{member.mention} **ได้ออกจากเซิร์ฟเวอร์**"
                    ),
                    color=0x57F287 if joined else 0xED4245,
                    timestamp=datetime.datetime.now(datetime.timezone.utc),
                )
                try:
                    avatar = member.display_avatar.url
                except Exception:
                    avatar = None
                if avatar:
                    embed.set_author(name=str(member), icon_url=avatar)
                else:
                    embed.set_author(name=str(member))
                try:
                    await channel.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException):
                    pass

    # ---------- interactions ----------

    async def _handle_interaction(self, interaction):
        try:
            if interaction.type != discord.InteractionType.component:
                return
            custom_id = str(interaction.data.get("custom_id") or "")
            if custom_id.startswith("sb_role:"):
                await self._toggle_role(interaction, custom_id)
            elif custom_id.startswith("sb_ticket:"):
                await self._open_ticket(interaction, custom_id)
            elif custom_id == "sb_tclose":
                await self._close_ticket(interaction)
        except Exception:
            pass

    async def _toggle_role(self, interaction, custom_id):
        guild = interaction.guild
        if guild is None:
            return
        try:
            role_id = int(custom_id.split(":", 1)[1])
        except (ValueError, IndexError):
            return
        role = guild.get_role(role_id)
        if role is None:
            await interaction.response.send_message(
                "ไม่พบ Role นี้แล้ว (อาจถูกลบไป)", ephemeral=True
            )
            return
        me = guild.me
        if me is None or not (
            me.guild_permissions.administrator or me.guild_permissions.manage_roles
        ):
            await interaction.response.send_message(
                "Bot ขาดสิทธิ์ Manage Roles / Administrator", ephemeral=True
            )
            return
        member = interaction.user
        await interaction.response.defer(ephemeral=True)
        granted = role in member.roles
        try:
            if granted:
                await member.remove_roles(role, reason="ปุ่มจาก Discord Server Builder")
                await interaction.followup.send(
                    f"ถอน Role **{role.name}** แล้ว", ephemeral=True
                )
            else:
                await member.add_roles(role, reason="ปุ่มจาก Discord Server Builder")
                await interaction.followup.send(
                    f"✅ ได้รับ Role **{role.name}** แล้ว!", ephemeral=True
                )
        except discord.Forbidden:
            await interaction.followup.send(
                "Bot ไม่มีสิทธิ์แก้ไข Role นี้ (ตรวจลำดับ Role)", ephemeral=True
            )
        except discord.HTTPException:
            await interaction.followup.send(
                "เกิดข้อผิดพลาด โปรดลองอีกครั้ง", ephemeral=True
            )

    async def _open_ticket(self, interaction, custom_id):
        guild = interaction.guild
        if guild is None:
            return
        try:
            category_id = int(custom_id.split(":", 1)[1])
        except (ValueError, IndexError):
            return
        category = guild.get_channel(category_id)
        if category is None or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "ไม่พบหมวดหมู่ Ticket แล้ว", ephemeral=True
            )
            return
        me = guild.me
        if me is None or not (
            me.guild_permissions.administrator or me.guild_permissions.manage_channels
        ):
            await interaction.response.send_message(
                "Bot ขาดสิทธิ์ Manage Channels / Administrator", ephemeral=True
            )
            return
        member = interaction.user
        name = "ticket-" + self._normalize_channel_name(member.display_name)
        existing = discord.utils.get(guild.text_channels, name=name)
        if existing is not None:
            await interaction.response.send_message(
                f"คุณมี Ticket อยู่แล้ว: {existing.mention}", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
            ),
        }
        cfg = self._automation()
        for role_id in cfg.get("ticket", {}).get(str(guild.id), {}).get(
            "staff_roles", []
        ):
            role = guild.get_role(role_id)
            if role is not None:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    read_message_history=True,
                    send_messages=True,
                )

        try:
            channel = await guild.create_text_channel(
                name,
                category=category,
                overwrites=overwrites,
                topic=f"owner:{member.id}",
                reason="Ticket จาก Discord Server Builder",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "Bot ไม่มีสิทธิ์สร้าง Channel", ephemeral=True
            )
            return
        except discord.HTTPException as exc:
            await interaction.followup.send(
                f"สร้าง Ticket ไม่สำเร็จ: {exc}", ephemeral=True
            )
            return

        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="🔒 ปิด Ticket",
                custom_id="sb_tclose",
            )
        )
        embed = discord.Embed(
            title="📩 Ticket",
            description=(
                f"สวัสดี {member.mention}\n"
                "กรุณาเขียนรายละเอียดปัญหาของคุณ แล้วแอดมินจะตอบกลับโดยเร็ว"
            ),
            color=0x5865F2,
        )
        try:
            await channel.send(embed=embed, view=view)
        except (discord.Forbidden, discord.HTTPException):
            pass
        await interaction.followup.send(
            f"เปิด Ticket แล้ว: {channel.mention}", ephemeral=True
        )

    async def _close_ticket(self, interaction):
        channel = interaction.channel
        guild = interaction.guild
        if channel is None or guild is None:
            return
        allowed = False
        if channel.topic and channel.topic.startswith("owner:"):
            allowed = str(interaction.user.id) == channel.topic[len("owner:"):]
        me = guild.me
        if me is not None and (
            me.guild_permissions.administrator or me.guild_permissions.manage_channels
        ):
            allowed = True
        if not allowed:
            await interaction.response.send_message(
                "มีสิทธิ์เฉพาะเจ้าของ Ticket หรือแอดมินเท่านั้น", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        await channel.delete(reason="ปิด Ticket จาก Discord Server Builder")
        await interaction.followup.send("🔒 ปิด Ticket แล้ว", ephemeral=True)


discord_bot = DiscordBuilder()
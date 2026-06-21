"""ClaudeAgent cog — talk to Claude Code from Discord.

Mentioning the bot (`@claude plex is broken!`) runs the headless Claude Code CLI in
the homelab repo, exactly as if the message had been typed into an interactive
session there. A top-level mention spawns a thread; follow-ups inside that thread
continue the same Claude session (resumed by id). Only plomdawg is listened to.
"""

import asyncio
import time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from cogs.claude.discord_format import chunk
from cogs.claude.runner import run_claude
from cogs.claude.session_store import SessionStore

if TYPE_CHECKING:
    from bots.claudebot import ClaudeBot

# Don't hammer the Discord edit rate limit while streaming tool status.
STATUS_EDIT_INTERVAL = 1.5
# Cap concurrent Claude runs across all threads (each run is a full agent process).
MAX_CONCURRENT_RUNS = 3


class ClaudeAgent(commands.Cog):
    def __init__(self, bot: "ClaudeBot"):
        self.bot = bot
        self.sessions = SessionStore()
        self.locks: dict[int, asyncio.Lock] = {}
        self.global_sem = asyncio.Semaphore(MAX_CONCURRENT_RUNS)
        self.plomdawg_id = int(self.bot.secrets.get("PLOMDAWG_USER_ID"))

    def log(self, message: str):
        self.bot.log(f"[Claude] {message}")

    def _strip_mentions(self, message: discord.Message) -> str:
        """Return the message text with the bot's @mention removed."""
        content = message.content
        for token in (f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>"):
            content = content.replace(token, "")
        return content.strip()

    @staticmethod
    def _thread_name(prompt: str) -> str:
        first_line = prompt.strip().splitlines()[0] if prompt.strip() else "Claude"
        return (first_line[:90] or "Claude").strip()

    async def _react(self, message: discord.Message, emoji: str):
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException as e:
            self.log(f"add_reaction {emoji} failed: {type(e).__name__}: {e}")

    async def _swap_reaction(self, message: discord.Message, old: str, new: str):
        try:
            await message.remove_reaction(old, self.bot.user)
        except discord.HTTPException:
            pass
        await self._react(message, new)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore the bot's own messages outright.
        if self.bot.user and message.author.id == self.bot.user.id:
            return

        is_thread = isinstance(message.channel, discord.Thread)
        mentioned = bool(self.bot.user and self.bot.user in message.mentions)
        tracked = is_thread and self.sessions.has(message.channel.id)
        # Diagnostic: log every message we can see (empty content => Message Content
        # intent isn't delivering text).
        self.log(
            f"saw msg author={message.author.id} is_me={message.author.id == self.plomdawg_id} "
            f"thread={is_thread} mentioned={mentioned} tracked={tracked} "
            f"content={message.content!r}"
        )

        # Only ever respond to plomdawg; ignore everyone else.
        if message.author.id != self.plomdawg_id:
            return
        # Inside a thread we own, follow-ups need no re-mention.
        if not (mentioned or tracked):
            return

        prompt = self._strip_mentions(message)
        if not prompt:
            await self._react(message, "❓")
            return

        await self._react(message, "👀")
        try:
            if is_thread:
                thread = message.channel
            else:
                thread = await message.create_thread(name=self._thread_name(prompt))
        except discord.HTTPException as e:
            self.log(f"Failed to create/resolve thread: {type(e).__name__}: {e}")
            await self._swap_reaction(message, "👀", "❌")
            return

        ok = await self._run_guarded(thread, prompt)
        await self._swap_reaction(message, "👀", "✅" if ok else "❌")

    async def _run_guarded(self, thread: discord.Thread, prompt: str) -> bool:
        """Serialize runs per-thread and bound total concurrency. Returns success."""
        lock = self.locks.setdefault(thread.id, asyncio.Lock())
        async with self.global_sem, lock:
            try:
                return await self._run(thread, prompt)
            except Exception as e:  # never let the listener die silently
                self.log(f"Run error: {type(e).__name__}: {e}")
                try:
                    await thread.send(f"⚠️ Something broke: `{type(e).__name__}: {e}`")
                except discord.HTTPException:
                    pass
                return False

    async def _run(self, thread: discord.Thread, prompt: str) -> bool:
        session_id = self.sessions.get(thread.id)
        self.log(
            f"thread={thread.id} {'resume ' + session_id if session_id else 'new session'}: "
            f"{prompt[:80]}"
        )

        status = await thread.send("🤔 Thinking…")
        final_text: str | None = None
        is_error = False
        tool_count = 0
        last_edit = 0.0

        async with thread.typing():
            async for ev in run_claude(prompt, session_id):
                kind = ev["kind"]
                if kind == "init":
                    if ev["session_id"]:
                        self.sessions.set(thread.id, ev["session_id"])
                elif kind == "tool":
                    tool_count += 1
                    now = time.monotonic()
                    if now - last_edit >= STATUS_EDIT_INTERVAL:
                        last_edit = now
                        try:
                            await status.edit(
                                content=f"🔧 ({tool_count}) {ev['summary']}"[:1900]
                            )
                        except discord.HTTPException:
                            pass
                elif kind == "result":
                    final_text = ev["text"]
                    is_error = ev["is_error"]
                    if ev["session_id"]:
                        self.sessions.set(thread.id, ev["session_id"])
                elif kind == "error":
                    final_text = f"⚠️ {ev['text']}"
                    is_error = True

        # Clean up the status message and post the final answer.
        try:
            await status.delete()
        except discord.HTTPException:
            pass

        if not final_text or not final_text.strip():
            await thread.send("✅ Done (no output).")
            return not is_error

        prefix = "⚠️ " if is_error else ""
        chunks = chunk(prefix + final_text)
        for piece in chunks:
            await thread.send(piece)
        self.log(f"thread={thread.id} replied in {len(chunks)} message(s), {tool_count} tools")
        return not is_error


async def setup(bot: "ClaudeBot"):
    await bot.add_cog(ClaudeAgent(bot))

import asyncio
import json
import logging
from datetime import datetime, timezone
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings, normalize_database_url
from app.core.security import hash_password, encrypt_secret
from app.features.authentication.models import User
from app.features.workspaces_and_channels.models import (
    Workspace,
    WorkspaceMember,
    Channel,
    ChannelMember,
)
from app.features.messaging.models import Message
from app.features.integrations.models import ConnectedPlatform, ChannelLink

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed")


async def seed() -> None:
    target_url = settings.DATABASE_URL
    if not target_url:
        logger.error("DATABASE_URL is not set.")
        return

    clean_url, connect_args = normalize_database_url(target_url)
    engine = create_async_engine(clean_url, connect_args=connect_args)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        logger.info("Seeding Northwind Labs storyline into DATABASE_URL...")

        # 1. Users
        password_hash = hash_password("Password123!")

        # Alice Chen
        stmt = select(User).where(User.email == "alice@northwindlabs.com")
        alice = (await db.execute(stmt)).scalar_one_or_none()
        if not alice:
            alice = User(
                name="Alice Chen",
                email="alice@northwindlabs.com",
                password_hash=password_hash,
                avatar_color="#007AFF",
                created_at=datetime.now(timezone.utc),
            )
            db.add(alice)

        # Bob Okafor
        stmt = select(User).where(User.email == "bob@northwindlabs.com")
        bob = (await db.execute(stmt)).scalar_one_or_none()
        if not bob:
            bob = User(
                name="Bob Okafor",
                email="bob@northwindlabs.com",
                password_hash=password_hash,
                avatar_color="#34C759",
                created_at=datetime.now(timezone.utc),
            )
            db.add(bob)

        # Demo user for quick login
        stmt = select(User).where(User.email == "demo@example.com")
        demo_user = (await db.execute(stmt)).scalar_one_or_none()
        if not demo_user:
            demo_user = User(
                name="Alice Chen (Demo)",
                email="demo@example.com",
                password_hash=password_hash,
                avatar_color="#007AFF",
                created_at=datetime.now(timezone.utc),
            )
            db.add(demo_user)

        await db.commit()
        await db.refresh(alice)
        await db.refresh(bob)
        await db.refresh(demo_user)
        logger.info("Users seeded: Alice Chen, Bob Okafor, Demo User")

        # 2. Workspace: Northwind Labs
        stmt = select(Workspace).where(Workspace.name == "Northwind Labs")
        ws = (await db.execute(stmt)).scalar_one_or_none()
        if not ws:
            ws = Workspace(
                name="Northwind Labs",
                owner_id=alice.id,
                created_at=datetime.now(timezone.utc),
            )
            db.add(ws)
            await db.commit()
            await db.refresh(ws)

        # Memberships
        for user, role in [(alice, "owner"), (bob, "member"), (demo_user, "owner")]:
            m_stmt = select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == ws.id, WorkspaceMember.user_id == user.id
            )
            if not (await db.execute(m_stmt)).scalar_one_or_none():
                db.add(
                    WorkspaceMember(
                        workspace_id=ws.id,
                        user_id=user.id,
                        role=role,
                        joined_at=datetime.now(timezone.utc),
                    )
                )
        await db.commit()
        logger.info("Workspace 'Northwind Labs' and memberships seeded")

        # 3. Channels
        channels_spec = [
            ("general", "Company announcements and team watercooler"),
            ("product", "Product requirements, architectural designs, and roadmaps"),
            ("launch", "Launch readiness and cross-platform synchronization coordination"),
        ]
        ch_map: dict[str, Channel] = {}
        for ch_name, ch_desc in channels_spec:
            stmt = select(Channel).where(Channel.workspace_id == ws.id, Channel.name == ch_name)
            ch = (await db.execute(stmt)).scalar_one_or_none()
            if not ch:
                ch = Channel(
                    workspace_id=ws.id,
                    name=ch_name,
                    description=ch_desc,
                    created_by=alice.id,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(ch)
                await db.commit()
                await db.refresh(ch)
            ch_map[ch_name] = ch

            # Add channel memberships
            for user in [alice, bob, demo_user]:
                cm_stmt = select(ChannelMember).where(
                    ChannelMember.channel_id == ch.id, ChannelMember.user_id == user.id
                )
                if not (await db.execute(cm_stmt)).scalar_one_or_none():
                    db.add(ChannelMember(channel_id=ch.id, user_id=user.id, joined_at=datetime.now(timezone.utc)))
        await db.commit()
        logger.info("Channels seeded: #general, #product, #launch")

        # 4. Connected Platforms & Channel Links
        stmt = select(ConnectedPlatform).where(ConnectedPlatform.workspace_id == ws.id, ConnectedPlatform.platform == "slack")
        slack_platform = (await db.execute(stmt)).scalar_one_or_none()
        if not slack_platform:
            slack_tokens = json.dumps({"bot_token": "xoxb-mock-demo-token", "app_token": "xapp-mock-demo-token", "team_id": "T01NORTHWIND"})
            slack_platform = ConnectedPlatform(
                workspace_id=ws.id,
                platform="slack",
                encrypted_tokens=encrypt_secret(slack_tokens),
                bot_identity="U01BOTSLACK",
                display_name="Northwind Slack",
                created_at=datetime.now(timezone.utc),
            )
            db.add(slack_platform)
            await db.commit()
            await db.refresh(slack_platform)

        stmt = select(ConnectedPlatform).where(ConnectedPlatform.workspace_id == ws.id, ConnectedPlatform.platform == "discord")
        discord_platform = (await db.execute(stmt)).scalar_one_or_none()
        if not discord_platform:
            discord_tokens = json.dumps({"bot_token": "mock-discord-demo-token"})
            discord_platform = ConnectedPlatform(
                workspace_id=ws.id,
                platform="discord",
                encrypted_tokens=encrypt_secret(discord_tokens),
                bot_identity="1029384756",
                display_name="Northwind Discord",
                created_at=datetime.now(timezone.utc),
            )
            db.add(discord_platform)
            await db.commit()
            await db.refresh(discord_platform)

        # Link #launch to Slack and Discord
        launch_ch = ch_map["launch"]
        stmt = select(ChannelLink).where(ChannelLink.channel_id == launch_ch.id, ChannelLink.platform == "slack")
        if not (await db.execute(stmt)).scalar_one_or_none():
            db.add(
                ChannelLink(
                    channel_id=launch_ch.id,
                    platform_id=slack_platform.id,
                    platform="slack",
                    external_channel_id="C01LAUNCHSLACK",
                    external_channel_name="launch",
                    last_synced_external_id="1710000000.000100",
                    created_at=datetime.now(timezone.utc),
                )
            )

        stmt = select(ChannelLink).where(ChannelLink.channel_id == launch_ch.id, ChannelLink.platform == "discord")
        if not (await db.execute(stmt)).scalar_one_or_none():
            db.add(
                ChannelLink(
                    channel_id=launch_ch.id,
                    platform_id=discord_platform.id,
                    platform="discord",
                    external_channel_id="112233445566",
                    external_channel_name="launch",
                    encrypted_webhook_url=encrypt_secret("https://discord.com/api/webhooks/mock/test"),
                    webhook_id="112233445566",
                    last_synced_external_id="123456789012345678",
                    created_at=datetime.now(timezone.utc),
                )
            )
        await db.commit()

        # 5. Messages — Northwind Labs Storyline
        # Check if messages already exist in #launch
        m_count = (await db.execute(select(text("count(*)")).select_from(Message).where(Message.channel_id == launch_ch.id))).scalar()
        if m_count == 0:
            logger.info("Inserting Northwind Labs launch storyline messages...")

            # Message 1: Alice Chen (UniChat)
            msg1 = Message(
                channel_id=launch_ch.id,
                author_id=alice.id,
                body="Good morning team! We are 48 hours out from the v2.0 public release. How are we looking across all platforms?",
                source="unichat",
                created_at=datetime.now(timezone.utc),
            )
            db.add(msg1)
            await db.commit()
            await db.refresh(msg1)

            # Message 2: Priya Raman (Slack external)
            msg2 = Message(
                channel_id=launch_ch.id,
                author_id=None,
                external_author_name="Priya Raman",
                body="Product checks are clean. Stripe webhook testing passed in staging with zero failures. Ready to flip the DNS.",
                source="slack",
                external_id="1710000001.000200",
                external_channel_id="C01LAUNCHSLACK",
                created_at=datetime.now(timezone.utc),
            )
            db.add(msg2)
            await db.commit()

            # Message 3: Marco Diaz (Discord external)
            msg3 = Message(
                channel_id=launch_ch.id,
                author_id=None,
                external_author_name="Marco Diaz",
                body="Community beta testers report 99.4% uptime on the preview build. Mobile responsive view is silky smooth.",
                source="discord",
                external_id="123456789012345679",
                external_channel_id="112233445566",
                created_at=datetime.now(timezone.utc),
            )
            db.add(msg3)
            await db.commit()

            # Message 4: Bob Okafor (UniChat)
            msg4 = Message(
                channel_id=launch_ch.id,
                author_id=bob.id,
                body="Infra is locked in. Neon connection pooling and Upstash Redis clusters are standing by for launch traffic.",
                source="unichat",
                created_at=datetime.now(timezone.utc),
            )
            db.add(msg4)
            await db.commit()

            # Message 5: Alice Chen (UniChat)
            msg5 = Message(
                channel_id=launch_ch.id,
                author_id=alice.id,
                body="Incredible work everyone. Let's do the final smoke test tomorrow at 10 AM UTC.",
                source="unichat",
                created_at=datetime.now(timezone.utc),
            )
            db.add(msg5)
            await db.commit()

            # Thread Reply: Priya Raman replying to msg5
            reply = Message(
                channel_id=launch_ch.id,
                author_id=None,
                external_author_name="Priya Raman",
                body="I'll prepare the release notes and post to Product Hunt right as we go live.",
                source="slack",
                parent_id=msg5.id,
                external_id="1710000002.000300",
                external_channel_id="C01LAUNCHSLACK",
                created_at=datetime.now(timezone.utc),
            )
            db.add(reply)
            await db.commit()

        # #general messages
        gen_ch = ch_map["general"]
        gen_count = (await db.execute(select(text("count(*)")).select_from(Message).where(Message.channel_id == gen_ch.id))).scalar()
        if gen_count == 0:
            db.add(
                Message(
                    channel_id=gen_ch.id,
                    author_id=alice.id,
                    body="Welcome to Northwind Labs! All project updates, sync links, and announcements live here.",
                    source="unichat",
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.add(
                Message(
                    channel_id=gen_ch.id,
                    author_id=bob.id,
                    body="Excited to be here. Check out the pinned spec documents before submitting PRs.",
                    source="unichat",
                    created_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()

        # #product messages
        prod_ch = ch_map["product"]
        prod_count = (await db.execute(select(text("count(*)")).select_from(Message).where(Message.channel_id == prod_ch.id))).scalar()
        if prod_count == 0:
            db.add(
                Message(
                    channel_id=prod_ch.id,
                    author_id=alice.id,
                    body="Sprint goals: Complete the cross-platform two-way sync demo and verify grounded citation extraction.",
                    source="unichat",
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.add(
                Message(
                    channel_id=prod_ch.id,
                    author_id=bob.id,
                    body="All acceptance criteria mapped in specs/features and verified with automated test coverage.",
                    source="unichat",
                    created_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()

        logger.info("Northwind Labs storyline seeded successfully!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())

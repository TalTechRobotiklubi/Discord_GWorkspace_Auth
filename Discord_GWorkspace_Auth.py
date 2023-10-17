import json
import os
import re

import discord
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient import discovery

# Discord bot variables
INTENTS = discord.Intents().default()
INTENTS.members = True
INTENTS.guilds = True
INTENTS.messages = True
INTENTS.message_content = True

# Google API variables
# If modifying these SCOPES, delete the file token.pickle.
GOOGLE_SCOPES = ["openid",
                 "https://www.googleapis.com/auth/userinfo.email",
                 "https://www.googleapis.com/auth/userinfo.profile",
                 "https://www.googleapis.com/auth/admin.directory.group.readonly"]
GOOGLE_AUTH_REDIRECT_URI = "https://127.0.0.1/"
GOOGLE_CLIENT_SECRETS = ""

GUILD = "Robotiklubi"
GROUP_ROLE_PAIRS = {
    "juhatus@robotiklubi.ee": "Juhatus",
    "liikmed@robotiklubi.ee": "Liige",
    "vilistlased@robotiklubi.ee": "Vilistlane",
    # "kursandid@robotiklubi.ee": "Kursant"
}
global_group_member_pairs = {}


class Bot:
    def __init__(self, token, intents):

        async def create_auth_url_embed(authorization_url):
            embed = discord.Embed(title="Getting a role", description="", color=0x00ff00)
            embed.add_field(name="", value=f"", inline=False)
            embed.add_field(name="", value=f"write CANCEL in this chat to cancel this process or GET_ROLE to start again",
                            inline=False)
            embed.add_field(name="", value=f"", inline=False)
            embed.add_field(name="", value=f"If you dont answer within 120s you will have to restart this process",
                            inline=False)
            embed.add_field(name="", value=f"", inline=False)
            embed.add_field(name="Step 1", value="Click on the link given below", inline=False)
            embed.add_field(name="Step 2", value="Login. Ignore the \"This site can’t be reached\" error", inline=False)
            embed.add_field(name="Step 3", value="Post the resulting URL in this chat", inline=False)
            embed.add_field(name="Link", value=f"[Click me!]({authorization_url})", inline=False)
            return embed

        async def handle_response(response, state, member):
            if response.content == "CANCEL":
                await member.send("Canceling process")
                return
            if "https://127.0.0.1/" in response.content:
                if state not in response.content:
                    await member.send("Incorrect url")
                    await get_user_groups(member)
                pattern = r"(?:https://127\.0\.0\.1/\?.*code=)(.+?)(?:&scope=|$)(?:.*group.readonly)"
                code = re.search(pattern, response.content).group(1)
                if not code:
                    await member.send("No authorization code in given url")
                    await get_user_groups(member)
            else:
                await member.send("Incorrect url or timed out")
                await get_user_groups(member)

        async def get_user_groups(member):
            print(f"Sending embed to {member.name}")

            # Start the Google flow
            flow = Flow.from_client_config(client_config=GOOGLE_CLIENT_SECRETS,
                                           scopes=GOOGLE_SCOPES,
                                           redirect_uri=GOOGLE_AUTH_REDIRECT_URI)
            # Generate the login URL
            authorization_url, state = flow.authorization_url(
                # Enable offline access so that you can refresh the access token without
                # re-prompting the user for consent.
                access_type='offline',
                # Enable incremental authorization.
                include_granted_scopes='true')

            embed = await create_auth_url_embed(authorization_url)
            await member.send(embed=embed)
            dm_chan = await member.create_dm()
            response = ""
            try:
                response = await self.client.wait_for("message",
                                                      check=(lambda m: m.channel == dm_chan),
                                                      timeout=120.0)
            except Exception:
                print("Timed out")
                await member.send("Timed out, type GET_ROLE to start again")
                raise Exception("Role setting process timed out for {member.name}")

            await handle_response(response, state, member)

            print(f"Processing {member.name}")

            # Exchange the authorization code for an access token
            flow.fetch_token(authorization_response=response.content)

            # Use the access token to create a session and retrieve the user's profile information
            session = flow.authorized_session()
            profile_info = session.get(
                'https://www.googleapis.com/userinfo/v2/me').json()

            user_in_groups = []
            for email, members in global_group_member_pairs.items():
                if profile_info['email'] in members:
                    user_in_groups.append(email)

            return user_in_groups

        async def refresh_members_list(message):
            # Make token
            flow = InstalledAppFlow.from_client_config(
                GOOGLE_CLIENT_SECRETS,
                scopes=['https://www.googleapis.com/auth/admin.directory.group.readonly'],
                redirect_uri=GOOGLE_AUTH_REDIRECT_URI)
            await message.author.send(f"[Link]({flow.authorization_url()[0]})")
            dm_chan = message.channel
            response = await self.client.wait_for("message",
                                                  check=(lambda m: m.channel == dm_chan),
                                                  timeout=120.0)
            flow.fetch_token(authorization_response=response.content)
            query_service = discovery.build('admin',
                                            'directory_v1',
                                            credentials=flow.credentials)
            results_groups = query_service.groups().list(domain='robotiklubi.ee', maxResults=400).execute()
            groups = results_groups.get('groups', [])
            emails = []
            for group in groups:
                emails.append(group.get('email', []))

            for email in emails:
                results_members = query_service.members().list(maxResults=400, groupKey=email).execute()
                members = results_members.get('members', [])
                member_emails = []
                for member in members:
                    member_emails.append(member.get('email', []))
                # Update groups list
                global_group_member_pairs[email] = member_emails

        # INITIALIZE DISCORD CLIENT
        self.client = discord.Client(intents=intents)

        # Ready message
        @self.client.event
        async def on_ready():
            print(f'Logged in as {self.client.user}')

        # What to do when a new member joins the server
        @self.client.event
        async def on_member_join(member):
            # Find member in guild
            groups = await get_user_groups(member)
            guild = discord.utils.get(self.client.guilds, name=GUILD)

            # Assign roles based on the email-role pairs
            for key, value in GROUP_ROLE_PAIRS.items():
                if key in groups:
                    role = discord.utils.get(guild.roles, name=value)
                    await member.add_roles(role)
                    print(f"Added role {role.name} to {member.name}")

        @self.client.event
        async def on_message(message):
            # Ignore messages sent by the bot itself
            if message.author == self.client.user:
                return

            # Check if the message is a direct message
            if isinstance(message.channel, discord.channel.DMChannel):
                # Check if the message content matches a certain condition
                if "GET_ROLE" in message.content:
                    groups = await get_user_groups(message.author)
                    if groups:
                        # Find member in guild
                        author = message.author
                        guild = discord.utils.get(self.client.guilds, name=GUILD)
                        member = guild.get_member(author.id)
                        if not member or member is None:
                            print(f"No member, with author id: {author.id}")

                        # Assign roles based on the email-role pairs
                        for key, value in GROUP_ROLE_PAIRS.items():
                            if key in groups:
                                role = discord.utils.get(guild.roles, name=value)
                                await member.add_roles(role)
                                print(f"Added role {role.name} to {member.name}")
                                await member.send(f"Role '{role.name}' added")

                        print(f"Gave role(s) to {author}\n")
                elif "REFRESH_LOADED_WORKSPACE_GROUPS" in message.content:
                    print("Refreshing members list\n")
                    # THE USER HAS TO LOGIN WITH A WORKSPACE ACCOUNT THAT HAS VISIBILITY OF GROUPS
                    await refresh_members_list(message)

                    await message.author.send(
                        f"Keys: {global_group_member_pairs.keys()}\nSuccessfully loaded members lists")

        # Run the bot
        self.client.run(token)


if __name__ == '__main__':
    # Load env variables
    load_dotenv()
    GOOGLE_CLIENT_SECRETS = json.loads(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_TOKEN')

    bot = Bot(intents=INTENTS, token=DISCORD_BOT_TOKEN)
